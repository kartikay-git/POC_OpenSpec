import json
from pathlib import Path
import pytest
from agent.runtime import ROOT, Run, validate_name
from agent.tools import make_tools
from agent.workflow import plan, apply, archive

@pytest.fixture
def run():
    return Run.create("test-delete", "Add deletion of owned tasks", "fixture")

@pytest.mark.parametrize("name", ["../outside", "has space", "UPPER", "a--b", "a/b", ""])
def test_change_names_are_validated(name):
    with pytest.raises(ValueError):
        validate_name(name)

@pytest.mark.parametrize("path", ["../application/manage.py", "C:/Windows/test.py", "/tmp/test.py",
                                    "application/../agent/cli.py", "application/.env", "application/db.sqlite3",
                                    "agent/workflow.py", "application\\todos\\views.py"])
def test_paths_cannot_escape_or_read_secrets(run, path):
    with pytest.raises(ValueError):
        run.read(path)

def test_planning_cannot_edit_code_or_wrong_artifacts(run):
    run.save(phase="PLANNING", artifact="proposal")
    with pytest.raises(ValueError):
        run.write("application/todos/views.py", "changed")
    with pytest.raises(ValueError):
        run.write(run.change_prefix + "tasks.md", "changed")
    run.write(run.change_prefix + "proposal.md", "Allowed proposal")
    assert "Allowed" in run.read(run.change_prefix + "proposal.md")

def test_apply_cannot_edit_settings_or_frozen_specs(run):
    run.save(phase="APPLYING")
    for path in ["application/config/settings.py", "openspec/specs/tasks/spec.md", run.change_prefix + "proposal.md"]:
        with pytest.raises(ValueError):
            run.write(path, "bypass")

def test_tool_errors_are_visible_to_model(run):
    tool = next(tool for tool in make_tools(run) if tool.name == "read_file")
    assert "error" in tool.invoke({"path": "../secret.py"})

def test_artifact_tool_resolves_openspec_relative_paths(run):
    run.save(phase="PLANNING", artifact="specs")
    tools = {tool.name: tool for tool in make_tools(run)}
    assert "write_file" not in tools
    assert "replace_text" not in tools
    assert tools["write_artifact"].return_direct is True
    result = tools["write_artifact"].invoke({"content": "# Correctly located", "capability": "tasks"})
    assert "Wrote" in result
    assert run.read(run.change_prefix + "specs/tasks/spec.md") == "# Correctly located"
    assert "error" in tools["write_artifact"].invoke({"content": "bad", "capability": "../outside"})

def test_repeated_tool_errors_stop_the_loop(run):
    read = next(tool for tool in make_tools(run) if tool.name == "read_file")
    for _ in range(2):
        assert "error" in read.invoke({"path": "../secret.py"})
    with pytest.raises(RuntimeError, match="three repeated"):
        read.invoke({"path": "../secret.py"})

def test_task_completion_requires_passing_tests(run):
    run.save(phase="APPLYING")
    tool = next(tool for tool in make_tools(run) if tool.name == "mark_tasks_complete")
    assert "Run run_checks" in tool.invoke({})["error"]

def test_focused_stage_is_limited_to_its_assigned_file(run):
    run.save(phase="APPLYING", implementation_target="application/todos/views.py")
    tools = {tool.name: tool for tool in make_tools(run)}
    assert set(tools) == {"read_file", "write_implementation"}
    assert tools["write_implementation"].return_direct
    with pytest.raises(ValueError, match="assigned file"):
        run.write("application/todos/urls.py", "wrong target")

def test_invalid_python_is_rejected_before_overwriting(run):
    run.save(phase="APPLYING")
    original = run.read("application/todos/views.py")
    with pytest.raises(ValueError, match="Invalid Python"):
        run.write("application/todos/views.py", "return 'outside function'\n")
    assert run.read("application/todos/views.py") == original

def test_focused_recipe_with_scripted_model_and_real_checks(run):
    plan(run)
    apply(run, approved=True, strategy="focused")
    assert run.state["phase"] == "VERIFIED"
    assert run.state["mode"] == "fixture"
    assert run.state["implementation_target"] is None
    assert "- [ ]" not in run.read(run.change_prefix + "tasks.md")
    assert json.loads((run.directory / "verification.json").read_text())["passed"]

def test_real_openspec_rejects_malformed_delta(run):
    run.save(phase="PLANNING", artifact="specs")
    run.write(run.change_prefix + "specs/tasks/spec.md", "This is not a specification.")
    result = run.openspec("validate", run.change, "--type", "change", "--strict", "--json", "--no-interactive", check=False)
    assert result["returncode"] != 0

def test_plan_requires_approval_and_rejects_tampering(run):
    plan(run)
    assert run.state["phase"] == "PLAN_READY"
    assert not (run.workspace / "application/todos/test_deletion.py").exists()
    with pytest.raises(ValueError, match="approve-plan"):
        apply(run)
    proposal = run.workspace / run.change_prefix / "proposal.md"
    proposal.write_text(proposal.read_text() + "\nUnreviewed change.")
    with pytest.raises(ValueError, match="changed"):
        apply(run, approved=True)

def test_complete_real_cli_and_langchain_fixture_workflow(run):
    plan(run)
    apply(run, approved=True)
    assert run.state["phase"] == "VERIFIED"
    assert json.loads((run.directory / "verification.json").read_text())["passed"]
    archive(run)
    assert run.state["phase"] == "ARCHIVED"
    assert "Delete own tasks" in run.read("openspec/specs/tasks/spec.md")
    assert list((run.workspace / "openspec/changes/archive").iterdir())
    assert "task_delete" in (run.directory / "changes.diff").read_text()
    assert "scripted" in json.loads((run.directory / "report.json").read_text())["interpretation"].lower()
    assert "task_delete" not in (ROOT / "application/todos/views.py").read_text()

def test_incomplete_code_fails_independent_checks_and_cannot_archive(run):
    run.save(phase="APPLYING")
    evidence = run.verify()
    assert not evidence["passed"]  # Baseline deliberately lacks deletion.
    with pytest.raises(ValueError, match="verified"):
        archive(run)

def test_task_descriptions_cannot_be_removed_during_apply(run):
    run.save(phase="PLANNING", artifact="tasks")
    run.write(run.change_prefix + "tasks.md", "- [ ] 1.1 Important work\n")
    run.save(phase="APPLYING")
    with pytest.raises(ValueError, match="checkbox"):
        run.write(run.change_prefix + "tasks.md", "All done\n")
    run.write(run.change_prefix + "tasks.md", "- [x] 1.1 Important work\n")

def test_verified_phase_disables_edits(run):
    run.save(phase="VERIFIED")
    with pytest.raises(ValueError, match="disabled"):
        run.write("application/todos/views.py", "changed")
