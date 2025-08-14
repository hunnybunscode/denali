#!/bin/sh

# exit when any command fails
set -e

echo "Creating user: $USERNAME"

groupadd --gid $USER_GUID $USERNAME

useradd \
  --create-home $USERNAME \
  --gid $USER_GUID \
  --uid $USER_UID \
  --comment "Docker created user"

# Restrict sudoer access to the user
echo "%$USERNAME ALL=(root) NOPASSWD: /usr/bin/update-ca-trust" >> /etc/sudoers
