import pathlib
import json
from typing import Optional, Any

import pulumi  # noqa
import pulumi_azure  # TODO: Consider migrating to native
import pulumi_azure_native as azure_native
import pulumiverse_time
import pulumi_databricks
import pulumi_azuread

from databricks_udr_ip_map import DATABRICKS_UDR_IP_MAP


# ======= CONFIGURATION =======
class HeiferConfig:
    """Main configuration class. Contains mainly names of resources and generic configuration.

    Warning:
        Names for resources needs to reflects limitations presented:
      https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules
    Note:
        Many other configuration variables are included in HeiferClusterConfig class.
    """
    # Location of the services (typically uksouth)
    AZURE_LOCATION: str = "TODO: FILL"
    # Resource group name (where things are deployed)
    RESOURCE_GROUP: str = "TODO: FILL"
    # Storage Account name for Bronze/Silver/Gold (or similar) layers
    #   Note that name for storage account is restricted: up to 24 alphanumeric chars, no hyphens
    STORAGE_ACCOUNT_NAME: str = "TODO: FILL"
    # Concrete layers (containers) present in the storage account (typically bronze, silver, gold)
    #   Warning: this value cannot be changed easily (have functional impacts)
    STORAGE_ACCOUNT_LAYERS: set[str] = {'bronze', 'silver', 'gold', 'libraries'}
    # Databricks workspace name
    DATABRICKS_WORKSPACE_NAME: str = "TODO: FILL"
    # Managed resource group name for Databricks
    DATABRICKS_MANAGED_RESOURCE_GROUP_NAME: str = "TODO: FILL"
    # Databricks secret scope name
    DATABRICKS_SECRET_SCOPE_NAME: str = "TODO: FILL"
    # Storage account name for Databricks filesystem (unique), is created by Databricks
    #   Note that name for storage account is restricted: up to 24 alphanumeric chars, no hyphens
    DATABRICKS_DFS_STORAGE_ACCOUNT_NAME: str = "TODO: FILL"
    # Account ID of the Databricks user for setting up provider
    # TODO: needs to be set up after the workspace is created. To find it go to Account Console
    #   (Manage Account) from inside workspace, then click on your name (right top corner).
    DATABRICKS_ACCOUNT_ID: Optional[str] = None
    # Unique UUID for the app registration for the Service Principal linking ADF and Workspace
    #   TODO: Find in ADF -> Properties (caption 'Managed Identity Application ID')
    DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID: Optional[str] = None
    # Azure Data Factory name
    AZURE_DATA_FACTORY_NAME: str = "TODO: FILL"
    # Name of the main Heifers virtual network
    VIRTUAL_NETWORK_NAME: str = "TODO: FILL"
    # Network address prefix for virtual network (must differs from others)
    VIRTUAL_NETWORK_ADDRESS_SPACE: str = "10.40.0.0/22"
    # There is a need to define subnets for shared, databricks host, and databricks container.
    #   - use any online Subnet Calculator to find a plausible values.
    VIRTUAL_NETWORK_SUBNETS_ADDRESS_SPACES: dict[str, str] = {
        "shared_subnet": "10.40.0.0/24",
        "databricks_host_subnet": "10.40.1.0/24",
        "databricks_container_subnet": "10.40.2.0/24",
    }
    # Path to directory with pipelines from inside Docker (DO NOT CHANGE UNLESS YOU KNOW)
    PATH_TO_PIPELINES: pathlib.Path = pathlib.Path("../pipelines")
    # This is the relative path to folder which content is upload as files to DBFS.
    #   (DO NOT CHANGE UNLESS YOU KNOW)
    PATH_TO_PIPELINES_UPLOAD_FOLDER: pathlib.Path = pathlib.Path("artifacts")
    # Decide whether to upload libraries (artifacts content)
    # TODO: Set to False on the first round, add your IP exception to the Storage Account Firewall
    #  rules before running. Also, check if the content of files is not empty (like __init__.py)
    UPLOAD_LIBRARIES: bool = False


