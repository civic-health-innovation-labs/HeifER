import os


class RioPipelineConfig:
    # If True, the pipeline for unzipping zipped files is deployed
    DEPLOY_PIPELINE: bool = bool(os.getenv("DEPLOY_RIO_PIPELINE", default="False") == "True")
    PIPELINE_NAME: str = "RioPipeline"
    # The following is either to use Username and Password: "SERVER_AUTHENTICATION" option;
    #   or to use App registration Client ID, Secret and Tenant ID: "APP_REGISTRATION" option.
    SQL_AUTHENTICATION_METHOD: str = os.getenv("RIO_SQL_AUTHENTICATION_METHOD",
                                               default="SERVER_AUTHENTICATION")
    SQL_FQDN: str = os.getenv("RIO_SQL_FQDN", default="TODO")
    SQL_DATABASE: str = os.getenv("RIO_SQL_DATABASE", default="TODO")
    # For SQL Auth
    SQL_USERNAME: str = os.getenv("RIO_SQL_USERNAME", default="TODO")
    SQL_PASSWORD: str = os.getenv("RIO_SQL_PASSWORD", default="TODO")
    # For App reg auth
    SQL_CLIENT_ID = os.getenv("RIO_SQL_CLIENT_ID", default="TODO")
    SQL_CLIENT_SECRET = os.getenv("RIO_SQL_CLIENT_SECRET", default="TODO")
    SQL_TENANT_ID = os.getenv("RIO_SQL_TENANT_ID", default="TODO")
    # Either "True" or "False" string
    SQL_STRUST_SERVER_CERTIFICATE: str = os.getenv("RIO_TRUST_SERVER_CERTIFICATE", default="False")
