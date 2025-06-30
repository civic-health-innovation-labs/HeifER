import os
from typing import Optional, Any
import pathlib

from config_rio import RioPipelineConfig
from config_bak_unzip_pipeline import BakUnzipPipelineConfig
from config_dataset_provisioning import DatasetProvisioningPipelineConfig


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
    AZURE_LOCATION: str = os.getenv("HEIFER_AZURE_LOCATION", default="uksouth")
    # Resource group name (where things are deployed)
    RESOURCE_GROUP: str = os.getenv("HEIFER_RESOURCE_GROUP")
    # Storage Account name for Bronze/Silver/Gold (or similar) layers
    #   Note that name for storage account is restricted: up to 24 alphanumeric chars, no hyphens
    STORAGE_ACCOUNT_NAME: str = os.getenv("HEIFER_STORAGE_ACCOUNT_NAME")
    # Concrete layers (containers) present in the storage account (typically bronze, silver, gold)
    #   Warning: this value cannot be changed easily (have functional impacts)
    STORAGE_ACCOUNT_LAYERS: set[str] = set(os.getenv("HEIFER_STORAGE_ACCOUNT_LAYERS_COMMA_SEPARATED").split(","))  # noqa: E501
    # Databricks workspace name
    DATABRICKS_WORKSPACE_NAME: str = os.getenv("HEIFER_DATABRICKS_WORKSPACE_NAME")
    # Managed resource group name for Databricks
    DATABRICKS_MANAGED_RESOURCE_GROUP_NAME: str = os.getenv("HEIFER_DATABRICKS_MANAGED_RESOURCE_GROUP_NAME")  # noqa: E501
    # Databricks secret scope name
    DATABRICKS_SECRET_SCOPE_NAME: str = os.getenv("HEIFER_DATABRICKS_SECRET_SCOPE_NAME")
    # Storage account name for Databricks filesystem (unique), is created by Databricks
    #   Note that name for storage account is restricted: up to 24 alphanumeric chars, no hyphens
    DATABRICKS_DFS_STORAGE_ACCOUNT_NAME: str = os.getenv("HEIFER_DATABRICKS_DFS_STORAGE_ACCOUNT_NAME")  # noqa: E501
    # Account ID of the Databricks user for setting up provider
    # TODO: needs to be set up after the workspace is created. To find it go to Account Console
    #   (Manage Account) from inside workspace, then click on your name (right top corner).
    DATABRICKS_ACCOUNT_ID: Optional[str] = None if (_HDAI := os.getenv("HEIFER_DATABRICKS_ACCOUNT_ID", "None")) == "None" else _HDAI  # noqa: E501
    # Unique UUID for the app registration for the Service Principal linking ADF and Workspace
    #   TODO: Find in ADF -> Properties (caption 'Managed Identity Application ID')
    DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID: Optional[str] = None if (_HDSPFAAU := os.getenv("HEIFER_DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID", "None")) == "None" else _HDSPFAAU  # noqa: E501
    # Azure Data Factory name
    AZURE_DATA_FACTORY_NAME: str = os.getenv("HEIFER_AZURE_DATA_FACTORY_NAME")
    # Name of the main Heifers virtual network
    VIRTUAL_NETWORK_NAME: str = os.getenv("HEIFER_VIRTUAL_NETWORK_NAME")
    # Network address prefix for virtual network (must differs from others)
    VIRTUAL_NETWORK_ADDRESS_SPACE: str = f"{os.getenv('HEIFER_VIRTUAL_NETWORK_ADDRESS_SPACE_PREFIX')}.0.0/22"  # noqa: E501
    # There is a need to define subnets for shared, databricks host, and databricks container.
    #   - use any online Subnet Calculator to find a plausible values.
    VIRTUAL_NETWORK_SUBNETS_ADDRESS_SPACES: dict[str, str] = {
        "shared_subnet": f"{os.getenv('HEIFER_VIRTUAL_NETWORK_ADDRESS_SPACE_PREFIX')}.0.0/24",
        "databricks_host_subnet": f"{os.getenv('HEIFER_VIRTUAL_NETWORK_ADDRESS_SPACE_PREFIX')}.1.0/24",  # noqa: E501
        "databricks_container_subnet": f"{os.getenv('HEIFER_VIRTUAL_NETWORK_ADDRESS_SPACE_PREFIX')}.2.0/24",  # noqa: E501
    }
    # Path to directory with pipelines from inside Docker (DO NOT CHANGE UNLESS YOU KNOW)
    PATH_TO_PIPELINES: pathlib.Path = pathlib.Path("../pipelines")
    # This is the relative path to folder which content is upload as files to DBFS.
    #   (DO NOT CHANGE UNLESS YOU KNOW)
    PATH_TO_PIPELINES_UPLOAD_FOLDER: pathlib.Path = pathlib.Path("artifacts")
    # Decide whether to upload libraries (artifacts content)
    # TODO: Set to False on the first round, add your IP exception to the Storage Account Firewall
    #  rules before running. Also, check if the content of files is not empty (like __init__.py)
    UPLOAD_LIBRARIES: bool = bool(os.getenv("HEIFER_UPLOAD_LIBRARIES", default="False") == "True")