class HeiferClusterConfiguration:
    """Configuration for the Spark (PySpark) job cluster.
    Note:
        To see the configuration options for Pulumi, visit the website:
https://www.pulumi.com/registry/packages/azure/api-docs/datafactory/linkedserviceazuredatabricks/
    """
    # Spark version, as an output of: pulumi_databricks.get_spark_version()
    CLUSTER_VERSION: str = "14.2.x-scala2.12"
    # Define auto scaling option for the cluster (minimum and maximum workers)
    MIN_NUMBER_OF_WORKERS: int = 2
    MAX_NUMBER_OF_WORKERS: int = 8
    # Node type ID as an output of the command:
    # pulumi_databricks.get_node_type(category='General Purpose', min_memory_gb=16, min_cores=4,
    #                                 photon_driver_capable=True, photon_worker_capable=True)
    NODE_TYPE: str = "Standard_D4as_v5"
    # Location for storing cluster's logs (must be in DBFS)
    LOG_DESTINATION: Optional[str] = "dbfs:/heifer_logs"
    # Secrets definition for Spark cluster, follows the logic:
    #   https://learn.microsoft.com/en-us/azure/databricks/security/secrets/secrets
    #   ones listed here are merged with system ones later (in cluster definition)
    SPARK_CONFIG: Optional[dict[str, Any]] = {
        # TODO: FILL
    }
# =============================


# -- Get information about current client (person who is deploying, probably you) --
CURRENT_CLIENT = azure_native.authorization.get_client_config()
# ----------------------------------------------------------------------------------


# -- Create an Azure Resource Group for HeifER --
heifer_rg = azure_native.resources.ResourceGroup(
    resource_name=HeiferConfig.RESOURCE_GROUP,
    location=HeiferConfig.AZURE_LOCATION,
)
# -----------------------------------------------


# -- Create an Azure Storage account for HeifER --
heifer_storage_account = azure_native.storage.StorageAccount(
    resource_name=HeiferConfig.STORAGE_ACCOUNT_NAME,
    account_name=HeiferConfig.STORAGE_ACCOUNT_NAME,
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    kind="StorageV2",
    is_hns_enabled=True,
    encryption=azure_native.storage.EncryptionArgs(require_infrastructure_encryption=True),
    enable_https_traffic_only=True,
    sku=azure_native.storage.SkuArgs(name="Standard_GRS"),
    access_tier=azure_native.storage.AccessTier.HOT,
    public_network_access=azure_native.storage.PublicNetworkAccess.DISABLED,
)
# ------------------------------------------------


# -- Create containers for each layer (aka zone; typically bronze, silver, gold) --
for container_name in HeiferConfig.STORAGE_ACCOUNT_LAYERS:
    heifer_layer_container = azure_native.storage.BlobContainer(
        resource_name=container_name,
        resource_group_name=heifer_rg.name,
        account_name=heifer_storage_account.name,
        container_name=container_name,
        public_access=azure_native.storage.PublicAccess.NONE,
    )
# ---------------------------------------------------------------------------------

# -- List all pipelines definitions and artifacts to be deployed --
pipelines_definitions: list[dict] = []
upload_files_paths: list[dict[str, str]] = []
for _directory in HeiferConfig.PATH_TO_PIPELINES.iterdir():
    if _directory.is_dir():
        if (_directory / "pipelines").is_dir():
            for _pipeline in (_directory / "pipelines").iterdir():
                if (pipeline_file := (_pipeline / "pipeline.json")).is_file():
                    pipelines_definitions.append(json.load(pipeline_file.open('r')))
                    # Iteration for each file to be uploaded
                    for _artifact_file in (_pipeline /
                                           HeiferConfig.PATH_TO_PIPELINES_UPLOAD_FOLDER).iterdir():
                        if _artifact_file.is_file():
                            upload_files_paths.append(
                                {
                                    "local_path": str(_artifact_file),
                                    "abfss_path": str(
                                            pathlib.Path(_pipeline.name) / _artifact_file.name
                                    )
                                }
                            )
