# Implementation walkthrough

This guide follows the project from installation to an archived, tested feature.
All shell examples use PowerShell from `F:\Projects\openspec-langchain-poc`.
They are commands for you to reproduce; the actual run transcripts are under `runs/`.

## 1. Understand the two processes

The Django application serves the login screen and each user's task list. It
does not call an LLM when someone creates or deletes a task.

The separate development agent receives a requirement from you. LangChain runs
the model/tool loop. OpenSpec provides the structured planning instructions.
Our Python controller creates the working copy, limits writable paths, validates
artifacts, runs independent checks, and manages the change lifecycle.

The project layout is:

```text
application/       Django baseline: config, todos, templates, static, migrations
agent/cli.py       Requirement input and plan/apply/archive commands
agent/workflow.py  OpenSpec stages, LangChain loop, verification lifecycle
agent/codex_model.py  Signed-in Codex CLI model adapter
agent/tools.py     LangChain read/write/OpenSpec/test tools
agent/runtime.py   Working copies, path guards, fixed commands, hashes, logs
agent/fixture.py   Predetermined test model (not a real LLM)
openspec/          Baseline specs, project context, per-artifact rules
verification/     Controller-owned behavior and deletion acceptance tests
tests/            Workflow, guard, and adapter tests
scripts/          Setup, test, and preview PowerShell entry points
runs/             Separate source/spec copy and evidence for every experiment
docs/             This walkthrough, command journal, results, screenshots
```

The successful live result is in
`runs/20261030T070131464642Z-codex-task-deletion`; use `scripts/start.ps1 -Latest`
to run it. The root `application/` remains the repeatable pre-change baseline.

```text
Your requirement
  -> agent.cli
  -> isolated workspace + OpenSpec change
  -> OpenSpec instructions JSON
  -> LangChain create_agent -> CodexChatModel -> signed-in Codex CLI -> GPT-6 Luna
  -> tool calls -> planning artifacts / application edits
  -> OpenSpec validation + independent Django checks
  -> diff / evidence / updated specs / archive
```

OpenSpec does not generate code itself. The model writes the proposal, spec,
design, tasks, and implementation. LangChain does not automatically understand
OpenSpec: `agent/workflow.py` explicitly obtains and supplies its instructions.

## 2. Install dependencies reproducibly

Prerequisites already available on this machine were Python 3.13.9, Node 24.20.0,
npm 11.19.0, Git 2.55.0, and uv 0.11.33. The project supports Python 3.11+ and
Node 20.19+; the locked packages were tested with the versions above.

The initial setup used:

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

`uv venv` creates a private Python interpreter environment. `uv lock` resolves
the version constraints in `pyproject.toml` into `uv.lock`. `uv sync --locked`
installs those exact versions without changing the lock. A project-local uv cache
avoids the restricted system cache encountered during initial setup.

The npm command installed OpenSpec **1.15.0** and wrote an exact package version
and `package-lock.json`. Future installations use `npm.cmd ci`, not a floating
latest package. `--tools none` initializes OpenSpec without installing slash-command
integrations for other coding assistants. This POC calls the CLI directly.

The main Python packages are:

| Package | Installed version | Why it exists |
|---|---|---|
| Django | 5.2.18 | Authentication, sessions, forms, database, templates, test client |
| langchain | 1.4.7 | `create_agent` and registered tool execution |
| Codex CLI | 0.164.0-alpha.11.1 (installed desktop CLI) | Signed-in GPT-6 Luna transport |
| python-dotenv | 1.2.4 | Load local `.env` settings |
| pytest | 9.2.0 | Test the controller and OpenSpec integration |

LangGraph, langchain-core, and other transitive packages
are installed automatically and pinned by `uv.lock`. No separate installation
of a read-file or write-file package is needed: these are project-owned tools
built with Python's standard library and LangChain's `@tool` decorator.

To recreate the setup now:

```powershell
.\scripts\setup.ps1
```

This synchronizes Python packages, runs `npm ci`, creates `.env` from the example
only if it is missing, migrates the baseline database, and seeds demo accounts.
It preserves an existing `.env` and existing account passwords. It does not
rerun OpenSpec initialization over the project's configured specifications.

