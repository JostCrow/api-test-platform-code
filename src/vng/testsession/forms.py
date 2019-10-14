from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import SessionType, Session
from ..utils.choices import AuthenticationChoices
from ..utils.forms import CustomModelChoiceField


class SessionTypeFormAdmin(forms.ModelForm):

    class Meta:
        model = SessionType
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['authentication'] == AuthenticationChoices.jwt:
            if not cleaned_data['client_id'] or not cleaned_data['secret']:
                raise forms.ValidationError(_('Client_id and secret must be provided with this authentication method'))
        elif cleaned_data['authentication'] == AuthenticationChoices.header:
            if not cleaned_data['header']:
                raise forms.ValidationError(_('Header must be provided with this authentication method'))
        return cleaned_data


class SessionForm(forms.ModelForm):

    session_type = CustomModelChoiceField(SessionType.objects.filter(active=True), widget=forms.RadioSelect, empty_label=None)

    class Meta:
        model = Session
        fields = ['session_type', 'sandbox']

    def __init__(self, *args, **kwargs):
        api_id = kwargs.pop('api_id', None)
        super().__init__(*args, **kwargs)
        if api_id:
            self.fields['session_type'] = CustomModelChoiceField(
                SessionType.objects.filter(active=True, api=api_id),
                widget=forms.RadioSelect,
                empty_label=None
            )
