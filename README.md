# HeifER
HeifER is a microservice for provisioning the Databricks cluster,
Azure Data Factory, and pipeline code management.

![alt text](assets-docs/heifer.png)

Author: David Salac, University of Liverpool

## Installation guide
Pulumi state should be stored inside an Azure Storage Account (Blob).

This Container (blob) needs to be created in advance. To do so, follow the logic:
1. Go to the Azure Portal.
2. Create a storage account:
    1. Optimally, in an independent Resource Group.
    2. Select `Enable public access from all networks` in the `Networking` tab.
    3. Un-tick all soft delete options in the `Data protection` tab (as they are useless).
3. Create a `Container` (aka blob) inside the storage account.
3. Add a `Storage Blob Data Contributor` role for yourself (or whoever is needed) for the blob:
    1. Go into the Container and click Access Control (IAM) in the left menu.
    2. Click `Add role assignment`
    3. Add yourself (or whoever is needed) as a `Storage Blob Data Contributor`.
3. Add a `Storage Blob Data Contributor` role for yourself (or whoever is needed) for the Storage Account:
    1. Use the same logic as for the blob, but on the Storage Account level.

From now on, use docker-compose environment to operate with the state.

## Local (development) stack/environment
It uses docker-compose, so make sure you have it installed and configured.

### Configure environment
First, after getting into the Docker environment, set the following environmental variables:
 - `AZURE_TENANT_ID`: Set it to Azure Tenant where things are to be deployed.
 - `PULUMI_BACKEND_URL`: Set it to `azblob://BLOB_NAME?storage_account=STORAGE_ACOUNT`
    and replace `BLOB_NAME` and `STORAGE_ACOUNT` with values from the previous step.
 - `PULUMI_CONFIG_PASSPHRASE`: stores a passphrase for deployment (optional).

### Build environment
To build an environment locally, use the command `docker-compose build`.

### Start environment
To start an environment locally, use the command `docker-compose up`; and then you
need to get inside the container. Use the logic:
1. Run the `docker ps` command to get the container info.
    - This returns you and `CONTAINER ID` for the heifer container.
2. Run the command `docker exec -ti CONTAINER_ID /bin/bash`, replace `CONTAINER_ID`
with the sequence obtained above. You should get into the bash console of the container.

### How to turn on Pulumi
From inside the Pulumi container (see the previous step):
1. Run `az login --use-device-code` and log into the Azure.
2. Select the subscription using the command `az account set -s SUBSCRIPTION_ID`
3. Run `pulumi login`

_Note: The Pulumi password for the project needs to be stored somewhere (preferably in an Azure Key vault instance).
Temporarily, the environmental variable can be used (for development)._

### How to install Pulumi's dependencies
If there are any dependencies to be installed, you need to add them
into a Python's virtual environment. Use:
```bash
source ./venv/bin/activate
```
to start the virtual environment. 
Then, use PIP to install dependencies:
```bash
pip install -r requirements.txt
```
To deactivate (get out of) a virtual environment, use:
```bash
deactivate
```

**Note:** a virtual environment should be created by Pulumi. Just write `pulumi up` on the beginning.

## Development
First of all, it is necessary to configure all variables in a config
class. These are located in `infrastructure/__main__.py` file in
classes `HeiferConfig` and `HeiferClusterConfiguration`. Some of these
variables need to be left empty for the first round of stack
(environment) building, namely:
 - `DATABRICKS_ACCOUNT_ID`: Account ID (personalised) of the
   Databricks environment.
 - `DATABRICKS_SERVICE_PRINCIPAL_FOR_ADF_APP_UUID`: ADF Managed
   Service Identity (Application ID). Find it in ADF properties tab.

Because you probably do not know the values in advance.

Once you run the first round of deployment (without the values mentioned
above), you need to add your IP as an exception into the container
`STORAGE_ACCOUNT_NAME`, as you need to access it from the VM that
runs Pulumi. Be careful to remove this exception afterwards.

### Managing pipelines
Copy your pipeline repository into `/pipelines` folder. Then build
artifacts from inside Docker container, using:
```bash
make artifacts
```
this needs to be run whenever you do any changes in the pipeline
codebase.

### Building stack (environment)
Once you set up all the variables and have pipelines ready, run:
```bash
pulumi up
```
this should (for the first time) lead you through process of the new stack creation. Then it should just build whatever changes.

Logic is smart enough to do reflect on changes only. 

Be aware that the name of the `linkedServiceName` in each
`pipeline.json` needs to match the name of the
`heifer_link_adf_databricks` resource.

## Generic notes
Full documentation of underpinning Terraform Databricks provider:
https://registry.terraform.io/providers/databricks/databricks/latest/docs

How to set up the secret for the `.yaml` files:
```bash
pulumi config set databricks:azureClientSecret "SECRET_VALUE" --secret
```

## Pipeline for unzipping BAK and unloading it to Microsoft SQL Server Managed Instance
The pipeline logically follows the flow depicted in the diagram:  
![alt text](assets-docs/bakpipeline.png)

### Network Configuration and Authentication
**Note:** Networking is primarily handled using standard tools like Virtual Network (VNET) peering and Private Endpoints. Authentication is managed via Azure AD App registrations (with client secrets) and system-assigned managed identities, each granted appropriate permissions.

**Important:** The App registration used for the SQL Server Managed Instance resource is shared across multiple pipelines.

1. Configure networking between the pre-bronze Storage Account and Azure Data Factory using the **Resource instance** exception  
   _(Storage Account → Networking → Resource instances → add ADF’s system-assigned identity)_.
2. Configure VNET peering between the Databricks instance’s virtual network and the pre-bronze Storage Account  
   _(Storage Account → Networking → Virtual networks → Add existing virtual network → select Databricks VNet + shared subnet)_.
3. Create a Private Endpoint between the pre-bronze Storage Account and the Databricks instance  
   _(Storage Account → Networking → Private endpoint connections → add Private Endpoint to the Databricks shared subnet, using default DNS settings)_.
4. Assign the **Storage Blob Data Contributor** role to the Azure Data Factory managed identity so ADF can access and unzip ZIP files.
5. Register an App in **Microsoft Entra ID** for the Databricks instance to authenticate against both the pre-bronze and landing-zone Storage Accounts.
6. Assign the **Storage Blob Data Reader** role on the landing-zone Storage Account to that App registration (use its Client ID).
7. Assign the **Storage Blob Data Owner** role on the pre-bronze container to the same App registration.
8. Generate a new client secret for this App registration and pass it in as an environment variable.
9. Register a separate App in Entra ID for managing the SQL Managed Instance resource.
10. Grant the App registration from step 9 administrative access to the SQL Managed Instance.
11. Finalize the pipeline configuration file.
12. Configure VNET peering between the Databricks VNet and the SQL Managed Instance VNet  
    _(Storage Account → Networking → Virtual networks → Add existing virtual network → select SQL MI VNet)_.
13. Configure networking between the SQL Managed Instance and the Storage Accounts using Private Endpoints and VNET peering as above.

## In-situ Fix for the Databricks File System (DBFS) Issue
Go to the `pe-heifer-databricks-filesystem` Private Endpoint resource. Click **Settings** > **DNS configuration**. Then, at the top, click **Add configuration** and select the appropriate DNS zone (deployed in the same resource group as the private endpoint).
