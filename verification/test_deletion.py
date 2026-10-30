from html.parser import HTMLParser
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from todos.models import Task

class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {**attrs, "fields": {}}
            self.forms.append(self.current)
        elif tag == "input" and self.current is not None and "name" in attrs:
            self.current["fields"][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None

class DeletionAcceptanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="DemoPass123!")
        cls.bob = get_user_model().objects.create_user("bob", password="DemoPass123!")

    def setUp(self):
        self.own = Task.objects.create(owner=self.alice, title="Delete this task")
        self.other = Task.objects.create(owner=self.bob, title="Keep Bob task")
        self.url = f"/tasks/{self.own.pk}/delete/"
        self.client.force_login(self.alice)

    def test_owner_can_delete_and_refresh(self):
        self.assertRedirects(self.client.post(self.url), "/")
        self.assertFalse(Task.objects.filter(pk=self.own.pk).exists())
        self.assertNotContains(self.client.get("/"), self.own.title)
        self.assertTrue(Task.objects.filter(pk=self.other.pk).exists())

    def test_other_user_cannot_delete(self):
        response = self.client.post(f"/tasks/{self.other.pk}/delete/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.other.pk).exists())

    def test_anonymous_cannot_delete(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertTrue(Task.objects.filter(pk=self.own.pk).exists())

    def test_get_cannot_delete(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertTrue(Task.objects.filter(pk=self.own.pk).exists())

    def test_missing_and_duplicate_delete_return_404(self):
        self.assertEqual(self.client.post("/tasks/999999/delete/").status_code, 404)
        self.client.post(self.url)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_csrf_is_required(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.alice)
        self.assertEqual(strict.post(self.url).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=self.own.pk).exists())

    def test_real_html_form_with_csrf_deletes(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.alice)
        response = strict.get("/")
        forms = Forms(response.content.decode()).forms
        own_forms = [form for form in forms if form.get("action") == self.url]
        self.assertEqual(len(own_forms), 1, "Each task needs its own delete form")
        form = own_forms[0]
        self.assertEqual(form.get("method", "").lower(), "post")
        self.assertIn("csrfmiddlewaretoken", form["fields"])
        self.assertNotIn(f"/tasks/{self.other.pk}/delete/", response.content.decode())
        self.assertEqual(strict.post(form["action"], form["fields"]).status_code, 302)
        self.assertFalse(Task.objects.filter(pk=self.own.pk).exists())
