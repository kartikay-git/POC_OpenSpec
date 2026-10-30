from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .forms import TaskForm
from .models import Task

@login_required
@require_http_methods(["GET", "POST"])
def task_list(request):
    form = TaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        messages.success(request, "Task added.")
        return redirect("task-list")
    return render(request, "todos/task_list.html", {
        "form": form, "tasks": Task.objects.filter(owner=request.user),
    })
