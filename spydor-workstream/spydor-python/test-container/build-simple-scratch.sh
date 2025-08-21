#!/bin/bash
set -e

echo "Building simple scratch container..."

chmod +x fixed-rootfs.sh
./fixed-rootfs.sh

docker build -f Dockerfile-scratch -t hello-scratch .

rm -rf rootfs

echo "Done! Run: docker run -p 8080:8080 hello-scratch"