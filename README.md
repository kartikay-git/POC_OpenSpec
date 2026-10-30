# OpenSpec + LangChain local POC

A real, inspectable experiment: a LangChain agent uses OpenSpec's CLI instructions
to plan and implement a feature in a small authenticated Django todo application.
The model is **GPT-6 Luna through your signed-in Codex CLI**. No Ollama server,
model download, GPU, or API key is required for the configured ChatGPT login.
Model requests run remotely and consume your Codex account usage.
LangChain owns the project tools; a custom adapter translates Codex structured
responses into LangChain tool calls (not native OpenAI API tool calling).

**Verified live result:** GPT-6 Luna generated the deletion feature, passed all
25 application/acceptance tests, and completed OpenSpec archive. The controller/
adapter suite passes 35 tests. Run `.\scripts\start.ps1 -Latest` to try it.

Start with [the full implementation walkthrough](docs/IMPLEMENTATION.md). It explains
each component, installation command, tool, workflow transition, and test.
[The command journal](docs/COMMANDS.md) records setup and verification commands.
[The test report](docs/TEST_REPORT.md) distinguishes live-model results from fixture tests.
[GPU setup and verification](docs/GPU_SETUP.md) records the approved switch of your
earlier Ollama container to the RTX 4060, including the preserved CPU backup.
Ollama is no longer a project dependency. Existing Docker containers/model data were preserved.

## Quick start (PowerShell)

Prerequisites: Python 3.11+, Node 20.19+, Git, and a current Codex CLI with a working login. This project was built with Python 3.13 and Node 24. `uv` is preferred;
the setup script falls back to pip. No global OpenSpec installation is needed.

```powershell
Set-Location 'F:\Projects\openspec-langchain-poc'
.\scripts\setup.ps1
.\scripts\test.ps1
.\.venv\Scripts\python.exe -m agent.cli doctor
.\scripts\start.ps1
```

Open http://127.0.0.1:8000/. Local demo accounts: **alice** and **bob**, initial
password **DemoPass123!**. The seed command preserves existing passwords.
The baseline intentionally has create/list/login/logout and **no deletion**.

## Run the complete live experiment

Stop the baseline server with Ctrl+C, or use another terminal for the agent:

```powershell
.\.venv\Scripts\python.exe -m agent.cli demo --mode live --change add-task-deletion
.\scripts\start.ps1 -Latest
```

`demo` explicitly opts into planning, local implementation, independent tests,
and archive for this experiment. It prints a unique run directory. It never
modifies the baseline app. `-Latest` selects the newest verified/archived **live** run.
An archived change is an OpenSpec documentation operation, not deployment or Git merge.

For the live deletion profile the default implementation strategy is **focused**:
the controller gives the model one of four files at a time and exposes a dedicated
write tool. This recipe is specific to this POC, not a general autonomous coding
planner. To test the broader free-form tool loop, pass `--strategy loop` to `apply`.
The first Qwen run generated prose instead of edits in the broader loop; that
failure was caught by the protected acceptance tests.

For a review between planning and implementation:

```powershell
.\.venv\Scripts\python.exe -m agent.cli plan --mode live --change add-task-deletion `
  --requirement 'Add a delete button for logged-in users to delete their own existing tasks.'
# Replace this with the exact directory printed by the command:
$run = 'F:\Projects\openspec-langchain-poc\runs\<printed-run-directory>'
Get-Content "$run\workspace\openspec\changes\add-task-deletion\proposal.md"
Get-Content "$run\workspace\openspec\changes\add-task-deletion\tasks.md"
.\.venv\Scripts\python.exe -m agent.cli apply --run $run --approve-plan
.\.venv\Scripts\python.exe -m agent.cli archive --run $run
.\scripts\start.ps1 -Run $run
```

Read all planning artifacts before approving. A hash prevents changed artifacts
from silently replacing the validated plan. Apply allows task checkbox updates
but not edits to task descriptions or frozen requirements/design.

## Repeatable test without a model

```powershell
.\.venv\Scripts\python.exe -m agent.cli demo --mode fixture --change fixture-deletion
```

This uses a scripted LangChain chat-model fixture, the real tool layer, the real
OpenSpec CLI, and real Django tests. It is **not evidence of model reasoning**.
It provides a reproducible infrastructure test with no model download or API call.

For a named, working reference application with deletion:

```powershell
.\.venv\Scripts\python.exe -m agent.cli demo --mode fixture --change reference-task-deletion
.\scripts\start.ps1 -Reference
```

The reference demonstrates the expected application and complete OpenSpec lifecycle.
It must not be confused with a successful live-model run.

## What to inspect

Each `runs/<id>/` contains:

- `workspace/`: an isolated runnable app, OpenSpec files, and a local baseline Git commit.
- `state.json` / `report.json` / `report.md`: outcome and model/mode information.
- `*-instructions.json`: actual OpenSpec JSON supplied to the agent.
- `*-messages.json`: model/tool conversations for completed stages.
- `codex-transport/`: raw CLI JSON events and usage per model request.
- `events.jsonl`: timestamped tool calls, writes, commands, outputs, and errors.
- `changes.diff`: source/spec diff against that run's baseline.
- `verification.json`: independent application checks and their complete output.
- `archived-spec-validation.json`: validation after merging the spec delta.

The fixed `task-deletion` acceptance profile checks the agreed deletion behavior.
For a different task use `--acceptance baseline` and supply additional acceptance
tests before treating it as verified against that new requirement. Baseline-only
checks cannot prove a new feature correct. A new run always starts from the root
baseline, not from a previous run's changed application.

## Scope and limitations

This is a local development POC with remote model inference. Codex manages your login;
the adapter never reads or copies authentication tokens. Account limits still apply.
`.env`, SQLite databases, generated runs, and local Django secrets are Git-ignored.
Commands are allowlisted and source paths are constrained, but generated Python
executes on the host: **a separate working copy is not an OS security sandbox**.
Use trusted local experiments. Strong isolation for untrusted tasks would require
a container/VM with its own filesystem, network, and resource restrictions.

The agent has bounded tool calls per process, model request timeouts, graph steps,
and a repair attempt. Failed runs remain inspectable. A failed apply can be retried
using the same `apply --approve-plan` command. Interrupted/failed planning can resume
with `python -m agent.cli resume-plan --run <run-directory>` using the project venv;
completed artifacts are preserved and the full plan is validated again.

To give planning feedback before implementation:

```powershell
.\.venv\Scripts\python.exe -m agent.cli revise-plan --run $run --artifact specs `
  --feedback 'Separate anonymous redirects, authenticated GET rejection, and missing IDs into distinct scenarios.'
.\.venv\Scripts\python.exe -m agent.cli resume-plan --run $run
```

Revisions invalidate the previous approval hash. Review dependent artifacts when
requirements change; the controller preserves existing artifacts rather than
silently rewriting them. The first live experiment required planning feedback;
the evidence records it explicitly.
