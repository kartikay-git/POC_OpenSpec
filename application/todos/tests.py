from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from .models import Task

class BaselineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="DemoPass123!")
        cls.bob = get_user_model().objects.create_user("bob", password="DemoPass123!")
        cls.task = Task.objects.create(owner=cls.bob, title="Private Bob task")

    def test_anonymous_redirected(self):
        self.assertRedirects(self.client.get("/"), "/accounts/login/?next=/")

    def test_login_and_logout(self):
        response = self.client.post(reverse("login"), {"username": "alice", "password": "DemoPass123!"})
        self.assertRedirects(response, "/")
        self.assertContains(self.client.get("/"), "Hello, alice")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"))

    def test_invalid_login(self):
        response = self.client.post(reverse("login"), {"username": "alice", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_only_own_tasks_visible(self):
        self.client.force_login(self.alice)
        self.assertNotContains(self.client.get("/"), "Private Bob task")

    def test_create_uses_session_owner(self):
        self.client.force_login(self.alice)
        self.assertRedirects(self.client.post("/", {"title": "My new task", "owner": self.bob.pk}), "/")
        self.assertEqual(Task.objects.get(title="My new task").owner_id, self.alice.pk)

    def test_blank_and_long_titles_rejected(self):
        self.client.force_login(self.alice)
        for title in ["   ", "a" * 201]:
            self.client.post("/", {"title": title})
        self.assertEqual(Task.objects.count(), 1)

    def test_csrf_required_for_create(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice)
        self.assertEqual(client.post("/", {"title": "No token"}).status_code, 403)

    def test_title_is_escaped(self):
        Task.objects.create(owner=self.alice, title="<script>alert(1)</script>")
        self.client.force_login(self.alice)
        response = self.client.get("/")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