# -----------------------------------------------------------------

# -- Upload files (.py scripts, WHL) from pipeline --
if HeiferConfig.UPLOAD_LIBRARIES:
    for _upload_file_path in upload_files_paths:
        heifer_file_to_upload = azure_native.storage.Blob(
            resource_name=_upload_file_path['abfss_path'],
            resource_group_name=heifer_rg.name,
            account_name=heifer_storage_account.name,
            container_name="libraries",
            type=azure_native.storage.BlobType.BLOCK,
            source=pulumi.FileAsset(_upload_file_path['local_path']),
            opts=pulumi.ResourceOptions(
                depends_on=[heifer_storage_account],
            ),
        )
# ---------------------------------------------------


# -- Create Azure Data Factory --
# heifer_adf = azure_native.datafactory.Factory(
#     resource_name=HeiferConfig.AZURE_DATA_FACTORY_NAME,
#     factory_name=HeiferConfig.AZURE_DATA_FACTORY_NAME,
#     # managed_virtual_network_enabled=True,
#     resource_group_name=heifer_rg.name,
#     location=heifer_rg.location,
#     identity=azure_native.datafactory.FactoryIdentityArgs(type="SystemAssigned"),
# )
heifer_adf = pulumi_azure.datafactory.Factory(
    resource_name=HeiferConfig.AZURE_DATA_FACTORY_NAME,
    name=HeiferConfig.AZURE_DATA_FACTORY_NAME,
    managed_virtual_network_enabled=True,  # TODO: once supported in Pulumi Native, migrate
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    identity=pulumi_azure.datafactory.FactoryIdentityArgs(type="SystemAssigned"),
)
# -------------------------------


# -- Network security group for databricks subnets --
heifer_databricks_network_security_group = azure_native.network.NetworkSecurityGroup(
    resource_name="nsg-heifer-databricks",
    network_security_group_name="nsg-heifer-databricks",
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
)
# ---------------------------------------------------


# -- Databricks route table --
heifer_databricks_route_table = azure_native.network.RouteTable(
    resource_name="heifer-databricks-route-table",
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    route_table_name="heifer-databricks-route-table"
)
# ----------------------------


# -- Create Databricks routes for the table --
for _route_name, _address_prefix in {
    "heifer-databricks": "AzureDatabricks",
    "heifer-sql": "Sql",
    "heifer-storage": "Storage",
    "heifer-eventhub": "EventHub"
  }.items():
    heifer_databricks_route = azure_native.network.Route(
        resource_name=_route_name,
        address_prefix=_address_prefix,
        next_hop_type="Internet",
        resource_group_name=heifer_rg.name,
        route_name=_route_name,
        route_table_name=heifer_databricks_route_table.name
    )
# --------------------------------------------


# -- Routes for Databricks UDR IP --
for _location_name, _ip_value in DATABRICKS_UDR_IP_MAP.items():
    heifer_databricks_ip_route = azure_native.network.Route(
        resource_name=f"heifer-location-{_location_name}",
        route_table_name=heifer_databricks_route_table.name,
        address_prefix=_ip_value,
        next_hop_type="Internet",
        resource_group_name=heifer_rg.name,
        route_name=f"heifer-location-{_location_name}",
    )
# --------------------------------------------


# -- Main Heifer's virtual network --
heifer_virtual_network = azure_native.network.VirtualNetwork(
    resource_name=HeiferConfig.VIRTUAL_NETWORK_NAME,
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    virtual_network_name=HeiferConfig.VIRTUAL_NETWORK_NAME,
    address_space=azure_native.network.AddressSpaceArgs(
        address_prefixes=[HeiferConfig.VIRTUAL_NETWORK_ADDRESS_SPACE],
    ),
)
# -----------------------------------