For machines without uv, the script uses:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
```

`requirements.lock` is a hashed pip-compatible export of the same dependency lock.
Virtual-environment activation is optional: every documented command uses its
interpreter explicitly. No global execution-policy change is required.

## 3. Use the signed-in Codex CLI

The installed desktop CLI was detected on PATH. `codex login status` reported
"Logged in using ChatGPT". A live `gpt-6-luna` probe succeeded. No credential was
copied out of Codex and no API key was added to this project.

On a machine without the CLI, install the official CLI and sign in interactively:

```powershell
npm.cmd install -g @openai/codex
codex login
codex --version
codex login status
```

The global installation is a reproduction option, not a command used to replace
this machine's existing desktop CLI. The adapter uses current CLI options such as
`--ignore-user-config`; older CLI versions may require an update.

The active `.env` is:

```dotenv
CODEX_MODEL=gpt-6-luna
CODEX_REASONING_EFFORT=high
CODEX_TIMEOUT=600
AGENT_RECURSION_LIMIT=80
AGENT_MAX_TOOL_CALLS=100
```

`CODEX_EXECUTABLE` may contain a full executable path if Codex is not on PATH.
`high` increases reasoning on the same small model; it does not select a larger
model. A first low-effort planning request stopped without writing and remains
recorded in the run. The adapter fails on missing writes rather than assuming success.

```powershell
.\.venv\Scripts\python.exe -m agent.cli doctor
```

Doctor checks dependencies and login, not model correctness. Real planning and
application checks are the functional test. Remote requests use your Codex account
limits and send the supplied project context to OpenAI. No local GPU is used.

### What the custom LangChain model does

`agent/codex_model.py` implements LangChain's `BaseChatModel` interface:

1. `bind_tools` receives the stage's real LangChain tools and exposes their schemas.
2. `_generate` serializes the conversation and tool descriptions into a prompt.
3. It invokes `codex exec` in an empty temporary directory, with read-only sandbox,
   personal config ignored, shell/apps/plugins/browser/multi-agent/hooks disabled,
   and `--output-schema` requiring `{tool, arguments_json, final}`.
4. Codex generates one structured decision. It does not execute the project tools.
5. The adapter validates the selected tool and its arguments and builds an
   `AIMessage(tool_calls=...)`. LangChain then runs the actual Python tool.
6. The tool result is included in the next request. A dedicated artifact/file
   write ends its stage through LangChain's `return_direct` behavior.

This is **structured-output tool emulation through an official CLI**, not a
first-party ChatOpenAI provider or native API function calling. The distinction
is recorded in response metadata and raw transport logs. It preserves a real
LangChain execution loop without requiring a separate API key. Each decision
starts a fresh ephemeral CLI invocation, so there is process/context overhead.

CLI events are saved in each run's `codex-transport/`. Native command/file/MCP
activity causes the adapter to reject the response, since that would violate
its role in this experiment. These checks and read-only CLI settings do not make
the separate Python application-test process an OS sandbox.

The old Ollama dependency and `.env` settings were removed with `uv lock` and
`uv sync --locked`. Existing Docker models/containers were preserved; their
historical setup and unsuccessful runs remain in GPU_SETUP.md and OLLAMA_HISTORY.md.

## 4. Build and establish the baseline application

The baseline is intentionally small:

- Django's built-in session login and POST logout.
- `Task(owner, title, created_at)` stored in SQLite.
- A form accepts nonblank titles up to 200 characters.
- Creation always assigns `request.user`, ignoring submitted ownership data.
- Listing filters by the authenticated owner and escapes title HTML.
- Django middleware enforces CSRF on state-changing requests.
- Responsive server-rendered templates and one local CSS file.

Accounts are created by a management command so signup, email verification, and
password reset do not distract from the experiment.

```powershell
.\.venv\Scripts\python.exe application\manage.py migrate --noinput
.\.venv\Scripts\python.exe application\manage.py seed_demo
.\.venv\Scripts\python.exe application\manage.py test todos --verbosity 2
.\.venv\Scripts\python.exe application\manage.py runserver 127.0.0.1:8000 --noreload
```

`migrate` creates the auth/session/task tables. `seed_demo` creates Alice and Bob,
each with their own task. Their initial local-demo password is `DemoPass123!`.
The root baseline never receives the deletion implementation. Each experiment
starts from this repeatable point and produces a separate runnable application.

## 5. Describe baseline behavior with OpenSpec

`openspec/specs/authentication/spec.md` describes login/logout and protected access.
`openspec/specs/tasks/spec.md` describes task creation and isolation.
`openspec/config.yaml` adds project context and per-artifact rules such as ownership,
CSRF, and the requirement to verify tasks. These files are hand-established ground
truth for the first experiment, not model-generated evidence.

```powershell
$env:OPENSPEC_TELEMETRY = '0'
.\node_modules\.bin\openspec.cmd validate --specs --strict --json --no-interactive
```

Strict validation checks the real OpenSpec document structure. It does not run
the app or prove that the app conforms to those documents.

## 6. Accept a requirement and create a working copy

```powershell
.\.venv\Scripts\python.exe -m agent.cli plan --mode live --change add-task-deletion `
  --requirement 'Add a delete button for logged-in users to delete their own existing tasks.'
```

