FROM python:3.11-bookworm

ENV PATH="/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.pulumi/bin"

# Download and install Pulumi
WORKDIR /installpulumi
RUN curl -fsSL https://get.pulumi.com | sh

# Download and install AZ-cli
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Workdir for code
WORKDIR /src

# To keep the container running forever
ENTRYPOINT ["tail", "-f", "/dev/null"]