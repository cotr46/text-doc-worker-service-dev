#!/bin/bash
# Script to push worker_service/ contents to worker GitHub repo (flat structure)

echo "🚀 Pushing Worker Service to GitHub..."

# Temporary directory for git operations
TEMP_DIR=$(mktemp -d)
WORKER_REPO="https://github.com/cotr46/text-doc-worker-service-dev.git"

# Clone the worker repo
echo "📥 Cloning worker repo..."
git clone $WORKER_REPO $TEMP_DIR

# Copy worker_service contents to temp dir (flat structure)
echo "📋 Copying worker service files..."
cp -r worker_service/* $TEMP_DIR/

# Copy shared files
cp .dockerignore $TEMP_DIR/ 2>/dev/null || true
cp .gitignore $TEMP_DIR/ 2>/dev/null || true
cp Makefile $TEMP_DIR/ 2>/dev/null || true
cp -r docs $TEMP_DIR/ 2>/dev/null || true
cp -r scripts $TEMP_DIR/ 2>/dev/null || true
cp -r tests $TEMP_DIR/ 2>/dev/null || true

# Commit and push
cd $TEMP_DIR
git add .
git commit -m "Update worker service from local"
git push origin main

# Cleanup
cd -
rm -rf $TEMP_DIR

echo "✅ Worker service pushed successfully!"