# -- Subnet for shared services --
heifer_shared_subnet = azure_native.network.Subnet(
    resource_name="subnet-heifer-databricks-shared",
    subnet_name="subnet-heifer-databricks-shared",
    resource_group_name=heifer_rg.name,
    address_prefix=HeiferConfig.VIRTUAL_NETWORK_SUBNETS_ADDRESS_SPACES["shared_subnet"],
    virtual_network_name=heifer_virtual_network.name,
    route_table=azure_native.network.RouteTableArgs(id=heifer_databricks_route_table.id),
)
# --------------------------------


# -- Subnet for Databricks host --
heifer_databricks_host_subnet = azure_native.network.Subnet(
    resource_name="subnet-heifer-databricks-host",
    subnet_name="subnet-heifer-databricks-host",
    resource_group_name=heifer_rg.name,
    address_prefix=HeiferConfig.VIRTUAL_NETWORK_SUBNETS_ADDRESS_SPACES["databricks_host_subnet"],
    virtual_network_name=heifer_virtual_network.name,
    delegations=[
        azure_native.network.DelegationArgs(
            name="delegation-heifer-databricks-host",
            service_name="Microsoft.Databricks/workspaces",
            actions=[
                "Microsoft.Network/virtualNetworks/subnets/join/action",
                "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
                "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
            ]
        )
    ],
    network_security_group=azure_native.network.NetworkSecurityGroupArgs(
        id=heifer_databricks_network_security_group.id
    ),
    route_table=azure_native.network.RouteTableArgs(id=heifer_databricks_route_table.id),
)
# --------------------------------


# -- Subnet for Databricks container --
heifer_databricks_container_subnet = azure_native.network.Subnet(
    resource_name="subnet-heifer-databricks-container",
    subnet_name="subnet-heifer-databricks-container",
    resource_group_name=heifer_rg.name,
    address_prefix=HeiferConfig.VIRTUAL_NETWORK_SUBNETS_ADDRESS_SPACES[
        "databricks_container_subnet"
    ],
    virtual_network_name=heifer_virtual_network.name,
    delegations=[
        azure_native.network.DelegationArgs(
            name="delegation-heifer-databricks-container",
            service_name="Microsoft.Databricks/workspaces",
            actions=[
                "Microsoft.Network/virtualNetworks/subnets/join/action",
                "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
                "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
            ]
        )
    ],
    network_security_group=azure_native.network.NetworkSecurityGroupArgs(
        id=heifer_databricks_network_security_group.id
    ),
    route_table=azure_native.network.RouteTableArgs(id=heifer_databricks_route_table.id),
    opts=pulumi.ResourceOptions(depends_on=[heifer_databricks_host_subnet]),
)
# -------------------------------------


# -- Private Endpoint to the Databricks data file system --
heifer_private_endpoint_databricks_dfs = azure_native.network.PrivateEndpoint(
    resource_name="pe-heifer-databricks-dfs",
    private_endpoint_name="pe-heifer-databricks-dfs",
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    subnet=azure_native.network.SubnetArgs(id=heifer_shared_subnet.id),
    private_link_service_connections=[
        azure_native.network.PrivateLinkServiceConnectionArgs(
            name="pe-conn-heifer-databricks-dfs",
            private_link_service_id=heifer_storage_account.id,
            request_message="Approve connection to Databricks DFS.",
            group_ids=["dfs"],
        ),
    ],
    opts=pulumi.ResourceOptions(depends_on=[heifer_shared_subnet, heifer_storage_account]),
)
# ---------------------------------------------------------


