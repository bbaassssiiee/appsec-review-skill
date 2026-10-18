#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes Claude to trigger (read the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.trigger_eval.utils import parse_skill_md

# Set on Ctrl-C. Every in-flight query checks it once a second, kills its
# claude subprocess and cleans up, so the run stops within a few seconds
# instead of hanging in the executor's shutdown.
STOP = threading.Event()

# Outcomes of a single run, from the stream claude -p emits.
OUTCOME_SKILL = "skill"            # first tool call was our skill: triggered
OUTCOME_OTHER_TOOL = "other-tool"  # first tool call was something else
OUTCOME_NO_TOOL = "no-tool"        # answered without any tool call
OUTCOME_TIMEOUT = "timeout"        # no decision before --timeout
OUTCOME_EXITED = "exited"          # claude exited before a decision (error?)
OUTCOME_INTERRUPTED = "interrupted"


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .claude/.

    Mimics how Claude Code discovers its project root, so the command file
    we create ends up where claude -p will look for it.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def remove_stale_command_files(project_root: Path, skill_name: str) -> int:
    """Delete command files a previous, interrupted run left behind.

    Each stale file is one more identical-looking skill in Claude's list, so
    the model may pick an old copy and the current run counts it as a miss.
    """
    commands_dir = project_root / ".claude" / "commands"
    if not commands_dir.is_dir():
        return 0
    removed = 0
    for stale in commands_dir.glob(f"{skill_name}-skill-*.md"):
        stale.unlink(missing_ok=True)
        removed += 1
    return removed


def write_command_file(commands_dir: Path, clean_name: str, skill_name: str, description: str) -> Path:
    """Create a command file so the skill appears in Claude's available_skills."""
    commands_dir.mkdir(parents=True, exist_ok=True)
    # Use YAML block scalar to avoid breaking on quotes in description
    indented_desc = "\n  ".join(description.split("\n"))
    command_file = commands_dir / f"{clean_name}.md"
    command_file.write_text(
        f"---\n"
        f"description: |\n"
        f"  {indented_desc}\n"
        f"---\n\n"
        f"# {skill_name}\n\n"
        f"This skill handles: {description}\n"
    )
    return command_file


