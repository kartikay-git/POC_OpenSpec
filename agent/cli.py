import argparse
import json
import os
import sys
import subprocess
import shutil
from dotenv import load_dotenv
from .runtime import ROOT, Run
from .workflow import apply, archive, plan, report, revise

REQUIREMENT = "Add a delete button for logged-in users to delete their own existing tasks."

def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Local OpenSpec + LangChain coding-agent POC")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Check dependencies and Codex login without modifying a run")
    for name in ("plan", "demo"):
        p = sub.add_parser(name)
        p.add_argument("--requirement", default=REQUIREMENT)
        p.add_argument("--change", default="add-task-deletion")
        p.add_argument("--mode", choices=("live", "fixture"), default="live")
        p.add_argument("--acceptance", choices=("task-deletion", "baseline"), default="task-deletion")
    for name in ("apply", "archive", "inspect", "resume-plan", "revise-plan"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True, type=PathArgument)
        if name == "apply":
            p.add_argument("--approve-plan", action="store_true")
            p.add_argument("--strategy", choices=("loop", "focused"), default=None)
        if name == "revise-plan":
            p.add_argument("--artifact", choices=("proposal", "specs", "design", "tasks"), required=True)
            p.add_argument("--feedback", required=True)
    args = parser.parse_args()
    if args.command == "doctor":
        import django, langchain
        print(f"Python {sys.version.split()[0]}, Django {django.get_version()}, LangChain {langchain.__version__}")
        print(f"OpenSpec CLI installed: {(ROOT / 'node_modules/@fission-ai/openspec/bin/openspec.js').exists()}")
        executable = shutil.which(os.environ.get("CODEX_EXECUTABLE", "codex"))
        if not executable:
            raise SystemExit("Install Codex CLI and run codex login, or set CODEX_EXECUTABLE.")
        result = subprocess.run([executable, "login", "status"], capture_output=True, text=True, timeout=30)
        print(result.stdout + result.stderr)
        print(f"Selected model: {os.environ.get('CODEX_MODEL', 'gpt-6-luna')}")
        if result.returncode:
            raise SystemExit("Codex authentication is missing. Run codex login in your terminal.")
        return
    run = None
    try:
        if args.command in {"plan", "demo"}:
            run = Run.create(args.change, args.requirement, args.mode, args.acceptance)
            print(f"Run directory: {run.directory}", flush=True)
            plan(run)
            if args.command == "demo":
                # The demo command explicitly opts into the entire local sample workflow.
                apply(run, approved=True)
                archive(run)
        else:
            run = Run(args.run)
            if args.command == "apply":
                apply(run, approved=args.approve_plan, strategy=args.strategy)
            elif args.command == "archive":
                archive(run)
            elif args.command == "resume-plan":
                if run.state["phase"] not in {"PLANNING", "FAILED_PLAN"}:
                    raise ValueError("Only interrupted or failed planning can resume.")
                run.event("planning_resumed", previous_phase=run.state["phase"])
                plan(run)
            elif args.command == "revise-plan":
                revise(run, args.artifact, args.feedback)
            else:
                print(json.dumps(run.state, indent=2))
        print(f"Result: {run.state['phase']}\nReport: {run.directory / 'report.md'}", flush=True)
    except Exception as exc:
        if run:
            previous = run.state["phase"]
            # Refused operations must not destroy an otherwise usable state.
            if previous in {"PLANNING", "APPLYING"}:
                run.save(phase="FAILED_APPLY" if previous == "APPLYING" else "FAILED_PLAN", error=str(exc))
            run.event("error", error=str(exc))
            report(run)
            print(f"Run preserved: {run.directory}", file=sys.stderr)
        raise SystemExit(str(exc)) from exc

def PathArgument(value):
    from pathlib import Path
    return Path(value)

if __name__ == "__main__":
    main()