# -- Private Endpoint to the Databricks blob --
heifer_private_endpoint_databricks_blob = azure_native.network.PrivateEndpoint(
    resource_name="pe-heifer-databricks-blob",
    private_endpoint_name="pe-heifer-databricks-blob",
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    subnet=azure_native.network.SubnetArgs(id=heifer_shared_subnet.id),
    private_link_service_connections=[
        azure_native.network.PrivateLinkServiceConnectionArgs(
            name="pe-conn-heifer-databricks-blob",
            private_link_service_id=heifer_storage_account.id,
            request_message="Approve connection to Databricks blob.",
            group_ids=["blob"],
        ),
    ],
    opts=pulumi.ResourceOptions(depends_on=[heifer_shared_subnet, heifer_storage_account]),
)
# ---------------------------------------------


# -- Databricks Workspace --
heifer_databricks_workspace = azure_native.databricks.Workspace(
    resource_name=HeiferConfig.DATABRICKS_WORKSPACE_NAME,
    workspace_name=HeiferConfig.DATABRICKS_WORKSPACE_NAME,
    resource_group_name=heifer_rg.name,
    managed_resource_group_id=f'/subscriptions/{CURRENT_CLIENT.subscription_id}/resourceGroups/'
                              f'{HeiferConfig.DATABRICKS_MANAGED_RESOURCE_GROUP_NAME}',
    location=heifer_rg.location,
    sku=azure_native.databricks.SkuArgs(name="premium"),
    public_network_access=azure_native.databricks.PublicNetworkAccess.ENABLED,  # TODO: CHANGE
    required_nsg_rules=azure_native.databricks.RequiredNsgRules.ALL_RULES,  # TODO: CHANGE
    parameters=azure_native.databricks.WorkspaceCustomParametersArgs(
        require_infrastructure_encryption=azure_native.databricks.WorkspaceCustomBooleanParameterArgs(value=True),  # noqa: E501
        enable_no_public_ip=azure_native.databricks.WorkspaceCustomBooleanParameterArgs(value=True),  # noqa: E501
        custom_public_subnet_name=azure_native.databricks.WorkspaceCustomStringParameterArgs(value=heifer_databricks_host_subnet.name),  # noqa: E501
        custom_private_subnet_name=azure_native.databricks.WorkspaceCustomStringParameterArgs(value=heifer_databricks_container_subnet.name),  # noqa: E501
        custom_virtual_network_id=azure_native.databricks.WorkspaceCustomStringParameterArgs(value=heifer_virtual_network.id),  # noqa: E501
        storage_account_name=azure_native.databricks.WorkspaceCustomStringParameterArgs(value=HeiferConfig.DATABRICKS_DFS_STORAGE_ACCOUNT_NAME),  # noqa: E501
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_databricks_host_subnet,
                    heifer_databricks_container_subnet,
                    heifer_virtual_network,
                    heifer_private_endpoint_databricks_dfs,
                    heifer_private_endpoint_databricks_blob],
        custom_timeouts=pulumi.CustomTimeouts(create="30m", update="30m", delete="30m")
    ),
)
# --------------------------


# --- Give 200s to finish creation of the Databricks Workspace ---
heifer_200_seconds_break = pulumiverse_time.Sleep(
    resource_name="heifer-200-seconds-break",
    create_duration="200s",
    opts=pulumi.ResourceOptions(depends_on=[heifer_databricks_workspace]),
)
# ----------------------------------------------------------------


# -- Private Endpoint to the Databricks control plane --
heifer_private_endpoint_databricks_control_plane = azure_native.network.PrivateEndpoint(
    resource_name="pe-heifer-databricks-control-plane",
    private_endpoint_name="pe-heifer-databricks-control-plane",
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    subnet=azure_native.network.SubnetArgs(id=heifer_shared_subnet.id),
    private_link_service_connections=[
        azure_native.network.PrivateLinkServiceConnectionArgs(
            name="pe-conn-heifer-databricks-control-plane",
            private_link_service_id=heifer_databricks_workspace.id,
            request_message="Approve connection to Databricks control plane.",
            group_ids=["databricks_ui_api"],
        ),
    ],
    opts=pulumi.ResourceOptions(depends_on=[heifer_200_seconds_break]),
)
# ------------------------------------------------------