def _kill_process_group(process: subprocess.Popen) -> None:
    """Kill claude and anything it spawned (it runs in its own session)."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _drain(stream, max_seconds: float) -> bytes:
    """Read what is left on a pipe without blocking on a grandchild that
    still holds the write end open."""
    data = b""
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        ready, _, _ = select.select([stream], [], [], 0.2)
        if not ready:
            continue
        chunk = os.read(stream.fileno(), 65536)
        if not chunk:
            break
        data += chunk
    return data


def run_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str | None,
    model: str | None = None,
) -> dict:
    """Run a single query and return {"triggered", "outcome", "elapsed"}.

    Registers the skill as a command file, runs `claude -p` with the raw
    query and watches the stream for the first tool call. By default the
    query runs in a throwaway directory that holds only the command file,
    so the model sees the skill the way an end user would, without this
    repository's files competing for its attention. Pass project_root to
    run inside a real project instead.

    Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the
    full assistant message, which only arrives after tool execution.
    """
    start_time = time.time()

    def outcome(name: str) -> dict:
        return {
            "triggered": name == OUTCOME_SKILL,
            "outcome": name,
            "elapsed": round(time.time() - start_time, 1),
        }

    if STOP.is_set():
        return outcome(OUTCOME_INTERRUPTED)

    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"

    sandbox: Path | None = None
    if project_root is None:
        sandbox = Path(tempfile.mkdtemp(prefix="trigger-eval-"))
        root = sandbox
    else:
        root = Path(project_root)
    command_file: Path | None = None

    try:
        command_file = write_command_file(
            root / ".claude" / "commands", clean_name, skill_name, skill_description
        )

        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        # start_new_session: the terminal's Ctrl-C must not reach claude
        # directly; this script owns its lifetime and kills the whole group.
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=root,
            env=env,
            start_new_session=True,
        )

        buffer = ""
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""

        try:
            while time.time() - start_time < timeout:
                if STOP.is_set():
                    return outcome(OUTCOME_INTERRUPTED)

                if process.poll() is not None:
                    buffer += _drain(process.stdout, 2.0).decode("utf-8", errors="replace")
                    exited = True
                else:
                    exited = False
                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if not ready:
                        continue
                    chunk = os.read(process.stdout.fileno(), 8192)
                    if not chunk:
                        exited = True
                    else:
                        buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Early detection via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    return outcome(OUTCOME_OTHER_TOOL)

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if clean_name in accumulated_json:
                                    return outcome(OUTCOME_SKILL)

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                if clean_name in accumulated_json:
                                    return outcome(OUTCOME_SKILL)
                                return outcome(OUTCOME_OTHER_TOOL)
                            if se_type == "message_stop":
                                return outcome(OUTCOME_NO_TOOL)

                    # Fallback: assistant message. Claude Code emits one
                    # "assistant" event per content block (thinking, text,
                    # tool_use), so only decide once a tool_use block shows
                    # up; a thinking or text block says nothing yet.
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                                return outcome(OUTCOME_SKILL)
                            if tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                                return outcome(OUTCOME_SKILL)
                            return outcome(OUTCOME_OTHER_TOOL)

                    elif event.get("type") == "result":
                        return outcome(OUTCOME_NO_TOOL)

                if exited:
                    return outcome(OUTCOME_EXITED)

            return outcome(OUTCOME_TIMEOUT)
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            _kill_process_group(process)
    finally:
        if command_file is not None:
            command_file.unlink(missing_ok=True)
        if sandbox is not None:
            shutil.rmtree(sandbox, ignore_errors=True)


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str | None,
    model: str | None = None,
) -> bool:
    """Run a single query and return whether the skill was triggered."""
    return run_query(query, skill_name, skill_description, timeout, project_root, model)["triggered"]


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path | None,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
    verbose: bool = False,
) -> dict:
    """Run the full eval set and return results.

    project_root=None runs every query in its own throwaway directory.
    On Ctrl-C, stops the in-flight queries, cleans up and re-raises.
    """
    if project_root is not None:
        removed = remove_stale_command_files(Path(project_root), skill_name)
        if removed:
            print(f"Removed {removed} stale command file(s) from a previous run", file=sys.stderr)

    total_runs = len(eval_set) * runs_per_query
    query_triggers: dict[str, list[bool]] = {}
    query_outcomes: dict[str, dict[str, int]] = {}
    query_items: dict[str, dict] = {}
    for item in eval_set:
        query_triggers[item["query"]] = []
        query_outcomes[item["query"]] = {}
        query_items[item["query"]] = item

    STOP.clear()
    # Threads, not processes: the work is waiting on subprocesses, and a
    # shared stop flag lets Ctrl-C reach every worker.
    executor = ThreadPoolExecutor(max_workers=num_workers)
    try:
        future_to_item = {}
        for item in eval_set:
            for _ in range(runs_per_query):
                future = executor.submit(
                    run_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    None if project_root is None else str(project_root),
                    model,
                )
                future_to_item[future] = item

        done = 0
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            query = item["query"]
            done += 1
            try:
                run = future.result()
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                run = {"triggered": False, "outcome": "error", "elapsed": 0.0}
            query_triggers[query].append(run["triggered"])
            query_outcomes[query][run["outcome"]] = query_outcomes[query].get(run["outcome"], 0) + 1
            if verbose:
                mark = "TRIGGERED" if run["triggered"] else "-"
                print(
                    f"  [{done}/{total_runs}] {mark:9} {run['outcome']:10} "
                    f"{run['elapsed']:5.1f}s  {query[:60]}",
                    file=sys.stderr,
                )
    except KeyboardInterrupt:
        STOP.set()
        print("\nInterrupted: stopping claude subprocesses...", file=sys.stderr)
        executor.shutdown(wait=True, cancel_futures=True)
        if project_root is not None:
            remove_stale_command_files(Path(project_root), skill_name)
        raise
    else:
        executor.shutdown(wait=True)

    results = []
    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers) if triggers else 0.0
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
            "outcomes": query_outcomes[query],
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    timeouts = sum(r["outcomes"].get(OUTCOME_TIMEOUT, 0) for r in results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "timeouts": timeouts,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model to use for claude -p (default: user's configured model)")
    parser.add_argument(
        "--in-project", action="store_true",
        help="Run claude -p inside the enclosing project (the one with .claude/) instead of a "
             "throwaway directory, so the model also sees the project's files",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root() if args.in_project else None

    if args.verbose:
        runs = len(eval_set) * args.runs_per_query
        print(f"Evaluating: {description}", file=sys.stderr)
        print(
            f"{len(eval_set)} queries x {args.runs_per_query} runs = {runs} claude -p calls, "
            f"{args.num_workers} at a time, {args.timeout}s timeout each",
            file=sys.stderr,
        )

    try:
        output = run_eval(
            eval_set=eval_set,
            skill_name=name,
            description=description,
            num_workers=args.num_workers,
            timeout=args.timeout,
            project_root=project_root,
            runs_per_query=args.runs_per_query,
            trigger_threshold=args.trigger_threshold,
            model=args.model,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        sys.exit(130)

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        if summary["timeouts"]:
            print(
                f"  {summary['timeouts']} run(s) hit the {args.timeout}s timeout and count as not triggered; "
                f"raise --timeout if that is unexpected",
                file=sys.stderr,
            )
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
