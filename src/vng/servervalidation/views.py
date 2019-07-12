from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.db.utils import IntegrityError
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, CreateView, UpdateView
from django.views.generic.list import ListView
from django.core.exceptions import PermissionDenied

import vng.postman.utils as postman

from ..utils import choices
from ..utils.views import OwnerSingleObject, PDFGenerator
from .forms import CreateServerRunForm, CreateEndpointForm
from .models import (
    ServerRun, Endpoint, TestScenarioUrl, TestScenario, PostmanTest, PostmanTestResult, ServerHeader
)
from .task import execute_test


class ServerRunList(LoginRequiredMixin, ListView):

    template_name = 'servervalidation/server-run_list.html'
    context_object_name = 'server_run_list'
    paginate_by = 10
    model = ServerRun

    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user).filter(scheduled=False).order_by('-started')

    def get_context_data(self, *args, **kwargs):
        data = super().get_context_data(*args, **kwargs)
        data['choices'] = dict(choices.StatusWithScheduledChoices.choices)
        data['choices']['error_deploy'] = choices.StatusChoices.error_deploy
        for sr in data['server_run_list']:
            sr.success = sr.get_execution_result()
        if 'server_run_scheduled' in self.request.session:
            data['second_tab'] = self.request.session['server_run_scheduled']
            del self.request.session['server_run_scheduled']
        return data

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return super().get(request, *args, **kwargs)


class ServerRunForm(CreateView):

    template_name = 'servervalidation/server-run-form.html'
    form_class = CreateServerRunForm

    def form_valid(self, form):
        ts_id = form.instance.test_scenario.id
        self.request.session['server_run_scheduled'] = form.instance.scheduled
        self.request.session['supplier_name'] = form.instance.supplier_name
        self.request.session['software_product'] = form.instance.software_product
        self.request.session['product_role'] = form.instance.product_role
        return redirect(reverse('server_run:server-run_create', kwargs={
            "test_id": ts_id
        }))


class ServerRunListScheduled(ServerRunList):

    template_name = 'servervalidation/server-run_list_scheduled.html'

    def get_queryset(self):
        return self.model.objects.filter(user=self.request.user).filter(scheduled=True).order_by('-started')


class CreateEndpoint(LoginRequiredMixin, CreateView):

    template_name = 'servervalidation/server-run_create.html'
    form_class = CreateEndpointForm

    def get_success_url(self):
        return reverse('server_run:server-run_list')

    def fetch_server(self):
        ts = get_object_or_404(TestScenario, pk=self.kwargs['test_id'])
        self.server = ServerRun(
            user=self.request.user,
            test_scenario=ts,
            scheduled=self.request.session.get('server_run_scheduled', False),
            supplier_name=self.request.session.get('supplier_name', ''),
            software_product=self.request.session.get('software_product', ''),
            product_role=self.request.session.get('product_role', '')
        )

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        pre_form = data['form']
        ts = get_object_or_404(TestScenario, pk=self.kwargs['test_id'])
        self.fetch_server()

        data['ts'] = ts
        data['test_scenario'] = TestScenarioUrl.objects.filter(test_scenario=ts)
        test_scenario_url = TestScenarioUrl.objects.filter(test_scenario=self.server.test_scenario).order_by('-url')
        url_names = [tsu.name for tsu in test_scenario_url]
        no_url = len(data['test_scenario'].filter(url=True))
        data['form'] = CreateEndpointForm(
            quantity=len(data['test_scenario'].filter(url=True)) - 1,
            placeholders=[t.placeholder for t in test_scenario_url],
            field_name=url_names[1:no_url],
            text_area=data['test_scenario'].filter(url=False),
            text_area_field_name=url_names[no_url:]
        )
        if ts.jwt_enabled():
            data['form'].add_text_area(['Client ID', 'Secret'])
        elif ts.custom_header():
            data['form'].add_text_area(['Authorization header'])
        else:
            pass
        data['form'].set_labels(url_names)
        for k, v in pre_form.errors.items():
            data['form'].errors[k] = v
        return data

    def form_valid(self, form):
        self.fetch_server()
        if self.server.test_scenario.jwt_enabled():
            self.server.client_id = form.data['Client ID']
            self.server.secret = form.data['Secret']
        elif self.server.test_scenario.custom_header():
            ServerHeader(server_run=self.server, header_key='Authorization', header_value=form.data['Authorization header']).save()
        self.server.save()
        self.endpoints = []
        tsu = list(TestScenarioUrl.objects.filter(test_scenario=self.server.test_scenario))

        for key, value in form.data.items():
            entry = list(filter(lambda x: x.name == key, tsu))
            if len(entry) == 1:
                entry = entry[0]
                tsu.remove(entry)
                ep = Endpoint(url=value, server_run=self.server, test_scenario_url=entry)
                ep.save()
                self.endpoints.append(ep)
        form.instance.server_run = self.server
        if tsu:
            form.instance.test_scenario_url = tsu[0]
        if self.server.scheduled:
            self.server.status = choices.StatusWithScheduledChoices.scheduled
        else:
            self.server.status = choices.StatusWithScheduledChoices.running
        self.server.save()
        try:
            ep = form.instance
            ep.server_run = self.server
            ep.save()
        except IntegrityError:
            form.add_error(None, 'Endpoint url not configured, contact the admin.')
            return super().form_invalid(form)
        self.endpoints.append(ep)
        if not self.server.scheduled:
            execute_test.delay(self.server.pk)

        return HttpResponseRedirect(self.get_success_url())