# -- Private endpoint to Databricks filesystem --
heifer_private_endpoint_databricks_filesystem = azure_native.network.PrivateEndpoint(
    resource_name="pe-heifer-databricks-filesystem",
    private_endpoint_name="pe-heifer-databricks-filesystem",
    resource_group_name=heifer_rg.name,
    location=heifer_rg.location,
    subnet=azure_native.network.SubnetArgs(id=heifer_shared_subnet.id),
    private_link_service_connections=[
        azure_native.network.PrivateLinkServiceConnectionArgs(
            name="pe-conn-heifer-databricks-filesystem",
            private_link_service_id="".join(
                [f'/subscriptions/{CURRENT_CLIENT.subscription_id}/resourceGroups/'
                 f'{HeiferConfig.DATABRICKS_MANAGED_RESOURCE_GROUP_NAME}',
                 f"/providers/Microsoft.Storage/storageAccounts/"
                 f"{HeiferConfig.DATABRICKS_DFS_STORAGE_ACCOUNT_NAME}"]
            ),
            request_message="Approve connection to Databricks filesystem.",
            group_ids=["blob"],
        ),
    ],
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_200_seconds_break]
    ),
)
# -----------------------------------------------


# -- Add a current deployer (user using Pulumi) as a Contributor to Workspace --
perm_heifer_current_user_workspace_contributor = azure_native.authorization.RoleAssignment(
    resource_name='perm-heifer-current-user-workspace-contributor',
    principal_id=CURRENT_CLIENT.object_id,
    principal_type=azure_native.authorization.PrincipalType.USER,
    # role_definition_name='Contributor',
    role_definition_id=f"/subscriptions/{CURRENT_CLIENT.subscription_id}/providers/"
                       f"Microsoft.Authorization/roleDefinitions/"
                       f"b24988ac-6180-42a0-ab88-20f7382dd24c",  # Contributor GUID
    scope=heifer_databricks_workspace.id,
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_databricks_workspace]
    ),
)
# ------------------------------------------------------------------------------


# -- Configure Databricks provider to be able to deploy Cluster --
heifer_databricks_provider = pulumi_databricks.Provider(
    resource_name="heifer-databricks-provider",
    host=heifer_databricks_workspace.workspace_url,
    azure_client_id=HeiferConfig.DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID,
    account_id=HeiferConfig.DATABRICKS_ACCOUNT_ID,
    azure_use_msi=True,
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_databricks_workspace],
    ),
)
# ----------------------------------------------------------------


if not HeiferConfig.DATABRICKS_ACCOUNT_ID or \
        not HeiferConfig.DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID:
    # The following code does not make sense to run till the DATABRICKS_ACCOUNT_ID is set.
    pulumi.export("Warning", "You need to set up the DATABRICKS_ACCOUNT_ID and "
                             "DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID variable")
    exit(0)


# -- Assign role to the ADF's Service Principal to allow cluster creation --
heifer_adf_serpr_role_assignment = azure_native.authorization.RoleAssignment(
    resource_name='heifer-adf-serpr-role-assignment',
    principal_id=HeiferConfig.DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID,
    principal_type=azure_native.authorization.PrincipalType.SERVICE_PRINCIPAL,
    # role_definition_name='Contributor',
    role_definition_id=f"/subscriptions/{CURRENT_CLIENT.subscription_id}/providers/"
                       f"Microsoft.Authorization/roleDefinitions/"
                       f"b24988ac-6180-42a0-ab88-20f7382dd24c",  # Contributor GUID
    scope=heifer_databricks_workspace.id,
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_databricks_workspace, heifer_adf]
    ),
)
# --------------------------------------------------------------------------