`Run.create` validates the change name, creates a timestamped directory under
`runs/`, copies application source and baseline specifications, and omits databases,
secrets, caches, dependencies, and `.env`. It creates a local Git baseline inside
that copy. Dependency executables remain shared with the parent project.

The controller invokes:

```text
git init --quiet
git add application openspec .gitignore
git -c user.name="POC Baseline" -c user.email=poc@localhost commit --quiet -m "Baseline before agent change"
openspec new change add-task-deletion
```

These commands run inside the isolated working copy. The Git author configuration
is command-local and does not change your global Git settings. No remote is added
and nothing is pushed. The CLI is actually executed as `node <absolute-local-openspec.js>`
to avoid Windows `.cmd` shell quoting and global PATH ambiguity.

## 7. Let the model plan using actual OpenSpec instructions

The controller requests artifact status, then instructions for each ready stage:

```text
openspec status --change add-task-deletion --json
openspec instructions proposal --change add-task-deletion --json
openspec instructions specs --change add-task-deletion --json
openspec instructions design --change add-task-deletion --json
openspec instructions tasks --change add-task-deletion --json
```

The dependency sequence used here is proposal, specs, design, tasks. OpenSpec
itself permits specs/design after proposal; our controller chooses a simple
sequential order for an inspectable POC. Every stage receives the user requirement,
the selected acceptance contract, and the real JSON instructions, including
project context, templates, rules, and dependency paths.

`create_agent` connects `CodexChatModel` and the tool list. The model selects tools,
LangChain executes them, tool results return to the model, and the loop continues.
Each planning stage has its own short conversation. Files preserve cross-stage
context, and instructions identify dependencies to read.

The outputs answer:

| Artifact | Question |
|---|---|
| proposal.md | Why is this change needed and what is in scope? |
| specs/tasks/spec.md | What observable behavior must change? |
| design.md | How should authorization, routing, and UI work? |
| tasks.md | What implementation steps and verification are required? |

Only the current planning artifact is writable at this stage. Application edits
are rejected by Python code even if the model asks to make them.

After generation the controller runs:

```text
openspec validate add-task-deletion --type change --strict --json --no-interactive
```

A malformed specification gets one bounded repair attempt. A valid plan must also
contain unfinished checkbox tasks. The controller saves a SHA-256 fingerprint of
the planning artifacts and moves to `PLAN_READY`.

## 8. Understand every agent tool

The implementation is in `agent/tools.py`; filesystem and command enforcement
is in `agent/runtime.py`. Function type annotations become the JSON input schema,
and docstrings explain each tool to the model. The model supplies arguments;
Python executes the actual operation. The tool wrapper records calls and results.

| Tool | Inputs | Operation / restriction |
|---|---|---|
| list_files | none | Enumerate accessible application/OpenSpec text files |
| read_file | path | Read UTF-8 text, maximum 100 KB |
| write_artifact | content, capability | Planning only: resolve the current OpenSpec artifact path and write Markdown |
| write_implementation | content | Focused apply only: save the current assigned source file and end that stage |
| write_file | path, content | Apply only: write complete text within allowed application paths |
| replace_text | path, old, new | Require exactly one match; use the same write enforcement |
| openspec_status | none | Return real JSON status for the current change |
| openspec_instructions | artifact | Fetch proposal/specs/design/tasks/apply instructions |
| validate_specs | none | Run strict validation of the current change |
| run_checks | none | Run fixed Django and protected acceptance commands during apply |
| mark_tasks_complete | none | After passing checks, update checkbox markers without rewriting task text |
| git_diff | none | Show source/spec edits against the copy's baseline, including new files |

