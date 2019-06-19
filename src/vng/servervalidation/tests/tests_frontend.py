import factory

from django_webtest import WebTest
from django.urls import reverse

from vng.testsession.tests.factories import UserFactory
from vng.servervalidation.models import ServerRun, PostmanTest, PostmanTestResult, User

from .factories import TestScenarioFactory, ServerRunFactory, TestScenarioUrlFactory, PostmanTestFactory
from ...utils import choices, forms


class TestMultipleEndpoint(WebTest):

    def setUp(self):
        self.user = UserFactory()
        self.ts = TestScenarioFactory()
        self.ts.authorization = choices.AuthenticationChoices.no_auth
        self.ts.save()
        TestScenarioUrlFactory(test_scenario=self.ts)
        TestScenarioUrlFactory(test_scenario=self.ts)

    def test_run_collection(self):
        call = self.app.get(reverse('server_run:server-run_create_item'), user=self.user)
        form = call.forms[0]
        form['test_scenario'] = self.ts.pk
        res = form.submit().follow()

        form = res.forms[0]
        for name, _ in form.field_order:
            if name is not None and 'test_scenario' in name:
                print(name)
                n = name
        form[n] = 'https://ref.tst.vng.cloud/drc/api/v1/'
        form['url'] = 'https://ref.tst.vng.cloud/drc/api/v1/'
        form.submit()


class TestCreation(WebTest):

    def setUp(self):
        self.tsf = TestScenarioUrlFactory()
        self.pt = PostmanTestFactory()
        self.user = UserFactory()
        self.server = ServerRunFactory()

        self.test_scenario = self.tsf.test_scenario
        self.server.test_scenario = self.test_scenario
        self.pt.test_scenario = self.test_scenario
        self.server.user = self.user

        self.pt.save()
        self.server.save()

    def test_creation_error_list(self):
        call = self.app.get(reverse('server_run:server-run_list'), user='test')
        assert 'Started' not in str(call.body)

        call = self.app.get(reverse('server_run:server-run_create_item'), user='test')
        form = call.forms[0]
        form['test_scenario'].force_value('9')
        form.submit()
        call = self.app.get(reverse('server_run:server-run_list'), user='test')
        assert 'Started' not in str(call.body)

    def test_scenarios(self):
        call = self.app.get(reverse('server_run:server-run_create_item'), user=self.user)
        form = call.forms[0]
        form['test_scenario'] = self.tsf.test_scenario.pk

        res = form.submit().follow()
        form = res.forms[0]
        form['url'] = 'https://ref.tst.vng.cloud/drc/api/v1/'
        form['Client ID'] = 'client id'
        form['Secret'] = 'secret'
        form.submit()
        call = self.app.get(reverse('server_run:server-run_list'), user=self.user)
        self.assertIn(self.user.username, call.text)
        server = ServerRun.objects.filter(status=choices.StatusChoices.stopped)[0]

        url = reverse('server_run:server-run_detail', kwargs={
            'pk': server.pk
        })
        call = self.app.get(url, user=self.user)

        ptr = PostmanTestResult.objects.get(postman_test__test_scenario=server.test_scenario)
        url = reverse('server_run:server-run_detail_log', kwargs={
            'uuid': ptr.server_run.uuid
        })
        call = self.app.get(url, user=self.user)

        ptr = PostmanTestResult.objects.get(postman_test__test_scenario=server.test_scenario)
        url = reverse('server_run:server-run_detail_log_json', kwargs={
            'uuid': ptr.server_run.uuid
        })
        call = self.app.get(url, user=self.user)

        ptr = PostmanTestResult.objects.get(postman_test__test_scenario=server.test_scenario)
        url = reverse('server_run:server-run_detail_pdf', kwargs={
            'uuid': server.uuid
        })
        call = self.app.get(url, user=self.user)

    def test_postman_outcome(self):
        server = ServerRun.objects.filter(user=self.user).order_by('-started')[0]
        url = reverse('server_run:server-run_detail', kwargs={
            'pk': server.pk
        })
        call = self.app.get(url, user=self.user)
        self.assertIn(str(server.pk), call.text)


