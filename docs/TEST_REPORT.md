# Verification report

Date: 30 October 2026. User timezone: Asia/Calcutta. Run events use UTC.

## Final outcome

**The live GPT-6 Luna run completed planning, implementation, independent testing,
and OpenSpec archive successfully.**

Run: `runs/20261030T070131464642Z-codex-task-deletion`.
Final phase: `ARCHIVED`. Provider: `codex-cli`. Strategy: `focused`.
No manual edits to this run's planning artifacts or application source were made.
The controller's assigned four-file recipe and explicit acceptance contract guided
implementation; this is not a claim of unrestricted autonomous development.

## Environment and provider

- Python 3.13.9, Django 5.2.18, LangChain 1.4.7.
- OpenSpec 1.15.0, exact local npm dependency.
- Codex CLI 0.164.0-alpha.11.1, existing ChatGPT sign-in.
- GPT-6 Luna, high reasoning for successful planning and implementation.
- No API key copied into the project, no Ollama dependency, no new model download.

The adapter uses Codex structured responses to build LangChain tool calls. This is
custom tool emulation, not native OpenAI API function calling. LangChain executes
all project reads/writes. The 18 recorded CLI requests contain zero native command,
file-change, MCP, web-search, or collaboration action events.

Reported CLI usage across this run, including the first failed planning attempt:
387,327 input tokens, of which 126,080 were reported cached; 10,537 output tokens,
including 3,699 reported reasoning-output tokens. These are CLI usage counters,
not a monetary billing calculation. Each decision starts a new process and sends
conversation context again; this POC has transport overhead and uses account limits.

## Live run sequence and repair

1. The initial low-effort proposal request stopped without calling a write tool.
   The controller rejected it. Its transcript remains as an earlier attempt.
2. The adapter protocol was clarified and reasoning changed to high. `resume-plan`
   generated proposal, task spec delta, design, and checklist through LangChain tools.
3. Strict OpenSpec change validation passed. The plan was reviewed against the
   explicit acceptance contract; no artifact corrections were needed. Its hash
   was frozen and approved for the already-authorized implementation.
4. Luna wrote the view, URL configuration, task template, and seven regression tests.
5. Initial verification found one incorrect generated test: it expected only two
   CSRF tokens across a page that also has create and logout forms. The actual
   count was four. Protected acceptance checks were not changed.
6. The bounded model repair pass changed the test to inspect deletion forms.
   All application and protected tests then passed. The approved plan hash stayed
   unchanged. The controller marked tasks complete only after those results.
7. Archive reran checks, synchronized the spec delta, moved the change into
   `workspace/openspec/changes/archive/2026-10-30-codex-task-deletion`, and strict
   validation of the updated baseline specs passed.

The original failure and repair are in events.jsonl and focused stage transcripts.
The final verification.json holds the checks rerun immediately before archive.

## Automated results

| Check | Result |
|---|---|
| Controller/adapter pytest suite | **35 passed in 74.35 seconds** |
| Root baseline Django suite | **8 passed** |
| Root Django system check and migration consistency | Passed |
| Root authentication/tasks OpenSpec specs | Both strict-valid |
| Generated application's Django suite | **15 passed** (8 baseline + 7 generated) |
| Protected baseline behavior suite | **3 passed** |
| Protected deletion acceptance suite | **7 passed** |
| Generated app system/migration checks | Passed |
| Live change validation and post-archive spec validation | Passed |

Full root-suite output: `automated-test-output.txt`.
Live checks: `runs/20261030T070131464642Z-codex-task-deletion/verification.json`.

The pytest suite covers path escape/secret rejection, stage write restrictions,
artifact path resolution, plan approval/fingerprint protection, syntax rejection,
repeated-error limits, guarded task completion, real OpenSpec rejection of invalid
specs, fixture application/archival, focused execution, and Codex transport decisions.
The Codex adapter tests mock network transport; the recorded live run is the separate
functional evidence for real model access. OpenSpec integration tests use the real CLI.

## Protected deletion contract

| Case | Expected and observed |
|---|---|
| Owner deletes and refreshes | Task absent from database/list; other owner's task preserved |
| Other owner targets task | 404, task preserved |
| Anonymous deletion in auth test | Login redirect, task preserved |
| Authenticated GET | 405, task preserved |
| Missing/repeated task ID | 404 |
| Missing/invalid CSRF token | 403, task preserved |
| Submit rendered form with valid CSRF | POST owner deletion succeeds |

Authentication tests use Django's default test client. In a real request with
missing CSRF, middleware may reject the POST before the view's login decorator;
this is not a bypass. CSRF-specific tests explicitly enforce middleware checks.
Three additional protected tests cover existing auth/create/list behavior. These
files are outside the agent's normal file-tool scope. Running generated Python on
the host is not an operating-system sandbox against hostile code.

## Browser verification

The live generated app was started with `scripts/start.ps1 -Latest`:

- Alice signed in and saw her seeded task with a labeled delete button.
- A disposable task was created through the UI, deleted using its button, and
  remained absent after refreshing the page.
- Alice signed out. Bob signed in and saw only his own seeded task.
- The page rendered correctly in the in-app browser.

Screenshots: `codex-before-delete.png`, `codex-after-delete.png`,
`codex-bob-isolation.png`. The test preview server was stopped after verification.
Run `scripts/start.ps1 -Latest` to open it again.

## Historical Ollama results (not successful live runs)

The initial CPU run `20261030T054938521532Z-add-task-deletion` required recorded
reviewer corrections to planning and failed implementation with Qwen/Mistral.
The GPU run `20261030T063445625743Z-gpu-task-deletion` also required plan corrections
and failed implementation checks despite GPU acceleration. Neither was verified
or archived. The retained state, transcripts, and before-reviewer-corrections
folders make those limitations inspectable.

The approved GPU setup detected RTX 4060 Laptop hardware with 8,188 MiB VRAM and
verified Qwen at 100% GPU. It improved execution speed but did not fix code quality.
Ollama packages/settings have since been removed from this project. Existing Docker
containers and their model volume remain preserved; see GPU_SETUP.md for details.

The named reference fixture `20261030T065104528790Z-reference-task-deletion` also
completed/archive successfully. Its code was predetermined fixture data, so it
is infrastructure evidence, not a live-model success. The Codex run above is the
successful real-model result.

## Reproduce

```powershell
.\scripts\test.ps1
.\.venv\Scripts\python.exe -m agent.cli demo --mode live --change repeat-codex-deletion
.\scripts\start.ps1 -Latest
```

Each run starts from the same root baseline. Another model run may differ or fail.
This validates one guided feature workflow. It does not establish reliability on
arbitrary requirements or a measured improvement over an agent without OpenSpec.
