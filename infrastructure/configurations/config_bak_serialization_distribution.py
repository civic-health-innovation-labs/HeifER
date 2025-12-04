import os
from .config_bak_unzip_pipeline import BakUnzipPipelineConfig


class BakSerializationDistributionConfig(BakUnzipPipelineConfig):
    """To configure pipeline for processing zipped bak file in a Landing Zone
        and then distributing serialized SQL tables as Parquet files.
    Note:
        Networking configuration for the Storage Account:
        1. Assign `Storage Blob Data Contributor` to the ADF managed identity
           (copy the ID in `Managed identities` tab).
        2. Select `	Enabled from selected virtual networks and IP addresses`.
        3. Add `Resource instances` in networking; select the correct ADF.
        4. Assign App Registration role of Storage Blob Data Contributor within all
            destination containers.
        5. Add Virtual Network exception for all target Storage Accounts targeting
            HeifER Virtual Network.
    """
    # If True, the pipeline for unzipping zipped files is deployed
    DEPLOY_PIPELINE: bool = bool(os.getenv("DEPLOY_BAK_SERIALIZATION_PIPELINE", default="False") == "True")
    PIPELINE_NAME: str = "BakSerializationDistribution"
    
    # D) Configuration of temporary and target storage accounts
    TEMP_ACCOUNT_CONTAINER: str = os.getenv("SERIALIZATION_TEMP_ACCOUNT_CONTAINER", default="TODO")
    # Separated by a '|' symbol. Vertical-bar separated list of URLs following the logic:
    #   https://<STORAGE_ACCOUNT>.blob.core.windows.net/<CONTAINER>/<PATH>
    TARGET_STORAGE_ACCOUNTS_URLS: str = os.getenv("SERIALIZATION_TARGET_STORAGE_ACCOUNTS_URLS", default="TODO")
