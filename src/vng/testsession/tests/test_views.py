import collections
import json

from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext

from django_webtest import WebTest

from vng.accounts.models import User

from ..models import Session, SessionType
from .factories import SessionFactory, SessionTypeFactory, UserFactory, ScenarioCaseFactory, ScenarioFactory
from ...utils import choices


def get_object(r):
    return json.loads(r.decode('utf-8'))


class RetrieveSessionType(WebTest):

    def setUp(self):
        SessionTypeFactory()

    def test_retrieve_single_session_types(self):
        call = self.app.get('/api/v1/sessiontypes/', user='admin')
        t = get_object(call.body)
        self.assertTrue(t[0]['id'] > 0)

    def test_retrieve_multiple_session_types(self):
        SessionTypeFactory.create_batch(size=10)
        call = self.app.get('/api/v1/sessiontypes/', user='admin')
        t = json.loads(call.text)
        self.assertTrue(t[9]['id'] > 0)


class AuthorizationTests(WebTest):

    def setUp(self):
        UserFactory()

    def test_check_unauthenticated_testsessions(self):
        self.app.get('/session/v1/testsessions/', expect_errors=True)

    def test_right_login(self):
        call = self.app.post('/api/auth/login/', params=collections.OrderedDict([
            ('username', 'test'),
            ('password', 'pippopippo')]))
        self.assertIsNotNone(call.json.get('key'))

    def test_wrong_login(self):
        call = self.app.post(reverse('apiv1_auth:rest_login'), {
            'username': 'test',
            'password': 'wrong'
        }, status=400)

        self.assertEqual(call.json, {"non_field_errors": [gettext("Unable to log in with provided credentials.")]})

    def test_session_creation_authentication(self):
        Session.objects.all().delete()
        session = {
            'session_type': 1,
            'started': str(timezone.now()),
            'status': choices.StatusChoices.running,
            'api_endpoint': 'http://google.com',
        }
        call = self.app.post('/api/v1/testsessions/', session, status=401)


class CreationAndDeletion(WebTest):

    def setUp(self):
        self.session_type = SessionTypeFactory()
        self.user = UserFactory()

    def test_session_creation(self):
        session = {
            'session_type': self.session_type.id,
            'started': str(timezone.now()),
            'status': choices.StatusChoices.running,
            'api_endpoint': 'http://google.com'
        }
        call = self.app.post('/api/auth/login/', params=collections.OrderedDict([
            ('username', 'test'),
            ('password', 'pippopippo')]))
        key = get_object(call.body)['key']
        head = {'Authorization': 'Token {}'.format(key)}
        call = self.app.post(reverse('apiv1:test_session_list'), session, headers=head)

    def test_session_creation_permission(self):
        Session.objects.all().delete()
        session = {
            'session_type': self.session_type.id,
            'started': str(timezone.now()),
            'status': choices.StatusChoices.running,
            'api_endpoint': 'http://google.com',
            'user': self.user.id,
        }

        call = self.app.post('/api/auth/login/', params=collections.OrderedDict([
            ('username', 'test'),
            ('password', 'pippopippo')]))
        key = get_object(call.body)['key']
        head = {'Authorization': 'Token {}'.format(key)}
        call = self.app.post(reverse('apiv1:test_session_list'), session, headers=head)
        response_parsed = get_object(call.body)
        session = Session.objects.filter(pk=response_parsed['id'])[0]
        user = User.objects.all()[0]
        self.assertEqual(session.user.pk, user.pk)


class TestLog(WebTest):

    def setUp(self):
        self.scenarioCase = ScenarioCaseFactory()
        self.session = SessionFactory()
        self.scenarioCase.scenario = self.session.scenario

    def test_retrieve_no_logged(self):
        call = self.app.get(reverse('testsession:session_log', kwargs={'session_id': self.session.id}), status=302)

    def test_retrieve_no_entry(self):
        call = self.app.get(reverse('testsession:session_log', kwargs={'session_id': self.session.id}), user=self.session.user)
        self.assertTrue('no log' in call.text)

    def test_retrieve_no_entry(self):
        url = reverse('testsession:run_test', kwargs={
            'url': self.session.exposed_api,
            'relative_url': self.scenarioCase.url
        })
        call = self.app.get(url, user=self.session.user)
        call2 = self.app.get(reverse('testsession:session_log', kwargs={'session_id': self.session.id}), user=self.session.user)
        self.assertTrue(url in call2.text)

    def test_log_report(self):
        self.test_retrieve_no_entry()
        call = self.app.get(reverse('testsession:session_report', kwargs={'session_id': self.session.id}), user=self.session.user)
        self.assertEqual(self.scenarioCase.scenario.id, self.session.scenario.id)

    def test_log_report_pdf(self):
        self.test_retrieve_no_entry()
        call = self.app.get(reverse('testsession:session_report-pdf', kwargs={'session_id': self.session.id}), user=self.session.user)