FROM ubuntu/squid:latest

# Copy custom Squid config into the container
COPY config/squid.conf /etc/squid/squid.conf

RUN apt-get update; apt-get install -y curl

# Expose Squid proxy port
EXPOSE 3128