Paths must be repository-relative with forward slashes. Absolute paths, traversal,
Windows alternate streams, database files, `.env`, local secrets, and paths that
resolve outside the copy are rejected. Only allowed text suffixes are readable.
During apply the agent may edit todo code, templates, static files, and task
checkboxes. It cannot use these tools to edit application settings, controller
code, established specs, or the external acceptance suite.

Planning uses `write_artifact` rather than exposing `write_file`: OpenSpec's
`outputPath` is relative to a change folder, whereas application paths are relative
to the repository. The first live run exposed that ambiguity when the model sent
`specs/tasks/spec.md` to the general file tool. The guard rejected it. The dedicated
artifact tool resolves the path in Python, removing that ambiguity from the model.
A regression test exercises this exact case, including a traversal attempt.
The artifact tool uses LangChain's `return_direct` behavior: a successful artifact
write ends that planning-stage agent invocation immediately. This prevents a model
from wandering into the next artifact while the controller still permits only the
current one. Three identical consecutive tool errors also stop a run with evidence.

If planning is interrupted, resume it with:

```powershell
.\.venv\Scripts\python.exe -m agent.cli resume-plan --run $run
```

The controller preserves completed artifacts, records the resumption, and validates
the full plan before approval. It also supplies a small selection of real baseline
spec/code content directly to planning prompts, so project facts do not depend
entirely on the model choosing to read them with tools.

`revise-plan --run $run --artifact specs --feedback 'concrete review feedback'`
lets you request a model-authored correction. The feedback is saved in the event
log and the prior plan fingerprint is invalidated. Run `resume-plan` afterward
to validate again; inspect/revise dependent artifacts if the requirement changed.
This is explicit reviewer guidance, not autonomous agent success.

There is no model-accessible unrestricted shell or arbitrary Python tool. Test
commands use argument arrays with `shell=False`, timeouts, and an environment
that removes common credential variable names. This reduces accidental exposure;
it does not make generated Python safe against deliberately malicious execution.

## 9. Approve and implement

After reviewing the artifacts, use the printed run directory:

```powershell
$run = 'F:\Projects\openspec-langchain-poc\runs\<printed-run-directory>'
.\.venv\Scripts\python.exe -m agent.cli apply --run $run --approve-plan
```

The controller requires `PLAN_READY` or `FAILED_APPLY`, an approval flag, and an
unchanged plan fingerprint. It records the approved hash before enabling writes.
It then requests `openspec instructions apply --change add-task-deletion --json`.

For the deletion experiment, the acceptance profile fixes the expected route and
behavior so the test is unambiguous: POST `/tasks/<id>/delete/`, own task only,
login required, valid CSRF required, redirect to `/`, and 404 for missing/other-owner
tasks. These are explicit POC decisions supplied to the model, not conclusions
that the model is expected to infer from a one-line requirement.

The model must implement the endpoint, route, per-row form, and regression tests.
It can use test output to repair failures. Task descriptions cannot change during
apply; only checkbox markers can. A final response saying “done” is insufficient.
The `mark_tasks_complete` tool avoids requiring a small model to rewrite an entire
checklist just to change its markers. It refuses to run before passing test evidence
exists; independent final verification still checks the current application.

`demo --mode live` deliberately combines plan, approval for this local experiment,
apply, verification, and archive. Use the separate commands for an actual review gate.

### Broad loop versus focused execution

The POC retains two application strategies. `apply --strategy loop` lets the model
choose tools across the entire feature. In the first live Qwen attempt it read
files, then returned code blocks in chat instead of invoking writes. The protected
tests failed, so the controller refused to mark that run verified. A subsequent
focused Qwen attempt returned an empty response and was also rejected.

