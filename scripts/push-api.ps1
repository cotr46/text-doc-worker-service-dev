# Script to push api_service/ contents to API GitHub repo (flat structure)

Write-Host "[API] Pushing API Service to GitHub..." -ForegroundColor Green

# Temporary directory for git operations
$TEMP_DIR = Join-Path $env:TEMP "api-push-$(Get-Random)"
$API_REPO = "https://github.com/cotr46/text-doc-api-service-dev.git"

try {
    # Clone the API repo
    Write-Host "[API] Cloning API repo..." -ForegroundColor Cyan
    git clone $API_REPO $TEMP_DIR 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to clone repo" }

    # Copy api_service contents to temp dir (flat structure)
    Write-Host "[API] Copying API service files..." -ForegroundColor Cyan
    Copy-Item -Path "api_service\*" -Destination $TEMP_DIR -Recurse -Force

    # Copy shared files
    Copy-Item -Path ".dockerignore" -Destination $TEMP_DIR -ErrorAction SilentlyContinue
    Copy-Item -Path ".gitignore" -Destination $TEMP_DIR -ErrorAction SilentlyContinue
    Copy-Item -Path "Makefile" -Destination $TEMP_DIR -ErrorAction SilentlyContinue

    # Commit and push
    Push-Location $TEMP_DIR
    
    # Check if there are changes
    git add .
    $status = git status --porcelain
    if ($status) {
        Write-Host "[API] Committing changes..." -ForegroundColor Cyan
        git commit -m "Update API service from local" 2>&1 | Out-Null
        Write-Host "[API] Pushing to GitHub..." -ForegroundColor Cyan
        git push origin main
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[API] SUCCESS: Changes pushed successfully!" -ForegroundColor Green
        } else {
            throw "Failed to push to GitHub"
        }
    } else {
        Write-Host "[API] INFO: No changes to push" -ForegroundColor Yellow
    }
    
    Pop-Location
}
catch {
    Write-Host "[API] ERROR: $_" -ForegroundColor Red
    exit 1
}
finally {
    # Cleanup
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Path $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }
}
