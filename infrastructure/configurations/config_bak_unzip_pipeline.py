import os


class BakUnzipPipelineConfig:
    """To configure pipeline for unzipping files in a given folder (for loading bak files).
    Note:
        Networking configuration for the Storage Account:
        1. Assign `Storage Blob Data Contributor` to the ADF managed identity
           (copy the ID in `Managed identities` tab).
        2. Select `	Enabled from selected virtual networks and IP addresses`.
        3. Add `Resource instances` in networking; select the correct ADF.
    """
    # If True, the pipeline for unzipping zipped files is deployed
    DEPLOY_PIPELINE: bool = bool(os.getenv("DEPLOY_BAK_UNZIP_PIPELINE", default="False") == "True")
    PIPELINE_NAME: str = "BakToManagedSQL"

    # A) LANDING ZONE ACCESS CONFIGURATION
    LANDING_ZIP_STORAGE_ACCOUNT: str = os.getenv("BAK_UNZIP_LANDING_ZIP_STORAGE_ACCOUNT", default="TODO")  # noqa
    LANDING_ZIP_CONTAINER: str = os.getenv("BAK_UNZIP_LANDING_ZIP_CONTAINER", default="TODO")  # noqa

    # B) PRE-BRONZE (TEMPORARY STORAGE) CONFIGURATION
    # Where is the Zipped file/files located (storage account, container and the exact file name)
    PRE_BRONZE_STORAGE_ACCOUNT: str = os.getenv("BAK_UNZIP_PRE_BRONZE_STORAGE_ACCOUNT", default="TODO")  # noqa
    PRE_BRONZE_ZIPPED_BAK_DATASET_CONTAINER: str = os.getenv("BAK_UNZIP_PRE_BRONZE_ZIPPED_BAK_DATASET_CONTAINER", default="TODO")  # noqa
    PRE_BRONZE_ZIPPED_BAK_DATASET_FILE_NAME: str = os.getenv("BAK_UNZIP_PRE_BRONZE_ZIPPED_BAK_DATASET_FILE_NAME", default="TODO")  # noqa

    # Where should be the file extracted (storage account, container and destination folder)
    PRE_BRONZE_UNZIPPED_BAK_DATASET_STORAGE_ACCOUNT: str = os.getenv("BAK_UNZIP_PRE_BRONZE_UNZIPPED_BAK_DATASET_STORAGE_ACCOUNT", default="TODO")  # noqa
    PRE_BRONZE_UNZIPPED_BAK_DATASET_CONTAINER: str = os.getenv("BAK_UNZIP_PRE_BRONZE_UNZIPPED_BAK_DATASET_CONTAINER", default="TODO")  # noqa
    # The file will be extracted into the folder with the name of the zipped file and inside
    PRE_BRONZE_UNZIPPED_BAK_DATASET_FOLDER_PATH: str = os.getenv("BAK_UNZIP_PRE_BRONZE_UNZIPPED_BAK_DATASET_FOLDER_PATH", default="TODO")  # noqa

    # Has Blob Owner permissions on pre-bronze and Blob Reader perms on landing zone
    PRE_BRONZE_APP_TENANT: str = os.getenv("BAK_UNZIP_PRE_BRONZE_APP_TENANT", default="TODO")  # noqa
    PRE_BRONZE_CLIENT_ID: str = os.getenv("BAK_UNZIP_PRE_BRONZE_CLIENT_ID", default="TODO")  # noqa
    PRE_BRONZE_CLIENT_SECRET: str = os.getenv("BAK_UNZIP_PRE_BRONZE_CLIENT_SECRET", default="TODO")  # noqa

    # C) MANAGED INSTANCE CONFIGURATION
    SQL_MI_FQDN: str = os.getenv("BAK_UNZIP_SQL_MI_FQDN", default="TODO")  # noqa
    SQL_MI_DATABASE: str = os.getenv("BAK_UNZIP_SQL_MI_DATABASE", default="TODO")  # noqa
    # To authenticate to the Database (using App Registration credentials)
    SQL_MI_APP_TENANT: str = os.getenv("BAK_UNZIP_SQL_MI_APP_TENANT", default="TODO")  # noqa
    SQL_MI_APP_CLIENT_ID: str = os.getenv("BAK_UNZIP_SQL_MI_APP_CLIENT_ID", default="TODO")  # noqa
    SQL_MI_APP_CLIENT_SECRET: str = os.getenv("BAK_UNZIP_SQL_MI_APP_CLIENT_SECRET", default="TODO")  # noqa
