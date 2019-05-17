import json
import os

from kubernetes import client, config
from google.cloud import container_v1

from ..utils.commands import run_command

'''
Set with the location where the credentials are.
For further info visit: https://cloud.google.com/docs/authentication/getting-started
'''
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/projects/env/VNG_Test_platform-d71b9ef79195.json"

'''
The configuration of the kubectl has to be already performed.
By default it tries to fetch the resource located in $HOME/.kube/config or the environment variable KUBECONFIG.
For further info check https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/
and https://cloud.google.com/kubernetes-engine/docs/quickstart
'''
config.load_kube_config()

# TODO: set as global variable, maybe in the setting file?
# TODO: use library to execute commands instead of command line
project_id = 'vng-test-platform'
zone = 'europe-west4-a'


class K8S():

    def __init__(self, app_name=None):
        set_zone = [
            'gcloud',
            'config',
            'set',
            'compute/zone',
            'europe-west4-a'
        ]
        set_project = [
            'gcloud',
            'config',
            'set',
            'core/project',
            'vng-test-platform'
        ]
        run_command(set_zone)
        run_command(set_project)

        v1 = client.CoreV1Api()

    def fetch_resource(self, resource):
        fetch = [
            'kubectl',
            'get',
            resource,
            '--output=json'
        ]
        res = run_command(fetch).decode('utf-8')
        return json.loads(res)

    def deploy(self, app_name, image, port=8080, access_port=8080):
        create_cluster = [
            'gcloud',
            'container',
            'clusters',
            'create',
            'test-sessions',
            '--num-nodes=1',
        ]
        get_credentials = [
            'gcloud',
            'container',
            'clusters',
            'get-credentials',
            'test-sessions',
        ]
        # Create a general cluster (will error if it already exists)
        run_command(create_cluster)

        # Get the credentials to use kubectl for the correct cluster
        run_command(get_credentials)

        deploy_image = [
            'kubectl',
            'run',
            '{}'.format(app_name),
            '--image={}'.format(image),
            '--port={}'.format(port),
        ]
        load_balancer = [
            'kubectl',
            'expose',
            'deployment',
            '{}'.format(app_name),
            '--type=LoadBalancer',
            '--port={}'.format(access_port),
            '--target-port={}'.format(port)
        ]

        # Create a workload with pods
        run_command(deploy_image)

        # Create a load balancer to expose the cluster
        run_command(load_balancer)

    def delete(self, app_name):
        delete_service = [
            'kubectl',
            'delete',
            'service',
            '{}'.format(app_name),
        ]
        clean_up = [
            'kubectl',
            'delete',
            'deployment',
            '{}'.format(app_name),
        ]

        # Delete the load balancer
        run_command(delete_service)

        # Delete the workload
        run_command(clean_up)

    def get_pods_status(self, app_name):
        status_command = [
            'kubectl',
            'get',
            'pods',
            '--output=json'
        ]
        res1 = run_command(status_command).decode('utf-8')
        pods = json.loads(res1)
        items = pods.get('items')
        for item in items:
            metadata = item.get('metadata')
            if metadata and app_name in metadata.get('name'):
                status = item.get('status').get('containerStatuses')[0]
                if item.get('status').get('phase') == 'Pending':
                    return False, status.get('state').get('waiting').get('message')
                elif item.get('status').get('phase') == 'Running':
                    return True, None
        raise Exception('Application {} not found in the deployed cluster'.format(app_name))

    def status(self, app_name):
        status_command = [
            'kubectl',
            'get',
            'service',
            '--output=json'
        ]
        res1 = run_command(status_command).decode('utf-8')
        services = json.loads(res1)
        items = services.get('items')
        for item in items:
            metadata = item.get('metadata')
            if metadata and metadata.get('name') == app_name:
                ip_list = item.get('status').get('loadBalancer').get('ingress')
                if ip_list:
                    return ip_list[0].get('ip')
        raise Exception('Application {} not found in the deployed cluster'.format(app_name))

    def exec(self, app_name, command):
        exec_command = [
            'kubectl',
            'exec',
            app_name,
            *command
        ]
        run_command(exec_command)
