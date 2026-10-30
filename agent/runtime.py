"""Controlled local workspace and observable, fixed command execution."""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEXT_SUFFIXES = {".py", ".html", ".css", ".md", ".yaml"}
SECRET_PARTS = {".env", ".local-secret", ".git", "__pycache__", "node_modules", ".venv"}

def now():
    return datetime.now(timezone.utc).isoformat()

def validate_name(name):
    if not NAME_PATTERN.fullmatch(name) or len(name) > 80:
        raise ValueError("Use a lowercase kebab-case name of at most 80 characters.")
    return name

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

class Run:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.state_path = self.directory / "state.json"
        self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.workspace = self.directory / "workspace"
        self.change = validate_name(self.state["change"])
        self.change_prefix = f"openspec/changes/{self.change}/"
        self.tool_calls = 0

    @classmethod
    def create(cls, change, requirement, mode, acceptance="task-deletion"):
        validate_name(change)
        if not requirement.strip():
            raise ValueError("Requirement must not be blank.")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        directory = ROOT / "runs" / f"{stamp}-{change}"
        workspace = directory / "workspace"
        workspace.mkdir(parents=True)
        ignore = shutil.ignore_patterns("__pycache__", "*.sqlite3*", ".local-secret", ".env")
        shutil.copytree(ROOT / "application", workspace / "application", ignore=ignore)
        shutil.copytree(ROOT / "openspec" / "specs", workspace / "openspec" / "specs")
        shutil.copy2(ROOT / "openspec" / "config.yaml", workspace / "openspec" / "config.yaml")
        shutil.copy2(ROOT / ".gitignore", workspace / ".gitignore")
        write_json(directory / "state.json", {
            "change": change, "requirement": requirement, "mode": mode,
            "acceptance": acceptance, "phase": "CREATED", "created_at": now(),
            "provider": "codex-cli" if mode == "live" else "fixture",
            "model": os.environ.get("CODEX_MODEL", "gpt-6-luna") if mode == "live" else "scripted-fixture",
        })
        run = cls(directory)
        run.command(["git", "init", "--quiet"])
        run.command(["git", "add", "application", "openspec", ".gitignore"])
        run.command(["git", "-c", "user.name=POC Baseline", "-c", "user.email=poc@localhost", "commit", "--quiet", "-m", "Baseline before agent change"])
        run.openspec("new", "change", change)
        return run

    def save(self, **updates):
        self.state.update(updates)
        self.state["updated_at"] = now()
        write_json(self.state_path, self.state)

    def event(self, kind, **data):
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": now(), "kind": kind, **data}, ensure_ascii=False) + "\n")

    def command(self, argv, timeout=120, check=True):
        # Fixed argv, never a model-supplied shell string. Test children do not need credentials.
        env = {key: value for key, value in os.environ.items()
               if not any(marker in key.upper() for marker in ("API_KEY", "TOKEN", "PASSWORD", "SECRET"))}
        env.update({"OPENSPEC_TELEMETRY": "0", "NO_COLOR": "1", "PYTHONUTF8": "1",
                    "PYTHONPATH": str(ROOT)})
        self.event("command_start", argv=[str(x) for x in argv])
        try:
            result = subprocess.run([str(x) for x in argv], cwd=self.workspace, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False)
        except subprocess.TimeoutExpired:
            self.event("command_timeout", argv=[str(x) for x in argv], timeout=timeout)
            raise RuntimeError(f"Command exceeded {timeout}s: {argv[0]}")
        data = {"argv": [str(x) for x in argv], "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}
        self.event("command_result", **data)
        if check and result.returncode:
            raise RuntimeError(f"Command failed: {argv}\n{result.stdout}\n{result.stderr}")
        return data

    def openspec(self, *args, check=True):
        node = shutil.which("node")
        cli = ROOT / "node_modules/@fission-ai/openspec/bin/openspec.js"
        if not node or not cli.exists():
            raise RuntimeError("Node/OpenSpec missing. Run npm ci from the project root.")
        return self.command([node, cli, *args], check=check)

    def openspec_json(self, *args):
        return json.loads(self.openspec(*args, "--json")["stdout"])

    def path(self, relative):
        # Absolute paths, alternate streams, traversal and links outside the copy are rejected.
        if not relative or "\\" in relative or ":" in relative:
            raise ValueError("Use a repository-relative path with forward slashes.")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or any(p in SECRET_PARTS for p in candidate.parts):
            raise ValueError("Path is outside the allowed source tree.")
        path = (self.workspace / candidate).resolve()
        if not path.is_relative_to(self.workspace.resolve()):
            raise ValueError("Path escapes the run workspace.")
        if candidate.parts[0] not in {"application", "openspec"} or path.suffix not in TEXT_SUFFIXES:
            raise ValueError("Only application and OpenSpec text sources can be accessed.")
        return path

    def files(self):
        results = []
        for directory in ("application", "openspec"):
            for path in (self.workspace / directory).rglob("*"):
                relative = path.relative_to(self.workspace).as_posix()
                try:
                    resolved = self.path(relative)
                except ValueError:
                    continue
                if resolved.is_file():
                    results.append(relative)
        return sorted(results)

    def read(self, relative):
        path = self.path(relative)
        if path.stat().st_size > 100_000:
            raise ValueError("File exceeds the 100 KB read limit.")
        return path.read_text(encoding="utf-8")

    def write(self, relative, content):
        path = self.path(relative)
        if len(content.encode("utf-8")) > 100_000:
            raise ValueError("File exceeds the 100 KB write limit.")
        phase = self.state["phase"]
        if phase == "PLANNING":
            target = self.state.get("artifact")
            expected = self.change_prefix + {"proposal": "proposal.md", "design": "design.md", "tasks": "tasks.md"}.get(target, "specs/")
            allowed = relative == expected if target != "specs" else relative.startswith(expected) and relative.endswith("/spec.md")
            if not allowed:
                raise ValueError(f"Planning may only write the current {target} artifact.")
        elif phase == "APPLYING":
            target = self.state.get("implementation_target")
            if target and relative != target:
                raise ValueError("Focused implementation may only write its assigned file.")
            allowed = relative.startswith(("application/todos/", "application/templates/", "application/static/"))
            if relative == self.change_prefix + "tasks.md":
                old = path.read_text(encoding="utf-8")
                if normalize_tasks(old) != normalize_tasks(content):
                    raise ValueError("During apply, tasks may only change checkbox state.")
                allowed = True
            if not allowed:
                raise ValueError("Apply may only edit todo code/templates/static and task checkboxes.")
        else:
            raise ValueError(f"Writes are disabled in phase {phase}.")
        if path.suffix == ".py":
            try:
                compile(content, relative, "exec")
            except SyntaxError as exc:
                raise ValueError(f"Invalid Python at line {exc.lineno}: {exc.msg}. Fix syntax before saving.") from exc
        path.parent.mkdir(parents=True, exist_ok=True)
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(content, encoding="utf-8")
        diff = "".join(difflib.unified_diff(before.splitlines(True), content.splitlines(True), fromfile=relative, tofile=relative))
        self.event("file_write", path=relative, diff=diff)
        return f"Wrote {relative} ({len(content)} characters)."

    def plan_hash(self):
        digest = hashlib.sha256()
        folder = self.workspace / "openspec/changes" / self.change
        for path in sorted(folder.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            if path.name == "tasks.md":
                text = normalize_tasks(text)
            digest.update(path.relative_to(folder).as_posix().encode())
            digest.update(text.encode())
        return digest.hexdigest()

    def verify(self):
        manage = self.workspace / "application/manage.py"
        commands = [[sys.executable, manage, "check"],
                    [sys.executable, manage, "makemigrations", "--check", "--dry-run"],
                    [sys.executable, manage, "test", "todos", "--verbosity", "2"],
                    [sys.executable, manage, "test", "verification.test_baseline", "--verbosity", "2"]]
        if self.state["acceptance"] == "task-deletion":
            commands.append([sys.executable, manage, "test", "verification.test_deletion", "--verbosity", "2"])
        results = [self.command(command, check=False) for command in commands]
        passed = all(result["returncode"] == 0 for result in results)
        evidence = {"passed": passed, "checked_at": now(), "results": results}
        write_json(self.directory / "verification.json", evidence)
        return evidence

    def diff(self):
        self.command(["git", "add", "--intent-to-add", "application", "openspec"])
        return self.command(["git", "diff", "HEAD", "--", "application", "openspec"])["stdout"]

def normalize_tasks(text):
    return re.sub(r"(?m)^(\s*-\s*)\[[ xX]\]", r"\1[ ]", text)
