"""Deterministic tool-calling model fixture. This never claims to be a real LLM.

It exercises the same LangChain create_agent loop, tools, OpenSpec CLI, and
verification controller as live mode, using predefined outputs for one scenario.
"""
from typing import Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

PROPOSAL = """# Proposal

## Why
Users need to remove finished or unwanted tasks from their personal list.

## What Changes
- Add an authenticated delete action to each owned task.
- Reject cross-account, anonymous, non-POST, and CSRF-invalid deletion.
- Non-goals: bulk deletion, undo, registration, and schema changes.

## Capabilities
### New Capabilities
None.
### Modified Capabilities
- `tasks`: Add owner-only task deletion.

## Impact
Todo views, URLs, task template, and regression tests. No new dependencies.
"""

SPEC = """# Task deletion delta

## ADDED Requirements

### Requirement: Delete own tasks
The application SHALL let authenticated users delete only tasks they own using
a CSRF-protected POST form on their task list. Deletion SHALL persist after refresh.

#### Scenario: Owner deletes a task
- **WHEN** the owner submits its delete form with a valid CSRF token
- **THEN** the task is deleted and the refreshed task list no longer shows it

#### Scenario: Another user's task
- **WHEN** a user requests deletion of another account's task
- **THEN** a 404 response is returned and the task remains stored

#### Scenario: Anonymous deletion
- **WHEN** an unauthenticated visitor attempts deletion
- **THEN** they are redirected to login and the task remains stored

#### Scenario: Read-only request
- **WHEN** an authenticated user sends GET to a delete URL
- **THEN** a 405 response is returned and no task is deleted

#### Scenario: Missing CSRF token
- **WHEN** an authenticated user submits deletion without a valid CSRF token
- **THEN** a 403 response is returned and no task is deleted

#### Scenario: Missing task or repeated deletion
- **WHEN** an authenticated user submits deletion for a nonexistent task
- **THEN** a 404 response is returned
"""

DESIGN = """# Design

## Context
See proposal.md for motivation. The existing Django application uses session
authentication, CSRF middleware, and Task.owner. Deletion crosses authorization,
routing, and user interaction boundaries, so a design artifact is appropriate.

## Goals / Non-Goals
Reuse existing ownership and form patterns. No JavaScript, schema changes, or dependencies.

## Decisions
- POST /tasks/<int:pk>/delete/ named task-delete redirects to task-list after success.
- Use login_required, require_POST, and get_object_or_404(Task, pk=pk, owner=request.user).
  Filtering on owner prevents direct requests from deleting another account's task;
  UI hiding alone would not enforce authorization. 404 avoids revealing ownership.
- Reuse Django CSRF protection in a separate form on each task row. GET remains read-only.
- Delete immediately. Undo and confirmation dialogs are outside this small experiment.

## Risks / Trade-offs
Permanent deletion -> use disposable local demo data and explicit per-row action.

## Migration Plan
No database migration. Run regression/acceptance tests and reload the local app.
Rollback restores the baseline code; it does not recover already deleted tasks.
"""

TASKS = """# Tasks

## 1. Endpoint and authorization
- [ ] 1.1 Add the owner-filtered POST endpoint and tests; verify own deletion and rejection of other users, anonymous requests, GET, invalid CSRF, and missing IDs.

## 2. Task list action
- [ ] 2.1 Add a CSRF-protected delete form to each task row; verify the rendered form deletes a task and the refreshed list excludes it.

## 3. Integration
- [ ] 3.1 Run all application and protected acceptance checks; verify no login, creation, or list regressions and no missing migrations.

## Workflow follow-up
- Controller archives after independent verification and updates the established specification.
"""

VIEW_APPEND = '''

@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    task.delete()
    messages.success(request, "Task deleted.")
    return redirect("task-list")
'''

DELETE_FORM = '''<form method="post" action="{% url 'task-delete' task.pk %}">{% csrf_token %}<button class="danger" type="submit" aria-label="Delete {{ task.title }}">Delete</button></form>'''