The default for a live `task-deletion` profile is now `focused`. The controller
selects the view, URLs, task-list template, and regression test file in sequence.
For each it provides the approved OpenSpec context, the current source, and a
specific file task. The model generates the complete file and saves it through
`write_implementation`. That tool ends the stage and cannot choose a different
path. The controller checks that a successful write actually happened.

This is a deliberately specialized small-model recipe. The model still generates
the code; the controller supplies the decomposition and some implementation
guidance. It is not evidence that the model independently discovered the file plan.
After all four writes, the controller runs independent checks, allows one bounded
repair pass on failure, and marks task checkboxes only after those checks pass.
The generic baseline acceptance profile continues to use the broader tool loop.
The scripted test model can exercise both strategies without any remote model calls.

## 10. Verify with three different kinds of evidence

1. **OpenSpec validation**: Is the specification structurally valid?
2. **Agent/controller integration tests**: Are the workflow, tools, restrictions,
   failure paths, plan approval, and real CLI interaction functioning?
3. **Application tests**: Does the changed application satisfy the behavior?

During and after apply the application commands are:

```text
python <workspace>/application/manage.py check
python <workspace>/application/manage.py makemigrations --check --dry-run
python <workspace>/application/manage.py test todos --verbosity 2
python <workspace>/application/manage.py test verification.test_baseline --verbosity 2
python <workspace>/application/manage.py test verification.test_deletion --verbosity 2
```

The first test suite lives in the working application; the last two live in the
controller repository and are made importable with `PYTHONPATH`. They preserve
baseline functionality and independently check deletion. The deletion tests cover
owner success, refresh/persistence, other-user rejection, anonymous rejection,
GET rejection, missing/repeated IDs, CSRF rejection, and submitting the actual
rendered HTML form with a valid CSRF token.

The controller independently reruns verification after the model stops. It permits
one additional model repair stage for failed implementation tests. Only passing
checks, an unchanged plan, completed tasks, and valid specs yield `VERIFIED`.
The protected tests are outside the agent's file-tool scope, but host execution is
not a hostile-code sandbox. The tests are evidence for this trusted local POC.

The standalone pytest suite runs without a model service. Its scripted model emits fixed
LangChain tool calls and exercises real filesystem edits, CLI validation, Django
checks, and archive. Fixture results are explicitly labeled and kept distinct
from the live model's behavior.

## 11. Archive and inspect the resulting application

```powershell
.\.venv\Scripts\python.exe -m agent.cli archive --run $run
.\scripts\start.ps1 -Run $run
```

Archive requires `VERIFIED`, checks that the plan did not change, and rechecks the
current application. The controller executes:

```text
openspec archive add-task-deletion --yes
openspec validate --specs --strict --json --no-interactive
```

OpenSpec merges the delta into the working copy's established specification and
moves the change into the archive. The root baseline remains unchanged.
`start.ps1` migrates and seeds a fresh local database for the selected application
and serves it on loopback. `start.ps1 -Latest` selects the newest verified live run.

## 12. Read the evidence and interpret the POC

The CLI prints the run directory immediately. `events.jsonl` contains UTC timestamps,
exact commands, exit statuses, stdout/stderr, tool inputs/results, and file diffs.
Each completed model stage also has a full message transcript and a snapshot of
the OpenSpec instructions the controller supplied. `verification.json` preserves
test output; `report.json` identifies the mode/model/provider and outcome.
`codex-transport/` records CLI JSON events, token usage, and stderr for each request.

You can correlate requirement -> spec scenario -> task -> source edit -> test
result without relying on the agent's final prose. `changes.diff` is reviewable
with Git or a text editor. The baseline Git commit exists in each working copy;
there is no automated merge into your other projects.

A passing live run demonstrates this integration works for this model and feature.
It does not prove general autonomous-development reliability or that OpenSpec is
better than an unconstrained agent. For that, repeat several tasks from identical
baselines and compare acceptance results, manual interventions, tool counts,
latency, and token use. The current repository provides the evidence structure
for that experiment; it does not claim a completed comparative study.

## References

- [OpenSpec CLI](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md)
- [OpenSpec workflows](https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md)
- [Codex models](https://learn.chatgpt.com/docs/models)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)
- [Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/)

The installed OpenSpec 1.15.0 CLI and schema files are the implementation source
of truth for this checkout; upstream documentation may change after this build.
