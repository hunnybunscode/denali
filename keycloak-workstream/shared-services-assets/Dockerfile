ARG BASE_ARCH=amd64
ARG BASE_OS=linux

ARG BASE_REGISTRY=registry.access.redhat.com
ARG BASE_IMAGE=ubi9/ubi
ARG BASE_TAG=latest

FROM --platform=${BASE_OS}/${BASE_ARCH} ${BASE_REGISTRY}/${BASE_IMAGE}:${BASE_TAG}

ARG USERNAME=container
ARG USER_UID=1000
ARG USER_GUID=1000

ARG UPDATE_OS=false 

# Override Python and NodeJS Trust Store to OS Trust Store (RHEL Location)
ENV NODE_EXTRA_CA_CERTS=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
ENV REQUESTS_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

ARG USER_HOME_DIR=/home/${USERNAME}
ARG WORKSPACE_DIR=${USER_HOME_DIR}/workspace

# Disable Go Proxy
ENV GOPROXY=direct

# Disable Docker build auto progress
ENV BUILDKIT_PROGRESS=plain

# Setup Build Environment
COPY ./docker/scripts /tmp
WORKDIR /tmp

USER root

RUN chmod +x *.sh &&\
  ./install_dev.sh &&\
  ./create_user.sh &&\
  cp --preserve=mode,timestamps configure_user.sh /home/${USERNAME} &&\
  ./clean.sh 

# Create Workspace
RUN mkdir -p ${WORKSPACE_DIR}
COPY . ${WORKSPACE_DIR}
WORKDIR ${WORKSPACE_DIR}

RUN chown -R ${USERNAME}:${USERNAME} ${WORKSPACE_DIR}

USER ${USERNAME}
ENV USER=${USERNAME}

WORKDIR ${USER_HOME_DIR}
RUN ./configure_user.sh && rm -f configure_user.sh

WORKDIR ${WORKSPACE_DIR}
RUN npm ci
RUN npx run fetch

# WORKDIR ${WORKSPACE_DIR}/node_modules/cdk-ecr-deployment/lambda
# RUN node install.js ${WORKSPACE_DIR}/node_modules/cdk-ecr-deployment/lambda/out

USER root
WORKDIR ${WORKSPACE_DIR}

ENTRYPOINT [ "/bin/bash" ]
#checkov:skip=CKV_DOCKER_2:HEALTHCHECK not needed, not a service container