class ServerRunOutput(OwnerSingleObject, DetailView):

    model = ServerRun
    template_name = 'servervalidation/server-run_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        server_run = context['object']
        ptr = PostmanTestResult.objects.filter(server_run=server_run)
        context["postman_result"] = ptr
        return context


class ServerRunOutputUpdate(UpdateView):

    model = ServerRun
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    fields = [
        'supplier_name',
        'software_product',
        'product_role',
    ]
    template_name = 'servervalidation/server-run_update.html'

    def get_success_url(self):
        return reverse_lazy(
            'server_run:server-run_detail_uuid',
            kwargs={'uuid': self.object.uuid}
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        server_run = context['object']
        ptr = PostmanTestResult.objects.filter(server_run=server_run)
        context["postman_result"] = ptr
        context["update_info"] = False
        return context

    def get_object(self, queryset=None):
        res = super().get_object(queryset=queryset)
        if res.user != self.request.user:
            raise PermissionDenied()
        return res


class ServerRunOutputUuid(DetailView):

    model = ServerRun
    template_name = 'servervalidation/server-run_detail.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'

    def get_success_url(self):
        return reverse_lazy(
            'server_run:server-run_detail_uuid',
            kwargs={'uuid': self.object.uuid}
        )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        server_run = context['object']
        ptr = PostmanTestResult.objects.filter(server_run=server_run)
        context["postman_result"] = ptr
        context["update_info"] = True
        return context


class TriggerServerRun(OwnerSingleObject, View):

    model = ServerRun
    pk_name = 'server_id'

    def get(self, request, *args, **kwargs):
        server = self.get_object()
        if server.status == choices.StatusWithScheduledChoices.stopped:
            raise Http404("Server already stopped")
        self.request.session['server_run_scheduled'] = server.scheduled
        execute_test.delay(server.pk, scheduled=True, email=True)
        if server.scheduled:
            return redirect(reverse('server_run:server-run_list_scheduled'))
        return redirect(reverse('server_run:server-run_list'))


class StopServer(OwnerSingleObject, View):

    model = ServerRun
    pk_name = 'server_id'

    def post(self, request, *args, **kwargs):
        server = self.get_object()
        self.request.session['server_run_scheduled'] = server.scheduled
        server.stopped = timezone.now()
        server.status = choices.StatusWithScheduledChoices.stopped
        server.save()
        if server.scheduled:
            return redirect(reverse('server_run:server-run_list_scheduled'))
        return redirect(reverse('server_run:server-run_list'))


class ServerRunLogView(DetailView):

    model = ServerRun
    template_name = 'servervalidation/server-run_log.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return HttpResponse(content=self.object.postmantestresult_set.first().log)


class ServerRunLogJsonView(DetailView):

    model = ServerRun
    template_name = 'servervalidation/server-run_log_json.html'
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'


class ServerRunPdfView(PDFGenerator, ServerRunOutputUuid):

    template_name = 'servervalidation/server-run-PDF.html'

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        server_run = context['object']
        for ptm in context['postman_result']:
            ptm.json = ptm.get_json_obj()
            for calls in ptm.json:
                if 'response' in calls:
                    calls['response']['code'] = str(calls['response']['code'])
                else:
                    calls['response'] = 'Error occurred call the resource'

        self.filename = 'Server run {} report.pdf'.format(server_run.pk)
        context['error_codes'] = postman.get_error_codes()
        return context


class PostmanDownloadView(View):

    def get(self, request, pk, *args, **kwargs):
        pmt = get_object_or_404(PostmanTest, pk=pk)
        with open(pmt.validation_file.path) as f:
            response = HttpResponse(f, content_type='Application/json')
            response['Content-Length'] = len(response.content)
            response['Content-Disposition'] = 'attachment;filename={}.json'.format(pmt.test_scenario.name)
            return response


class TestScenarioDetail(DetailView):

    model = TestScenario
    template_name = 'servervalidation/test_scenario-detail.html'