class TestList(WebTest):

    def setUp(self):
        TestScenarioFactory()
        ServerRunFactory()

    def test_list(self):
        call = self.app.get(reverse('server_run:server-run_list'), user='test')
        assert 'no session' not in str(call.body)


class TestUserRegistration(WebTest):

    def add_dynamic_field(self, form, name, value):
        from webtest.forms import Text
        field = Text(form, 'input', name, None, value)
        field.id = name
        form.fields[name] = [field]

    def test_registration(self):

        # user registration
        call = self.app.get(reverse('registration_register'))
        form = call.forms[0]
        form['username'] = 'test'
        form['email'] = 'test.gmail.com'
        form['password1'] = 'asdgja3u8lksa'
        form['password2'] = 'asdgja3u8lksa'
        call = form.submit()

        # try to login before email confirmation
        call = self.app.get(reverse('auth_login'))
        form = call.forms[0]
        form['username'] = 'test'
        form['password'] = 'password'
        form.submit(expect_errors=True)

        User.objects.create_user(username='test', password='12345678a').save()
        call = self.app.get(reverse('auth_login'))
        form = call.forms[0]
        form['username'] = 'test'
        form['password'] = '12345678a'
        call = form.submit()
        self.assertIn(call.text, 'consumer')


class IntegrationTest(WebTest):

    def setUp(self):
        self.server = ServerRunFactory()
        self.test_scenario = TestScenarioUrlFactory().test_scenario
        PostmanTestFactory(test_scenario=self.test_scenario)
        self.server_s = ServerRunFactory(test_scenario=self.test_scenario, scheduled=True)
        self.user = self.server_s.user

    def test_access(self):
        call = self.app.get(reverse('server_run:server-run_detail_uuid', kwargs={
            'uuid': self.server.uuid
        }))
        self.assertIn(str(self.server.id), call.text)

    def test_trigger(self):
        prev = len(PostmanTestResult.objects.all())
        self.app.get(
            reverse('server_run:server-run_trigger', kwargs={
                'server_id': self.server_s.id
            }), user=self.server_s.user
        )
        self.assertEqual(prev, len(PostmanTestResult.objects.all()) - 1)

    def test_badge(self):
        call = self.app.get(reverse('server_run:server-run_create_item'), user=self.user)
        form = call.forms[0]
        form['test_scenario'] = self.server_s.test_scenario.pk
        res = form.submit().follow()
        form = res.forms[0]
        form['url'] = 'https://ref.tst.vng.cloud/drc/api/v1/'
        form['Client ID'] = 'client id'
        form['Secret'] = 'secret'
        form.submit()
        new_server = ServerRun.objects.latest('id')

        call = self.app.get(reverse('server_run:server-run_detail', kwargs={
            'pk': new_server.id
        }))
        self.assertIn(str(new_server.uuid), call.text)
        call = self.app.get(reverse('server_run:server-run_list'), user=self.user)
        ptr = PostmanTestResult.objects.all()[0]
        self.assertIn(str(ptr.get_assertions_details()[0]), call.text)

    def test_session_number_no_user(self):
        # simply check that with no user it raises no errors
        call = self.app.get(reverse('server_run:server-run_list'), status=[200, 302])

    def test_session_number_user(self):
        call = self.app.get(reverse('server_run:server-run_list'), user=self.user)
        self.assertIn(str(ServerRun.objects.filter(user=self.user, scheduled=True).count()), call.text)

    def test_information_form(self):
        self.test_badge()
        new_server = ServerRun.objects.latest('id')
        call = self.app.get(
            reverse(
                'server_run:server-run_detail_uuid',
                kwargs={'uuid': new_server.uuid}),
            user=self.user
        )
        form = call.forms[0]
        form['supplier_name'] = 'test_name'
        form['software_product'] = 'test_software'
        form['product_role'] = 'test_product'
        res = form.submit().follow()
        new_server = ServerRun.objects.latest('id')
        self.assertEqual(new_server.product_role, 'test_product')
