import factory
from factory.django import DjangoModelFactory as Dmf

from filer.models import File

from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings

from vng.accounts.models import User
from vng.testsession.tests.factories import UserFactory

from ..models import ServerRun, TestScenario, TestScenarioUrl, PostmanTest, PostmanTestResult, Endpoint
from ...utils.factories import UserFactory


class TestScenarioFactory(Dmf):

    class Meta:
        model = TestScenario

    name = factory.sequence(lambda n: 'testype %d' % n)


class FilerField(Dmf):
    class Meta:
        model = File

    file = factory.django.FileField(from_path=settings.MEDIA_ROOT + '/Google.postman_collection.json')


class FilerFieldNoAssertion(Dmf):
    class Meta:
        model = File

    file = factory.django.FileField(from_path=settings.MEDIA_ROOT + '/Google_no_assertion.postman_collection.json')


class FilerFieldSubFolder(Dmf):
    class Meta:
        model = File

    file = factory.django.FileField(from_path=settings.MEDIA_ROOT + '/sub_sub_fold.postman_collection.json')


class PostmanTestNoAssertionFactory(Dmf):

    class Meta:
        model = PostmanTest
    test_scenario = factory.SubFactory(TestScenarioFactory)
    validation_file = factory.SubFactory(FilerFieldNoAssertion)


class PostmanTestFactory(Dmf):

    class Meta:
        model = PostmanTest
    test_scenario = factory.SubFactory(TestScenarioFactory)
    validation_file = factory.SubFactory(FilerField)
    name = factory.Sequence(lambda n: "Postman test %d" % n)


class PostmanTestSubFolderFactory(Dmf):

    class Meta:
        model = PostmanTest
    test_scenario = factory.SubFactory(TestScenarioFactory)
    validation_file = factory.SubFactory(FilerFieldSubFolder)


class TestScenarioUrlFactory(Dmf):

    class Meta:
        model = TestScenarioUrl

    name = factory.sequence(lambda n: 'test_scenario_url %d' % n)
    test_scenario = factory.SubFactory(TestScenarioFactory)


class ServerRunFactory(Dmf):

    class Meta:
        model = ServerRun

    test_scenario = factory.SubFactory(TestScenarioFactory)
    user = factory.SubFactory(UserFactory)
    started = timezone.now()
    client_id = 'client_id_field'
    secret = 'secret_field'


class EndpointFactory(Dmf):

    class Meta:
        model = Endpoint

    test_scenario_url = factory.SubFactory(TestScenarioUrlFactory)
    server_run = factory.SubFactory(ServerRunFactory)


class PostmanTestResultFactory(Dmf):

    class Meta:
        model = PostmanTestResult

    postman_test = factory.SubFactory(PostmanTestFactory)
    server_run = factory.SubFactory(ServerRunFactory)
    log = factory.django.FileField()
    log_json = factory.django.FileField()
