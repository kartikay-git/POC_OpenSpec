from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title"]
        widgets = {"title": forms.TextInput(attrs={"placeholder": "What needs to get done?", "autocomplete": "off"})}

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Please enter a task.")
        return title
