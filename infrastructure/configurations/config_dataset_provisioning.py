import os


class DatasetProvisioningPipelineConfig:
    DEPLOY_PIPELINE: bool = bool(os.getenv("DEPLOY_DATASET_PROVISIONING_PIPELINE", default="False") == "True")  # noqa
    PIPELINE_NAME: str = "DatasetProvisioning"

    WORKSPACE_TENANT_ID: str = os.getenv("DATASET_PROVISIONING_TENANT_ID", default="TODO")
    WORKSPACE_CLIENT_ID: str = os.getenv("DATASET_PROVISIONING_WORKSPACE_CLIENT_ID", default="TODO")  # noqa
    WORKSPACE_CLIENT_SECRET: str = os.getenv("DATASET_PROVISIONING_WORKSPACE_CLIENT_SECRET", default="TODO")  # noqa
