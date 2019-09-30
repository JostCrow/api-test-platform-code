import uuid
from zds_client import ClientAuth
import traceback
import re
import json

from django.core.files import File
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from celery.utils.log import get_task_logger
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from vng.postman.choices import ResultChoices

from ..celery.celery import app
from .models import PostmanTest, PostmanTestResult, Endpoint, ServerRun, ServerHeader, ScheduledTestScenario
from ..utils import choices
from ..utils.newman import NewmanManager
from ..utils.auth import get_jwt


logger = get_task_logger(__name__)


@app.task
def execute_test_scheduled():
    scheduled_scenarios = ScheduledTestScenario.objects.filter(active=True)
    for schedule in scheduled_scenarios:
        # server_run = ServerRun.objects.filter(scheduled=True).filter(status=choices.StatusWithScheduledChoices.scheduled).order_by('user')
        server_run = ServerRun.objects.create(
            test_scenario=schedule.test_scenario,
            scheduled_scenario=schedule,
            environment=schedule.environment,
            user=schedule.user
        )
        s_list = []
        failed = False
        for i, sr in enumerate(server_run):
            sr.status = choices.StatusWithScheduledChoices.running
            sr.save()
            result = execute_test(sr.pk, scheduled=True)
            failed = failed or result
            s_list.append((sr, result))
            if i == len(server_run) - 1 or sr.user != server_run[i + 1].user and s_list != []:
                # Send email only if there is at least one failure
                if result:
                    send_email_failure(s_list)
                s_list = []
                failed = False


def substitute_hidden_vars(server_run, file):
    data = file.read()
    hidden_vars = server_run.endpoint_set.filter(test_scenario_url__hidden=True)
    for hidden in hidden_vars:
        data = re.sub('{}'.format(hidden.url), '{hidden}', data)
    return data


@app.task
def execute_test(server_run_pk, scheduled=False, email=False):
    server_run = ServerRun.objects.get(pk=server_run_pk)
    server_run.status = choices.StatusWithScheduledChoices.running
    endpoints = server_run.environment.endpoint_set.all()

    file_name = str(uuid.uuid4())
    postman_tests = PostmanTest.objects.filter(test_scenario=server_run.test_scenario).order_by('order')
    # remove previous results
    PostmanTestResult.objects.filter(server_run=server_run).delete()
    failure = False
    try:
        for counter, postman_test in enumerate(postman_tests):
            auth_choice = postman_test.test_scenario.authorization
            if auth_choice == choices.AuthenticationChoices.jwt:
                jwt_auth = get_jwt(server_run).credentials()
            server_run.status_exec = 'Running the test {}'.format(postman_test.validation_file)
            server_run.percentage_exec = int(((counter + 1) / (len(postman_tests) + 1)) * 100)
            server_run.save()
            nm = NewmanManager(postman_test.validation_file)

            if auth_choice == choices.AuthenticationChoices.jwt:
                nm.replace_parameters({
                    'BEARER_TOKEN': list(jwt_auth.values())[0].split()[1]
                })
            elif auth_choice == choices.AuthenticationChoices.header:
                se = ServerHeader.objects.filter(server_run=server_run)
                for header in se:
                    nm.replace_parameters({
                        'Authentication': header.header_value
                    })
            elif auth_choice == choices.AuthenticationChoices.no_auth:
                pass
            param = {}
            for ep in endpoints:
                param[ep.test_scenario_url.name] = ep.url
            nm.replace_parameters(param)
            file_html, file_json = nm.execute_test()
            ptr = PostmanTestResult(
                postman_test=postman_test,
                server_run=server_run
            )
            data = substitute_hidden_vars(server_run, file_html)
            data_json = substitute_hidden_vars(server_run, file_json)

            with open(file_html.name, 'w') as f:
                f.write(data)

            with open(file_json.name, 'w') as f:
                json.dump(json.loads(data_json), f, indent=4)

            ptr.log.save(file_name, File(open(file_html.name)))
            ptr.save_json(file_name, File(open(file_json.name)))
            ptr.status = ptr.get_outcome_json()
            ptr.save()
            failure = failure or (ptr.status == ResultChoices.failed)

        server_run.status_exec = 'Completed'
    except Exception as e:
        logger.warning(e)
        server_run.status = choices.StatusChoices.error_deploy
        server_run.status_exec = traceback.format_exc()

    server_run.percentage_exec = 100
    # if not scheduled:
    if server_run.status != choices.StatusChoices.error_deploy:
        server_run.status = choices.StatusWithScheduledChoices.stopped
    server_run.stopped = timezone.now()

    # else:
        # server_run.last_exec = timezone.now()
        # server_run.status = choices.StatusWithScheduledChoices.scheduled
    if email and not failure:
        send_email_failure([(server_run, failure)])
    server_run.save()
    return failure


def send_email_failure(sl):
    from django.contrib.sites.models import Site
    domain = Site.objects.get_current().domain
    msg_html = render_to_string('servervalidation/failed_test_email.html', {
        'successful': [s for s in sl if not s[1]],
        'failure': [s for s in sl if s[1]],
        'domain': domain
    })

    send_mail(
        _('Results of scheduled tests'),
        msg_html,
        settings.DEFAULT_FROM_EMAIL,
        [sl[0][0].user.email],
        html_message=msg_html
    )
