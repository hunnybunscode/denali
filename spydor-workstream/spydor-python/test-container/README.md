# Hello World Python Container From Scratch

This creates a minimal Python web server container built completely from scratch with no base images.

## Files:
- `app-hello.py` - Hello World Python web server
- `Dockerfile-scratch` - FROM scratch container definition  
- `fixed-rootfs.sh` - Builds minimal Linux filesystem with Python
- `build-simple-scratch.sh` - Complete build process

## Build:

```bash
./build-simple-scratch.sh
```

## Run:
```bash
docker run -p 8080:8080 hello-scratch
```

Visit: http://localhost:8080

## What it does:
1. Creates minimal Linux filesystem with only Python runtime and required libraries
2. Builds container FROM scratch (no base image)
3. Results in ~20-30MB container vs 1GB+ traditional Python images
4. Serves "Hello World!" web page