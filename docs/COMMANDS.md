# Command journal and reproduction guide

Run these commands in PowerShell from `F:\Projects\openspec-langchain-poc`.
Historical Ollama commands are retained in OLLAMA_HISTORY.md and GPU_SETUP.md.
The current provider is GPT-6 Luna through the signed-in Codex CLI.

## 1. Prerequisites and login

```powershell
Set-Location 'F:\Projects\openspec-langchain-poc'
python --version
node --version
npm.cmd --version
git --version
uv --version
codex --version
codex login status
```

Observed: Python 3.13.9, Node 24.20.0, npm 11.19.0, Git 2.55.0, uv 0.11.33,
Codex CLI 0.164.0-alpha.11.1, logged in using ChatGPT. The desktop CLI was reused.
On another machine without Codex, install/login with the following commands
(these were not used to replace this machine's existing CLI):

```powershell
npm.cmd install -g @openai/codex
codex login
```

Do not put a login token into .env. The adapter relies on Codex-managed login.
It uses current CLI options; older CLI versions may need an update.

## 2. Initial project installation

These commands established the project. Do not reinitialize its existing specs.

```powershell
$env:UV_CACHE_DIR = 'F:\Projects\openspec-langchain-poc\.uv-cache'
uv venv .venv --python 3.13
uv lock
uv sync --locked
npm.cmd install --save-dev --save-exact @fission-ai/openspec --cache .npm-cache --no-audit --no-fund
$env:OPENSPEC_TELEMETRY = '0'
.\node_modules\.bin\openspec.cmd --version
.\node_modules\.bin\openspec.cmd init --tools none
```

OpenSpec resolved to 1.15.0 and is pinned in package.json/package-lock.json.
`--tools none` initializes OpenSpec without assistant slash-command integrations;
our Python controller calls the CLI directly. uv.lock pins Python packages.

For repeat setup, use:

```powershell
.\scripts\setup.ps1
```

This runs `uv sync --locked`, then `npm.cmd ci --cache .npm-cache --no-audit --no-fund`,
copies .env.example only if .env is missing, migrates, and seeds the baseline.
Without uv, the script uses:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
```

No separate read/write-tool package is installed. Functions in agent/tools.py
use LangChain's `@tool` decorator and Python's pathlib/subprocess standard library.
No MCP server or vector database is required.

## 3. Replace Ollama with Codex (performed)

Removed langchain-ollama from pyproject.toml and synchronized the lock/environment:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
uv lock --offline
uv sync --locked --offline
uv export --format requirements-txt --output-file requirements.lock --no-dev --offline
```

This uninstalled langchain-ollama 1.1.0 and ollama 0.6.3 from the project venv.
Docker containers and the model volume were preserved. No model was downloaded.
The active .env selects CODEX_MODEL=gpt-6-luna, CODEX_REASONING_EFFORT=high,
CODEX_TIMEOUT=600, AGENT_RECURSION_LIMIT=80, and AGENT_MAX_TOOL_CALLS=100.
Optional CODEX_EXECUTABLE can specify a full executable path.

Successful connectivity probe:

```powershell
codex exec --ignore-user-config --ephemeral --skip-git-repo-check --sandbox read-only `
  --disable shell_tool --disable multi_agent --disable apps --disable plugins `
  -c 'web_search="disabled"' -m gpt-6-luna -c 'model_reasoning_effort="low"' `
  --json 'Reply only with OK. Do not use tools.'
.\.venv\Scripts\python.exe -m agent.cli doctor
```

The adapter executes the following argument array, with shell=False, in an empty
temporary working directory. The final `-` reads the prompt from stdin:

```text
codex exec --ignore-user-config --ephemeral --skip-git-repo-check
  --sandbox read-only --color never --json --model gpt-6-luna
  -c model_reasoning_effort="high" -c web_search="disabled"
  --output-schema <temporary-schema.json> --output-last-message <temporary-output.json>
  --disable shell_tool --disable multi_agent --disable apps --disable plugins
  --disable browser_use --disable computer_use --disable image_generation --disable hooks -
```

The schema requests one decision: tool name, JSON-encoded arguments, and final text.
The adapter validates it and creates a LangChain AIMessage with a tool call.
LangChain executes the actual Python function. This is structured-output tool
emulation, not native API function calling. Codex transport events and usage are
retained under each run's codex-transport directory. Authentication tokens are
never opened by project code. Requests use your Codex account usage limits.

## 4. Prepare and test the baseline

```powershell
.\.venv\Scripts\python.exe application\manage.py migrate --noinput
.\.venv\Scripts\python.exe application\manage.py seed_demo
.\scripts\test.ps1
.\scripts\start.ps1
```

Open http://127.0.0.1:8000. Local demo accounts: alice or bob / DemoPass123!.
The baseline intentionally has no deletion. Stop a foreground server with Ctrl+C.
The test script checks Django, migrations, eight baseline tests, two strict-valid
OpenSpec baseline specs, and the controller/adapter pytest suite. Pytest uses
`.pytest-tmp` because the desktop sandbox's system temporary folder was unwritable.

## 5. Plan, review, implement, verify, archive

```powershell
.\.venv\Scripts\python.exe -m agent.cli plan --mode live --change add-task-deletion `
  --requirement 'Add a delete button for logged-in users to delete their own existing tasks.'
$run = 'F:\Projects\openspec-langchain-poc\runs\<printed-run-directory>'
Get-Content "$run\workspace\openspec\changes\add-task-deletion\proposal.md"
Get-Content "$run\workspace\openspec\changes\add-task-deletion\specs\tasks\spec.md"
Get-Content "$run\workspace\openspec\changes\add-task-deletion\design.md"
Get-Content "$run\workspace\openspec\changes\add-task-deletion\tasks.md"
.\.venv\Scripts\python.exe -m agent.cli apply --run $run --approve-plan
.\.venv\Scripts\python.exe -m agent.cli archive --run $run
.\.venv\Scripts\python.exe -m agent.cli inspect --run $run
.\scripts\start.ps1 -Run $run
```

The combined command explicitly opts into the whole local experiment:

```powershell
.\.venv\Scripts\python.exe -m agent.cli demo --mode live --change another-deletion
.\scripts\start.ps1 -Latest
```

Recorded Codex execution used:

```powershell
.\.venv\Scripts\python.exe -m agent.cli plan --mode live --change codex-task-deletion
$run = 'runs\20261030T070131464642Z-codex-task-deletion'
# First low-effort request stopped without writing. After adapter clarification
# and selecting high reasoning, planning continued in the same evidence directory:
.\.venv\Scripts\python.exe -m agent.cli resume-plan --run $run
.\.venv\Scripts\python.exe -m agent.cli apply --run $run --approve-plan
.\.venv\Scripts\python.exe -m agent.cli archive --run $run
.\scripts\start.ps1 -Latest
```

Planning revision, when needed, uses:

```powershell
.\.venv\Scripts\python.exe -m agent.cli revise-plan --run $run --artifact specs `
  --feedback 'Describe the missing behavior precisely here.'
.\.venv\Scripts\python.exe -m agent.cli resume-plan --run $run
```

Revisions invalidate the approval fingerprint. Review dependent artifacts too.
`apply --strategy loop` selects the broader tool loop; default live task-deletion
uses a controller-defined sequence of four implementation files.

## 6. Commands inside each working copy

`openspec` below means `node <project>/node_modules/@fission-ai/openspec/bin/openspec.js`.
Actual expanded argv, timestamps, stdout/stderr, and exit statuses are in events.jsonl.

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

Git identity is command-local; no remote or push exists. Archive updates only that
run's OpenSpec baseline and archived change directory. It is not deployment.

## 7. Repeat without a model

```powershell
.\.venv\Scripts\python.exe -m agent.cli demo --mode fixture --change reference-task-deletion
.\scripts\start.ps1 -Reference
```

The fixture supplies predetermined decisions but executes real LangChain tools,
OpenSpec, and Django tests. It is infrastructure evidence, not model reasoning.
Every new run starts from the unchanged root baseline, not a previous result.
