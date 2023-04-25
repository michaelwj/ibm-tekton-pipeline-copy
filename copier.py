import time

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_continuous_delivery.cd_toolchain_v2 import CdToolchainV2
from ibm_continuous_delivery.cd_tekton_pipeline_v2 import CdTektonPipelineV2
from ibm_platform_services import IamIdentityV1
from ibm_platform_services import ResourceManagerV2
from prettytable import PrettyTable

# Authenticator
# add IBM iam_api_key
iam_api_key = ''
authenticator = IAMAuthenticator(apikey=iam_api_key)

# IBM API URLs
iam_identity_url = 'https://iam.cloud.ibm.com'
resource_manager_url = 'https://resource-controller.cloud.ibm.com'
# Replace with your region's URLs
tekton_pipeline_url = 'https://api.us-south.devops.cloud.ibm.com/pipeline/v2'
toolchain_url = 'https://api.us-south.devops.cloud.ibm.com/toolchain/v2'

# IBM API Init
iam_identity_api = IamIdentityV1(authenticator=authenticator)
iam_identity_api.set_service_url(iam_identity_url)

resource_manager_api = ResourceManagerV2(authenticator=authenticator)
resource_manager_api.set_service_url(resource_manager_url)

tekton_pipeline_api = CdTektonPipelineV2(authenticator=authenticator)
tekton_pipeline_api.set_service_url(tekton_pipeline_url)

toolchain_api = CdToolchainV2(authenticator=authenticator)
toolchain_api.set_service_url(toolchain_url)

def get_account_id():
    api_key_details = iam_identity_api.get_api_keys_details(iam_api_key=iam_api_key).get_result()
    return api_key_details['account_id']

def print_and_select_data(data, columns, message):
    table = PrettyTable()
    table.field_names = ["Index"] + columns
    table.align["Index"] = "r"

    for idx, item in enumerate(data):
        row = []
        for col in columns:
            if "." in col:
                parts = col.split(".")
                value = item
                for part in parts:
                    value = value.get(part, "")
                    if not value:
                        break
            else:
                value = item.get(col, "")

            row.append(value)
        table.add_row([idx+1] + row)

    print(table)

    # Ask the user to select a row
    selection = None
    while selection is None:
        try:
            print(message)
            selection = int(input('\nEnter the index of the row you would like to use: '))
            if selection < 1 or selection > len(data):
                raise ValueError()
        except ValueError:
            print('Invalid input. Please enter an index between 1 and', len(data))
            selection = None

    # Return the selected row
    return data[selection - 1]

def select_resource_group(account_id):
    resource_groups = resource_manager_api.list_resource_groups(account_id=account_id).get_result()
    return print_and_select_data(resource_groups['resources'], ['name', 'id'], 'Choose a Resource Group:')

def select_toolchain(resource_group_id):
    toolchains = toolchain_api.list_toolchains(resource_group_id = resource_group_id)

    return print_and_select_data(toolchains.result['toolchains'], ['name', 'id','location'], 'Choose a Toolchain:')

def get_pipelines(toolchain_id):
    tools = toolchain_api.list_tools(toolchain_id = toolchain_id)

    # filter tools
    return [t for t in tools.result['tools'] if t['tool_type_id'] == 'pipeline']

def get_pipeline_definitions(pipeline_id):
    definitions = tekton_pipeline_api.list_tekton_pipeline_definitions(pipeline_id=pipeline_id,)
    return definitions.get_result()

def put_pipeline_definitions(definitions, pipeline_id):
    for d in definitions:
        properties = d['source']['properties']
        definition_source_properties_model = {
            'url': properties['url'],
            'branch': properties['branch'],
            'path': properties['path'],
        }

        definition_source_model = {
            'type': d['source']['type'],
            'properties': definition_source_properties_model,
        }

        response = tekton_pipeline_api.create_tekton_pipeline_definition(
            pipeline_id=pipeline_id,
            source=definition_source_model,
        )

        definition = response.get_result()
        if definition and definition['id']:
            print(properties['path'], 'copied successfully')
        else:
            print(properties['path'], 'failed to copy')
        # ibm api throttling
        time.sleep(2)

def get_pipeline_environment_properties(pipeline_id):
    environment_properties = tekton_pipeline_api.list_tekton_pipeline_properties(pipeline_id=pipeline_id,)
    return environment_properties.get_result()

def put_pipeline_environment_properties(properties, pipeline_id):
    for p in properties:
        if p['type'] == 'single_select':
            response = tekton_pipeline_api.create_tekton_pipeline_properties(
                pipeline_id=pipeline_id,
                name=p['name'],
                type=p['type'],
                value=p['value'],
                enum=p['enum']
            )
        else:
            response = tekton_pipeline_api.create_tekton_pipeline_properties(
                pipeline_id=pipeline_id,
                name=p['name'],
                type=p['type'],
                value=p['value'],
            )

        property = response.get_result()
        if property and property['name']:
                print(p['name'], 'copied successfully')
        else:
            print(p['name'], 'failed to copy')
        # ibm api throttling
        time.sleep(2)

def main():
    print('main()')
    # get account id
    account_id = get_account_id()

    # list available resource groups and select
    resource_group = select_resource_group(account_id)

    # list available toolchains
    toolchain = select_toolchain(resource_group['id'])

    # get pipelines
    pipelines = get_pipelines(toolchain['id'])

    # list and select source pipeline
    source_pipeline = print_and_select_data(pipelines, ['parameters.name', 'id','tool_type_id'], 'Choose source Delivery Pipeline to copy from:')

    # list and select target pipeline
    target_pipeline = print_and_select_data(pipelines, ['parameters.name', 'id','tool_type_id'], 'Choose target Delivery Pipeline to copy to:')
    while source_pipeline == target_pipeline:
        print('Target Pipeline must be different than Source Pipeline')
        target_pipeline = print_and_select_data(pipelines, ['parameters.name', 'id','tool_type_id'], 'Choose target Delivery Pipeline to copy to:')

    # copy definitions
    definitions = get_pipeline_definitions(source_pipeline['id'])
    put_pipeline_definitions(definitions['definitions'], target_pipeline['id'])

    # copy environment properties
    environment_properties = get_pipeline_environment_properties(source_pipeline['id'])
    put_pipeline_environment_properties(environment_properties['properties'], target_pipeline['id'])

if __name__ == "__main__":
    main()