# -- Create Service Principal with Storage Blob Data Contributor access to Storage Account --
# A) Azure requires Application Registration for principals
heifer_app_for_databricks_storage_account = pulumi_azuread.ApplicationRegistration(
    resource_name="heifer-app-for-databricks-storage-account",
    display_name="heifer-app-for-databricks-storage-account",
)
# B) To define client_secret value of the principal
heifer_app_for_databricks_storage_account_password = pulumi_azuread.ApplicationPassword(
    resource_name="heifer-app-for-databricks-storage-account-password",
    application_id=heifer_app_for_databricks_storage_account.id
)
# C) Actual service principal definition
heifer_service_principal_for_databricks_storage_account = pulumi_azuread.ServicePrincipal(
    resource_name="heifer-service-principal-for-databricks-storage-account",
    client_id=heifer_app_for_databricks_storage_account.client_id,
    owners=[CURRENT_CLIENT.object_id],
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_app_for_databricks_storage_account]
    ),
)
# D) Assign Contributor privilege on the Storage for the Service Principal
heifer_perm_service_principal_can_contribute_storage = azure_native.authorization.RoleAssignment(
    resource_name='heifer-perm-service-principal-can-contribute-storage',
    principal_id=heifer_service_principal_for_databricks_storage_account.id,
    principal_type=azure_native.authorization.PrincipalType.SERVICE_PRINCIPAL,
    # role_definition_name='Storage Blob Data Contributor',
    role_definition_id=f"/subscriptions/{CURRENT_CLIENT.subscription_id}/providers/"
                       f"Microsoft.Authorization/roleDefinitions/"
                       f"ba92f5b4-2d11-453d-a403-e96b0029c9fe",  # Storage Bl. Dt. Contr. GUID
    scope=heifer_storage_account.id,
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_service_principal_for_databricks_storage_account,
                    heifer_200_seconds_break]
    ),
)
# -------------------------------------------------------------------


# -- Databricks Service Principal for ADF --
heifer_service_principal_adf = pulumi_databricks.ServicePrincipal(
    resource_name="serpr-heifer-databricks-adf",
    application_id=HeiferConfig.DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID,
    # external_id=heifer_adf.identity.apply(lambda _identity: _identity['principal_id']),
    # acl_principal_id=heifer_adf.identity.apply(lambda _identity: _identity['principal_id']),
    display_name=f"Service Principal of Heifer ADF",
    allow_cluster_create=True,
    allow_instance_pool_create=True,
    workspace_access=True,

    opts=pulumi.ResourceOptions(
        depends_on=[heifer_private_endpoint_databricks_control_plane,
                    heifer_private_endpoint_databricks_filesystem,
                    heifer_databricks_workspace,
                    heifer_databricks_provider],
        provider=heifer_databricks_provider
    ),
)
# ------------------------------------------


# -- Allow to print info for configuration of Databricks Spark cluster --
#   Warning: this is only for development and debugging purposes
_print_spark_config_notes: bool = False
if _print_spark_config_notes:
    # You need to configure secrets in Pulumi.yaml file first
    pulumi.export("Spark version", pulumi_databricks.get_spark_version(spark_version="3.4"))
    pulumi.export(
        "Node IDs",
        pulumi_databricks.get_node_type(
            category='General Purpose', min_memory_gb=1, photon_driver_capable=False,
            photon_worker_capable=False
        )
    )
# -----------------------------------------------------------------------


# -- Integration runtime between ADF and Databricks --
heifer_adf_integration_runtime = pulumi_azure.datafactory.IntegrationRuntimeRule(
    resource_name="heifer-adf-integration-runtime",
    name="heifer-adf-integration-runtime",
    data_factory_id=heifer_adf.id,
    location=heifer_rg.location,
    virtual_network_enabled=True,
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_adf]
    ),
)
# ----------------------------------------------------


