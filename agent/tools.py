"""Tools are ordinary Python functions registered with LangChain's @tool."""
import json
import os
import re
from functools import wraps
from langchain.tools import tool
from .runtime import validate_name

def make_tools(run):
    def observed(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            run.tool_calls += 1
            if run.tool_calls > int(os.environ.get("AGENT_MAX_TOOL_CALLS", "100")):
                raise RuntimeError("Agent tool-call budget exhausted.")
            run.event("tool_call", tool=function.__name__, arguments=kwargs)
            print(f"  tool: {function.__name__}", flush=True)
            try:
                result = function(*args, **kwargs)
            except (ValueError, OSError, RuntimeError) as exc:
                result = {"error": str(exc)}
            run.event("tool_result", tool=function.__name__, result=result)
            if isinstance(result, dict) and "error" in result:
                message = result["error"]
                run.repeated_errors = getattr(run, "repeated_errors", 0) + 1 if getattr(run, "last_error", None) == message else 1
                run.last_error = message
                if run.repeated_errors >= 3:
                    raise RuntimeError(f"Stopped after three repeated tool errors: {message}")
            else:
                run.last_error, run.repeated_errors = None, 0
            return result
        return wrapper

    @tool
    @observed
    def list_files() -> list[str]:
        """List accessible source/spec files in the current isolated repository."""
        return run.files()

    @tool
    @observed
    def read_file(path: str) -> str:
        """Read one UTF-8 source file by repository-relative forward-slash path."""
        return run.read(path)

    @tool
    @observed
    def write_file(path: str, content: str) -> str:
        """Write a complete UTF-8 file. Planning and apply have enforced path limits."""
        return run.write(path, content)

    @tool(return_direct=True)
    @observed
    def write_artifact(content: str, capability: str = "tasks") -> str:
        """Write the CURRENT planning artifact. The controller resolves its path.

        For the specs stage, capability is the spec capability name (usually tasks).
        For proposal/design/tasks the capability argument is ignored.
        Pass Markdown content only, not a JSON wrapper or fenced Markdown block.
        """
        if run.state["phase"] != "PLANNING":
            raise ValueError("Artifact writing is only available during planning.")
        artifact = run.state["artifact"]
        file = f"specs/{validate_name(capability)}/spec.md" if artifact == "specs" else f"{artifact}.md"
        return run.write(run.change_prefix + file, content)

    @tool(return_direct=True)
    @observed
    def write_implementation(content: str) -> str:
        """Save the complete source content for the CURRENT implementation file.

        The controller chooses the path. Pass source code/HTML only, no Markdown fences.
        This tool performs the edit and ends the current file's stage.
        """
        target = run.state.get("implementation_target")
        if run.state["phase"] != "APPLYING" or not target:
            raise ValueError("No focused implementation file is active.")
        return run.write(target, content)

    @tool
    @observed
    def replace_text(path: str, old: str, new: str) -> str:
        """Replace exactly one occurrence in an existing file. Read it first."""
        content = run.read(path)
        if not old or content.count(old) != 1:
            raise ValueError("old must match exactly one occurrence; read the file and retry.")
        return run.write(path, content.replace(old, new, 1))

    @tool
    @observed
    def openspec_status() -> dict:
        """Get real OpenSpec artifact completion/dependency status for this change."""
        return run.openspec_json("status", "--change", run.change)

    @tool
    @observed
    def openspec_instructions(artifact: str) -> dict:
        """Get actual OpenSpec instructions: proposal, specs, design, tasks, or apply."""
        if artifact not in {"proposal", "specs", "design", "tasks", "apply"}:
            raise ValueError("Unsupported artifact.")
        return run.openspec_json("instructions", artifact, "--change", run.change)

    @tool
    @observed
    def validate_specs() -> dict:
        """Run the real OpenSpec validator on the proposed change (not app tests)."""
        return run.openspec("validate", run.change, "--type", "change", "--strict", "--json", "--no-interactive", check=False)

    @tool
    @observed
    def run_checks() -> dict:
        """Run Django checks, migrations check, app tests, and protected acceptance tests."""
        if run.state["phase"] != "APPLYING":
            raise ValueError("Application checks are enabled only in APPLYING.")
        evidence = run.verify()
        return {"passed": evidence["passed"], "results": [
            {"argv": r["argv"], "returncode": r["returncode"], "output": (r["stdout"] + r["stderr"])[-16000:]}
            for r in evidence["results"]]}

    @tool
    @observed
    def git_diff() -> str:
        """Show source and specification changes relative to this run's baseline."""
        return run.diff()[:30000]

    @tool
    @observed
    def mark_tasks_complete() -> str:
        """Mark checklist boxes complete after run_checks passes. Preserve all task text.

        The controller independently rechecks the final code before accepting the run.
        """
        if run.state["phase"] != "APPLYING":
            raise ValueError("Task completion is only available during apply.")
        evidence = run.directory / "verification.json"
        if not evidence.exists() or not json.loads(evidence.read_text())["passed"]:
            raise ValueError("Run run_checks and fix all failures before completing tasks.")
        path = run.change_prefix + "tasks.md"
        content = re.sub(r"(?m)^(\s*-\s*)\[ \]", r"\1[x]", run.read(path))
        return run.write(path, content)

    if run.state["phase"] == "PLANNING":
        return [list_files, read_file, write_artifact, openspec_status, openspec_instructions, validate_specs]
    if run.state.get("implementation_target"):
        return [read_file, write_implementation]
    return [list_files, read_file, write_file, replace_text, openspec_status,
            openspec_instructions, validate_specs, run_checks, git_diff, mark_tasks_complete]