class HeiferClusterConfiguration:
    """Configuration for the Spark (PySpark) job cluster.
    Note:
        To see the configuration options for Pulumi, visit the website:
https://www.pulumi.com/registry/packages/azure/api-docs/datafactory/linkedserviceazuredatabricks/
    """
    # Spark version, as an output of: pulumi_databricks.get_spark_version()
    CLUSTER_VERSION: str = os.getenv("HEIFER_CLUSTER_VERSION", "16.4.x-scala2.13")
    # Define auto scaling option for the cluster (minimum and maximum workers)
    MIN_NUMBER_OF_WORKERS: int = int(os.getenv("HEIFER_MIN_NUMBER_OF_WORKERS", "2"))
    MAX_NUMBER_OF_WORKERS: int = int(os.getenv("HEIFER_MAX_NUMBER_OF_WORKERS", "8"))
    # Node type ID as an output of the command:
    # pulumi_databricks.get_node_type(category='General Purpose', min_memory_gb=16, min_cores=4,
    #                                 photon_driver_capable=True, photon_worker_capable=True)
    NODE_TYPE: str = os.getenv("HEIFER_NODE_TYPE", "Standard_D4as_v5")
    # Location for storing cluster's logs (must be in DBFS)
    LOG_DESTINATION: Optional[str] = "dbfs:/logs"
    # Secrets definition for Spark cluster, follows the logic:
    #   https://learn.microsoft.com/en-us/azure/databricks/security/secrets/secrets
    #   ones listed here are merged with system ones later (in cluster definition)
    SPARK_CONFIG: Optional[dict[str, Any]] = {
        # A) MANDATORY: link to TRE workspace for Dataset provisioning (TRE-related)
        "spark.secret.workspace-tenant-id": DatasetProvisioningPipelineConfig.WORKSPACE_TENANT_ID,
        "spark.secret.workspace-app-id": DatasetProvisioningPipelineConfig.WORKSPACE_CLIENT_ID,
        "spark.secret.workspace-app-secret": DatasetProvisioningPipelineConfig.WORKSPACE_CLIENT_SECRET,  # noqa: E501
        # B) MANDATORY: Enable change data feed
        "spark.databricks.delta.properties.defaults.enableChangeDataFeed": True,
        # TODO: C) MANDATORY- Configuration of the SQL Server Connection
        "spark.secret.rio-database-fqdn": RioPipelineConfig.SQL_FQDN,  # noqa: E501
        "spark.secret.rio-database-trust-server-certificate": RioPipelineConfig.SQL_STRUST_SERVER_CERTIFICATE,  # noqa: E501
        "spark.secret.rio-authentication_method": RioPipelineConfig.SQL_AUTHENTICATION_METHOD,
        "spark.secret.rio-database-database": RioPipelineConfig.SQL_DATABASE,  # noqa: E501
        # For SQL Auth method
        "spark.secret.rio-database-username": RioPipelineConfig.SQL_USERNAME,  # noqa: E501
        "spark.secret.rio-database-password": RioPipelineConfig.SQL_PASSWORD,  # noqa: E501
        # For AAD auth method
        "spark.secret.rio-app-registration-client-id": RioPipelineConfig.SQL_CLIENT_ID,
        "spark.secret.rio-app-registration-client-secret": RioPipelineConfig.SQL_CLIENT_SECRET,
        "spark.secret.rio-app-registration-tenant-id": RioPipelineConfig.SQL_TENANT_ID,
        # TODO: D) OPTIONAL- Only important if bak unloading is requested.
        "spark.secret.landing-zip-storage-account": BakUnzipPipelineConfig.LANDING_ZIP_STORAGE_ACCOUNT,  # noqa: E501
        "spark.secret.landing-zip-storage-container": BakUnzipPipelineConfig.LANDING_ZIP_CONTAINER,  # noqa: E501

        "spark.secret.pre-bronze-storage-account": BakUnzipPipelineConfig.PRE_BRONZE_STORAGE_ACCOUNT,  # noqa: E501
        "spark.secret.pre-bronze-zipped-bak-dataset-container": BakUnzipPipelineConfig.PRE_BRONZE_ZIPPED_BAK_DATASET_CONTAINER,  # noqa: E501
        "spark.secret.pre_bronze_zipped_bak_dataset_file_name": BakUnzipPipelineConfig.PRE_BRONZE_ZIPPED_BAK_DATASET_FILE_NAME,  # noqa: E501

        "spark.secret.pre-bronze-unzipped-bak-dataset-container": BakUnzipPipelineConfig.PRE_BRONZE_UNZIPPED_BAK_DATASET_CONTAINER,  # noqa: E501
        "spark.secret.pre-bronze-unzipped-bak-dataset-folder-path": BakUnzipPipelineConfig.PRE_BRONZE_UNZIPPED_BAK_DATASET_FOLDER_PATH,  # noqa: E501

        "spark.secret.pre-bronze-tenant": BakUnzipPipelineConfig.PRE_BRONZE_APP_TENANT,  # noqa: E501
        "spark.secret.pre-bronze-client-id": BakUnzipPipelineConfig.PRE_BRONZE_CLIENT_ID,  # noqa: E501
        "spark.secret.pre-bronze-client-secret": BakUnzipPipelineConfig.PRE_BRONZE_CLIENT_SECRET,  # noqa: E501

        "spark.secret.managed-instance-fqdn": BakUnzipPipelineConfig.SQL_MI_FQDN,  # noqa: E501
        "spark.secret.managed-instance-database-name": BakUnzipPipelineConfig.SQL_MI_DATABASE,  # noqa: E501
        "spark.secret.managed-instance-app-tenant": BakUnzipPipelineConfig.SQL_MI_APP_TENANT,  # noqa: E501
        "spark.secret.managed-instance-app-client-id": BakUnzipPipelineConfig.SQL_MI_APP_CLIENT_ID,  # noqa: E501
        "spark.secret.managed-instance-app-client-secret": BakUnzipPipelineConfig.SQL_MI_APP_CLIENT_SECRET,  # noqa: E501
    }
