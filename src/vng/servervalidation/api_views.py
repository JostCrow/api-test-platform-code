
import json

from itertools import zip_longest

from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.utils import timezone

from django.db import transaction
from django.db.models import Prefetch

from rest_framework import permissions, viewsets, mixins, views
# from rest_framework.exceptions import bad_request

from rest_framework.authentication import (
    SessionAuthentication, TokenAuthentication
)
from drf_yasg.utils import swagger_auto_schema

from .serializers import ServerRunSerializer, ServerRunPayloadExample, ServerRunResultShield
from .models import ServerRun, PostmanTestResult
from .task import execute_test
from ..permissions.UserPermissions import isOwner
from ..utils import postman as ptm
from ..utils import choices


class ServerRunViewSet(
        mixins.CreateModelMixin,
        mixins.ListModelMixin,
        mixins.RetrieveModelMixin,
        viewsets.GenericViewSet):
    """
    create:
    Create a provider-run.

    Create a new provider-run instance.


    retrieve:
    Provider-run detail.

    Return the given provider-run.

    list:
    Provider-run list.

    Return a list of all the existing provider-run.
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ServerRunSerializer

    @swagger_auto_schema(request_body=ServerRunPayloadExample)
    def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)

    def get_queryset(self):
        return ServerRun.objects.filter(user=self.request.user).prefetch_related(
            Prefetch('endpoint_set', to_attr='endpoints'),
            Prefetch('endpoint_set__test_scenario_url'))

    @transaction.atomic
    def perform_create(self, serializer):
        if 'endpoints' in serializer._kwargs['data']:
            server = serializer.save(user=self.request.user, pk=None, started=timezone.now(), endpoint_list=serializer._kwargs['data'].pop('endpoints'))
        else:
            server = serializer.save(user=self.request.user, pk=None, started=timezone.now())


class TriggerServerRunView(viewsets.ViewSet):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated, )

    def update(self, request, pk):
        server = get_object_or_404(ServerRun, pk=pk)
        if server.status == choices.StatusWithScheduledChoices.stopped:
            raise Http404("Server already stopped")
        execute_test.delay(server.pk, scheduled=True)
        return JsonResponse({"asd": pk})


class ResultServerViewShield(
        mixins.RetrieveModelMixin,
        viewsets.GenericViewSet):

    @swagger_auto_schema(responses={200: ServerRunResultShield})
    def retrieve(self, request, pk=None):
        server = ServerRun.objects.get(uuid=pk)
        res = server.get_execution_result()
        is_error = True
        if res is None:
            message = 'No results'
            color = 'inactive'
        elif res:
            message = 'Success'
            color = 'green'
            is_error = False
        else:
            message = 'Failed'
            color = 'red'
        result = {
            'schemaVersion': 1,
            'label': 'VNG test platform',
            'message': message,
            'color': color,
            'isError': is_error,
        }

        return JsonResponse(result)


class ResultServerView(views.APIView):
    """
    Result of a Session

    Return for each scenario case related to the session, if that call has been performed and the global outcome.
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        self.server_run = get_object_or_404(ServerRun, pk=self.kwargs['pk'])
        return self.server_run

    def get(self, request, pk, *args, **kwargs):
        server_run = self.get_object()
        if not server_run.is_stopped():
            res = {
                'Information': 'The tests against the provider-run is undergoing.'
            }
            response = HttpResponse(json.dumps(res))
            response['Content-Type'] = 'application/json'
            return response
        postman_res = PostmanTestResult.objects.filter(server_run=server_run)
        response = []
        for postman in postman_res:
            postman.json = postman.get_json_obj()
            postman_res_output = {
                'time': postman.get_json_obj_info()['run']['timings']['started'],
                'calls': []
            }
            for call in postman.json:
                _call = {
                    'name': call['item']['name'],
                    'request': call['request']['method'],
                    'response': call['response']['code'],
                }
                if 'assertions' in call:
                    for _assertion in call['assertions']:
                        _assertion['result'] = 'failed' if 'error' in _assertion else 'success'
                    _call['assertions'] = call['assertions']
                else:
                    _call['assertions'] = []

                if call['response']['code'] in ptm.get_error_codes():
                    _call['status'] = 'Error'
                else:
                    _call['status'] = 'Success'
                postman_res_output['calls'].append(_call)

            postman_res_output['status'] = postman.status
            response.append(postman_res_output)
        return JsonResponse(response, safe=False)
