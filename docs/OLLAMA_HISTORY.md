# Historical Ollama experiment

This is the command journal from the earlier provider, retained as evidence.
The active provider is now Codex CLI / GPT-6 Luna. Do not use this file as the current setup guide.
Statements about unchanged container configuration describe the initial CPU attempt only;
see GPU_SETUP.md for the later explicitly approved GPU replacement.
No new model was downloaded. Both Ollama live implementations failed acceptance checks.

# Command journal and reproduction reference

Working directory for these commands: `F:\Projects\openspec-langchain-poc`.
PowerShell is used throughout. `npm.cmd` avoids PowerShell's `npm.ps1` wrapper.
Commands shown with placeholders must use the real run path printed by the CLI.
No global OpenSpec package, remote repository, cloud deployment, or model download
was created. The user's existing Ollama Docker container was reused.

## Environment inspection

```powershell
python --version
node --version
npm.cmd --version
git --version
uv --version
Invoke-RestMethod -Uri 'http://localhost:11434/api/tags' -TimeoutSec 20
Invoke-RestMethod -Uri 'http://localhost:11434/api/ps' -TimeoutSec 15
docker ps --format '{{.Names}} | {{.Image}} | {{.Ports}}'
```

Observed: Python 3.13.9, Node 24.20.0, npm 11.19.0, Git 2.55.0, uv 0.11.33.
The `ollama` container published port 11434. It listed Qwen 2.5 and Mistral; Qwen
reported `size_vram: 0`, indicating CPU inference for this run. No existing model
or container settings were changed.

## Initial installation commands actually used

```powershell
New-Item -ItemType Directory -Path 'F:\Projects\openspec-langchain-poc' -Force
Set-Location 'F:\Projects\openspec-langchain-poc'
$env:UV_CACHE_DIR = 'F:\Projects\openspec-langchain-poc\.uv-cache'
uv venv .venv --python 3.13
uv lock
uv sync --locked
npm.cmd install --save-dev --save-exact @fission-ai/openspec --cache .npm-cache --no-audit --no-fund
$env:OPENSPEC_TELEMETRY = '0'
.\node_modules\.bin\openspec.cmd --version
.\node_modules\.bin\openspec.cmd init --tools none
uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock
```

The initial `python -m venv` attempt failed in ensurepip and was made one directory
too high. Its newly created, unused environment was removed after checking its
absolute path. A first uv attempt hit sandbox cache permissions; setting a
project-local `UV_CACHE_DIR` resolved it. These failed attempts did not supply the
final environment. Local socket access and package downloads needed the execution
environment's network approval; they were then allowed. No application error was
hidden by these setup retries.

The OpenSpec install pinned 1.15.0. The full Python versions and hashes are in
`uv.lock` and `requirements.lock`. For repeat installations use:

```powershell
.\scripts\setup.ps1
# Internally uses uv sync --locked (or hashed pip fallback), then:
npm.cmd ci --cache .npm-cache --no-audit --no-fund
```

## Inspect the real OpenSpec interface

During development a temporary change was created to inspect the installed CLI:

```powershell
.\node_modules\.bin\openspec.cmd new change inspect-workflow
.\node_modules\.bin\openspec.cmd instructions proposal --change inspect-workflow --json
.\node_modules\.bin\openspec.cmd validate --help
.\node_modules\.bin\openspec.cmd archive --help
```

The temporary inspection change was removed afterward; it is not an unfinished
project change. Schema instructions were also read from the installed package's
`schemas/spec-driven/schema.yaml`. Production runs create their own isolated changes.

## Prepare and test the baseline

```powershell
.\.venv\Scripts\python.exe application\manage.py migrate --noinput
.\.venv\Scripts\python.exe application\manage.py seed_demo
.\.venv\Scripts\python.exe application\manage.py check
.\.venv\Scripts\python.exe application\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe application\manage.py test todos --verbosity 2
.\node_modules\.bin\openspec.cmd validate --specs --strict --json --no-interactive
.\.venv\Scripts\python.exe -m compileall -q agent application verification
.\.venv\Scripts\python.exe -m pytest -q
```

The baseline has eight tests. The initial controller suite had 23 passing tests;
the artifact-path regression test was added after the first live run. Current
counts and outcomes are recorded in `TEST_REPORT.md`.

