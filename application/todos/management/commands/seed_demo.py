from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from todos.models import Task

class Command(BaseCommand):
    help = "Create local-only alice/bob demo accounts without overwriting existing passwords."

    def handle(self, *args, **options):
        for username, title in [("alice", "Review the OpenSpec proposal"), ("bob", "Prepare tomorrow's notes")]:
            user, created = get_user_model().objects.get_or_create(username=username)
            if created:
                user.set_password("DemoPass123!")
                user.save()
            Task.objects.get_or_create(owner=user, title=title)
        self.stdout.write(self.style.SUCCESS("Demo users: alice / bob. Initial password: DemoPass123! (local only)."))
