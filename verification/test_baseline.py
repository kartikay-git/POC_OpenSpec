from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from todos.models import Task

class ProtectedBaselineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="DemoPass123!")
        cls.bob = get_user_model().objects.create_user("bob", password="DemoPass123!")
        cls.other = Task.objects.create(owner=cls.bob, title="Only Bob can see this")

    def test_login_logout_and_invalid_credentials(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.client.post(reverse("login"), {"username": "alice", "password": "wrong"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(reverse("login"), {"username": "alice", "password": "DemoPass123!"}), "/")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_creation_ownership_visibility_and_escaping(self):
        self.client.force_login(self.alice)
        self.client.post("/", {"title": "<script>test</script>", "owner": self.bob.pk})
        task = Task.objects.get(title="<script>test</script>")
        self.assertEqual(task.owner_id, self.alice.pk)
        response = self.client.get("/")
        self.assertContains(response, "&lt;script&gt;test&lt;/script&gt;")
        self.assertNotContains(response, self.other.title)

    def test_invalid_titles_and_csrf_rejected(self):
        self.client.force_login(self.alice)
        for title in [" ", "x" * 201]:
            self.client.post("/", {"title": title})
        self.assertEqual(Task.objects.count(), 1)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.alice)
        self.assertEqual(strict.post("/", {"title": "forged"}).status_code, 403)
