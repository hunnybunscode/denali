#!/bin/bash
set -e

# Create basic structure
mkdir -p rootfs/{lib64,usr/lib,usr/lib64,usr/bin,etc}

# Copy Python
cp /usr/bin/python3 rootfs/usr/bin/python3

# Copy essential libs from your system
cp /lib64/ld-linux-x86-64.so.2 rootfs/lib64/
cp /lib64/libpython3.9.so.1.0 rootfs/lib64/
cp /lib64/libc.so.6 rootfs/lib64/
cp /lib64/libm.so.6 rootfs/lib64/
cp /usr/lib64/libcrypto.so.3 rootfs/lib64/
cp /usr/lib64/libssl.so.3 rootfs/lib64/
cp /usr/lib64/libz.so.1 rootfs/lib64/

# Copy Python stdlib
cp -r /usr/lib/python3.9 rootfs/usr/lib/
cp -r /usr/lib64/python3.9 rootfs/usr/lib64/

echo "root:x:0:0:root:/:/bin/sh" > rootfs/etc/passwd