# -- Databricks Secret Scope --
heifer_databricks_secret_scope = pulumi_databricks.SecretScope(
    resource_name=HeiferConfig.DATABRICKS_SECRET_SCOPE_NAME,
    name=HeiferConfig.DATABRICKS_SECRET_SCOPE_NAME,
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_adf_integration_runtime],
        provider=heifer_databricks_provider,
    ),
)
# -----------------------------


# -- Azure Data Factory Linked Service - Azure Databricks via MSI --
heifer_link_adf_databricks = pulumi_azure.datafactory.LinkedServiceAzureDatabricks(
    resource_name='link-service-heifer-databricks-and-adf',
    name="HeiferAdfToCluster",
    adb_domain=heifer_databricks_workspace.workspace_url.apply(
        lambda _workspace_url: f'https://{_workspace_url}'
    ),
    msi_work_space_resource_id=heifer_databricks_workspace.id,
    data_factory_id=heifer_adf.id,
    new_cluster_config=pulumi_azure.datafactory.LinkedServiceAzureDatabricksNewClusterConfigArgs(
        cluster_version=HeiferClusterConfiguration.CLUSTER_VERSION,
        node_type=HeiferClusterConfiguration.NODE_TYPE,
        log_destination=HeiferClusterConfiguration.LOG_DESTINATION,
        max_number_of_workers=HeiferClusterConfiguration.MAX_NUMBER_OF_WORKERS,
        min_number_of_workers=HeiferClusterConfiguration.MIN_NUMBER_OF_WORKERS,
        spark_config=HeiferClusterConfiguration.SPARK_CONFIG | {
            # A) MANDATORY: Connection to Data lake
            f"fs.azure.account.auth.type.{HeiferConfig.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net": "OAuth",  # noqa: E501
            f"fs.azure.account.oauth.provider.type.{HeiferConfig.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net": "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",  # noqa: E501
            f"fs.azure.account.oauth2.client.id.{HeiferConfig.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net": heifer_service_principal_for_databricks_storage_account.client_id.apply(lambda _client_id: _client_id),  # noqa: E501
            f"fs.azure.account.oauth2.client.secret.{HeiferConfig.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net": heifer_app_for_databricks_storage_account_password.value.apply(lambda _value: _value),  # noqa: E501
            f"fs.azure.account.oauth2.client.endpoint.{HeiferConfig.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net": f"https://login.microsoftonline.com/{CURRENT_CLIENT.tenant_id}/oauth2/token",  # noqa: E501
            "spark.secret.datalake-uri": f"{HeiferConfig.STORAGE_ACCOUNT_NAME}.dfs.core.windows.net"  # noqa: E501
        },
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[heifer_adf,
                    heifer_private_endpoint_databricks_filesystem,
                    heifer_databricks_workspace,
                    heifer_service_principal_adf,
                    heifer_perm_service_principal_can_contribute_storage,
                    heifer_adf_serpr_role_assignment],
        custom_timeouts=pulumi.CustomTimeouts(create="30m", update="30m", delete="30m"),
    )
)
# ------------------------------------------------------------------


# ====== DATA FACTORY AND PIPELINE PROVISIONING ======
# -- Deploy all available pipelines --
for _pipeline_definition in pipelines_definitions:
    heifer_adf_pipeline = pulumi_azure.datafactory.Pipeline(
        resource_name=f"heifer-adf-pipeline-{_pipeline_definition['name']}",
        name=_pipeline_definition['name'],
        data_factory_id=heifer_adf.id,
        activities_json=json.dumps(_pipeline_definition['properties']['activities']),
        parameters={
            # Mapping: parameter_name -> default value
            _pipeline_parameter_name: _pipeline_parameter_definition['defaultValue']
            for _pipeline_parameter_name, _pipeline_parameter_definition in
            _pipeline_definition['properties']['parameters'].items()
        },
        opts=pulumi.ResourceOptions(depends_on=[heifer_200_seconds_break,
                                                heifer_link_adf_databricks]),
    )
# ------------------------------------
