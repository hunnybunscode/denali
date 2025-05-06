ARG ARCH
FROM --platform=linux/${ARCH} ubuntu/squid:latest

# Copy custom Squid config into the container
COPY config/squid.conf /etc/squid/squid.conf

RUN apt-get update; apt-get install -y curl
RUN apt-get upgrade -y; openssl version; cat /etc/os-release
