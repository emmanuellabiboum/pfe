from django import forms
from core.models import Agence


class AgenceForm(forms.Form):
    agence = forms.ModelChoiceField(queryset=Agence.objects.all(), label="Agence")