The focused retest after that adapter fix was:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_workflow.py -k 'artifact_tool or complete_real'
```

Both selected tests passed, including the entire scripted integration workflow.

## Live Ollama experiment

```powershell
.\.venv\Scripts\python.exe -m agent.cli doctor
.\.venv\Scripts\python.exe -m agent.cli demo --mode live --change add-task-deletion
```

The initial run directory was:

```text
runs/20261030T054938521532Z-add-task-deletion
```

The model wrote a proposal, then repeated a change-relative spec path against a
repository-relative file tool. Both writes were rejected. The run was interrupted
to improve the adapter rather than spend more CPU time repeating the same error.
After adding `write_artifact` and a regression test, planning resumed with:

```powershell
.\.venv\Scripts\python.exe -m agent.cli resume-plan `
  --run 'runs\20261030T054938521532Z-add-task-deletion'
```

Continuation uses the same directory and records its provenance in `events.jsonl`.
The proposal is preserved. The following commands apply and archive a ready plan:

```powershell
$run = 'runs\20261030T054938521532Z-add-task-deletion'
.\.venv\Scripts\python.exe -m agent.cli apply --run $run --approve-plan
.\.venv\Scripts\python.exe -m agent.cli archive --run $run
.\.venv\Scripts\python.exe -m agent.cli inspect --run $run
```

See `TEST_REPORT.md` for the final observed result, rather than assuming every
listed continuation command succeeded.

Before approval, review feedback was sent with `agent.cli revise-plan` for both
proposal and specs. Remaining semantic mistakes were corrected using the explicit
one-off reviewer script, which preserves the original model outputs and records
the edits/reasons:

```powershell
.\.venv\Scripts\python.exe -m scripts.correct_recorded_plan `
  --run 'runs\20261030T054938521532Z-add-task-deletion'
```

The script is not part of the agent's automatic workflow and is intentionally
specific to the recorded first plan. It did not write application code. The model
still performs implementation through the normal LangChain apply loop.

## Commands the controller executes inside each working copy

The `openspec` executable below is shorthand for `node` plus the project's exact
`node_modules/@fission-ai/openspec/bin/openspec.js` path. Each argument is passed
separately without a shell. The event log contains the expanded argument arrays.

```text
git init --quiet
git add application openspec .gitignore
git -c user.name=POC Baseline -c user.email=poc@localhost commit --quiet -m Baseline before agent change
openspec new change <change>
openspec status --change <change> --json
openspec instructions proposal --change <change> --json
openspec instructions specs --change <change> --json
openspec instructions design --change <change> --json
openspec instructions tasks --change <change> --json
openspec validate <change> --type change --strict --json --no-interactive
openspec instructions apply --change <change> --json
python <workspace>/application/manage.py check
python <workspace>/application/manage.py makemigrations --check --dry-run
python <workspace>/application/manage.py test todos --verbosity 2
python <workspace>/application/manage.py test verification.test_baseline --verbosity 2
python <workspace>/application/manage.py test verification.test_deletion --verbosity 2
git add --intent-to-add application openspec
git diff HEAD -- application openspec
openspec archive <change> --yes
openspec validate --specs --strict --json --no-interactive
```

The model may request status, instructions, validation, tests, or diffs multiple
times. Tests are independently rerun by the controller after apply and before
archive. `events.jsonl` is the exact chronological record for a specific run.

## Browser preview commands

```powershell
# Baseline:
.\scripts\start.ps1
# Or explicit server invocation:
.\.venv\Scripts\python.exe application\manage.py runserver 127.0.0.1:8000 --noreload
# A verified live result:
.\scripts\start.ps1 -Latest
# Any particular run, on a separate port:
.\scripts\start.ps1 -Run $run -Port 8001
```

Stop a foreground server with Ctrl+C. The start script runs migrations and seeds
demo accounts in the selected copy before starting its server. This does not
copy production data or expose the server outside loopback.

## No hidden tool installers

`read_file`, `write_artifact`, `write_file`, `replace_text`, and the other tools are
implemented in `agent/tools.py` and `agent/runtime.py`. Installing LangChain is
sufficient to register them. Their actual operations use `pathlib`, `subprocess`,
`json`, and other Python standard-library modules. There is no MCP server, RAG
database, vector index, paid cloud service, or separately installed filesystem
toolkit required for this POC.