APP_TEST = '''from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from .models import Task

class DeleteTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("owner", password="Example123!")
        self.other = get_user_model().objects.create_user("other", password="Example123!")
        self.task = Task.objects.create(owner=self.owner, title="Remove me")
        self.url = reverse("task-delete", args=[self.task.pk])

    def test_owner_deletes(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(self.url), "/")
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())

    def test_other_owner_rejected(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_anonymous_and_get_rejected(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_csrf_rejected(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.owner)
        self.assertEqual(strict.post(self.url).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
'''

class ScriptedToolModel(BaseChatModel):
    responses: list[AIMessage] = Field(default_factory=list)
    position: int = 0

    @property
    def _llm_type(self):
        return "deterministic-tool-fixture"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.position < len(self.responses):
            message = self.responses[self.position]
            self.position += 1
        else:
            message = AIMessage(content="Fixture exhausted.")
        return ChatResult(generations=[ChatGeneration(message=message)])

def fixture_model(run, stage):
    responses = []
    def call(name, **args):
        responses.append(AIMessage(content="", tool_calls=[{
            "name": name, "args": args, "id": f"fixture-{stage}-{len(responses)}", "type": "tool_call",
        }]))
    if stage.startswith("focused-"):
        target = run.state["implementation_target"]
        if target == "application/todos/views.py":
            content = run.read(target).replace("from django.shortcuts import redirect, render", "from django.shortcuts import get_object_or_404, redirect, render")
            content = content.replace("from django.views.decorators.http import require_http_methods", "from django.views.decorators.http import require_http_methods, require_POST") + VIEW_APPEND
        elif target == "application/todos/urls.py":
            content = run.read(target).replace('urlpatterns = [path("", views.task_list, name="task-list")]', 'urlpatterns = [path("", views.task_list, name="task-list"), path("tasks/<int:pk>/delete/", views.task_delete, name="task-delete")]')
        elif target == "application/templates/todos/task_list.html":
            content = run.read(target).replace("<!-- TASK_ACTIONS -->", DELETE_FORM)
        else:
            content = APP_TEST
        call("write_implementation", content=content)
        return ScriptedToolModel(responses=responses)
    call("list_files")
    call("openspec_instructions", artifact=stage)
    call("read_file", path="openspec/specs/tasks/spec.md")
    if stage != "apply":
        file, content = {"proposal": ("proposal.md", PROPOSAL), "specs": ("specs/tasks/spec.md", SPEC),
                         "design": ("design.md", DESIGN), "tasks": ("tasks.md", TASKS)}[stage]
        call("write_artifact", content=content, capability="tasks")
        call("openspec_status")
    else:
        call("read_file", path=run.change_prefix + "tasks.md")
        call("read_file", path="application/todos/views.py")
        views = run.read("application/todos/views.py")
        views = views.replace("from django.shortcuts import redirect, render", "from django.shortcuts import get_object_or_404, redirect, render")
        views = views.replace("from django.views.decorators.http import require_http_methods", "from django.views.decorators.http import require_http_methods, require_POST")
        call("write_file", path="application/todos/views.py", content=views + VIEW_APPEND)
        call("replace_text", path="application/todos/urls.py", old='urlpatterns = [path("", views.task_list, name="task-list")]',
             new='urlpatterns = [path("", views.task_list, name="task-list"), path("tasks/<int:pk>/delete/", views.task_delete, name="task-delete")]')
        call("replace_text", path="application/templates/todos/task_list.html", old="<!-- TASK_ACTIONS -->", new=DELETE_FORM)
        call("write_file", path="application/todos/test_deletion.py", content=APP_TEST)
        call("run_checks")
        call("write_file", path=run.change_prefix + "tasks.md", content=TASKS.replace("- [ ]", "- [x]"))
        call("git_diff")
    responses.append(AIMessage(content="Scripted fixture stage complete; independent controller checks determine success."))
    return ScriptedToolModel(responses=responses)
