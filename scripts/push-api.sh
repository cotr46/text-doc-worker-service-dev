#!/bin/bash
# Script to push api_service/ contents to API GitHub repo (flat structure)

echo "🚀 Pushing API Service to GitHub..."

# Temporary directory for git operations
TEMP_DIR=$(mktemp -d)
API_REPO="https://github.com/cotr46/text-doc-api-service-dev.git"

# Clone the API repo
echo "📥 Cloning API repo..."
git clone $API_REPO $TEMP_DIR

# Copy api_service contents to temp dir (flat structure)
echo "📋 Copying API service files..."
cp -r api_service/* $TEMP_DIR/

# Copy shared files
cp .dockerignore $TEMP_DIR/ 2>/dev/null || true
cp .gitignore $TEMP_DIR/ 2>/dev/null || true
cp Makefile $TEMP_DIR/ 2>/dev/null || true

# Commit and push
cd $TEMP_DIR
git add .
git commit -m "Update API service from local"
git push origin main

# Cleanup
cd -
rm -rf $TEMP_DIR

echo "✅ API service pushed successfully!"
