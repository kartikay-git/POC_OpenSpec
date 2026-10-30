"""One-off, explicitly recorded reviewer corrections for the first live POC run.

This is NOT called by the agent workflow. It preserves the model's original
artifacts and records exactly what the reviewer corrected before approval.
Usage: python -m scripts.correct_recorded_plan --run <first-live-run-directory>
"""
import argparse
import shutil
from agent.runtime import Run
from agent.workflow import plan

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    run = Run(args.run)
    if run.state["phase"] != "PLAN_READY" or run.state.get("reviewer_corrections"):
        raise SystemExit("This recorded correction applies once, before the initial plan is approved.")
    original = run.workspace / "openspec/changes" / run.change
    shutil.copytree(original, run.directory / "before-reviewer-corrections")
    corrections = []

    def edit(artifact, filename, transform, reason):
        run.save(phase="PLANNING", artifact=artifact, plan_hash=None)
        path = run.change_prefix + filename
        content = transform(run.read(path))
        run.event("reviewer_edit", artifact=artifact, reason=reason)
        run.write(path, content)
        corrections.append({"artifact": artifact, "reason": reason})

    def spec(text):
        text = text.replace("## Purpose\n<!-- New capabilities only: one or two sentences (50+ characters) on what this capability is for. Delete this section for an existing capability. -->\n\n", "")
        text = text.replace("DELETE request", "POST request")
        text = text.replace("The system SHALL enforce user ownership and CSRF protection when deleting a task.",
            "The system SHALL provide a per-task delete form for logged-in users and enforce ownership, POST-only requests, and CSRF protection. Successful deletion SHALL persist after refresh.")
        old = "#### Scenario: Anonymous GET request returns 405\n- **WHEN** anonymous user sends a GET request to /tasks/<int:pk>/delete/\n- **THEN** server returns 405 Method Not Allowed and preserves the task"
        new = "#### Scenario: Anonymous request redirects to login\n- **WHEN** an anonymous user requests deletion\n- **THEN** the server redirects to login and preserves the task\n\n#### Scenario: Authenticated GET request returns 405\n- **WHEN** a logged-in user sends a GET request to /tasks/<int:pk>/delete/\n- **THEN** the server returns 405 Method Not Allowed and preserves the task"
        if old not in text:
            raise ValueError("Unexpected recorded spec; review it manually instead of applying this correction.")
        return text.replace(old, new)

    edit("specs", "specs/tasks/spec.md", spec,
         "Correct POST versus DELETE, separate anonymous redirects from authenticated GET, and require rendered form plus persistence.")
    edit("proposal", "proposal.md", lambda text: text.replace(
        "Modify the existing task deletion requirements to include server-side ownership enforcement and CSRF protection.",
        "Add owner-only deletion to the existing task creation and listing capability.") +
        "\n## Non-Goals\n\nBulk deletion, undo, registration, and schema changes are outside this experiment.\n",
        "Clarify that baseline deletion does not exist and record non-goals.")
    edit("design", "design.md", lambda text: text.replace(
        "- Redirect unauthorized GET requests to the login page.",
        "- Redirect unauthenticated requests to login; return 405 for authenticated GET requests."),
        "Remove ambiguous authentication/method handling in design.")

    def tasks(text):
        checks = {
            "1.1": "Verify the protected rendered-form test submits a valid CSRF-protected action.",
            "1.2": "Verify owner deletion redirects to / and persists after refresh.",
            "1.3": "Verify other users, anonymous requests, and GET cannot delete data.",
            "1.4": "Verify the protected rejection tests assert each specified status and preserve data.",
            "1.5": "Verify makemigrations --check and all baseline regression tests pass.",
            "1.6": "Run the application and protected acceptance suites and inspect their results.",
        }
        lines = []
        for line in text.splitlines():
            for task, check in checks.items():
                if line.startswith(f"- [ ] {task} "):
                    line = line.rstrip(".") + ". " + check
                    break
            lines.append(line)
        return "\n".join(lines) + "\n"
    edit("tasks", "tasks.md", tasks, "Make each task's verification explicit, as required by the OpenSpec task instructions.")
    run.save(reviewer_corrections=corrections, artifact=None)
    plan(run)  # Reuses corrected artifacts, validates them, and issues a new plan hash.

if __name__ == "__main__":
    main()
