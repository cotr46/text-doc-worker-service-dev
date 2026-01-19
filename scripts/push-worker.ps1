# Script to push worker_service/ contents to worker GitHub repo (flat structure)

Write-Host "[WORKER] Pushing Worker Service to GitHub..." -ForegroundColor Green

# Temporary directory for git operations
$TEMP_DIR = Join-Path $env:TEMP "worker-push-$(Get-Random)"
$WORKER_REPO = "https://github.com/cotr46/text-doc-worker-service-dev.git"

try {
    # Clone the worker repo
    Write-Host "[WORKER] Cloning worker repo..." -ForegroundColor Cyan
    git clone $WORKER_REPO $TEMP_DIR 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to clone repo" }

    # Copy worker_service contents to temp dir (flat structure)
    Write-Host "[WORKER] Copying worker service files..." -ForegroundColor Cyan
    Copy-Item -Path "worker_service\*" -Destination $TEMP_DIR -Recurse -Force

    # Copy shared files
    Copy-Item -Path ".dockerignore" -Destination $TEMP_DIR -ErrorAction SilentlyContinue
    Copy-Item -Path ".gitignore" -Destination $TEMP_DIR -ErrorAction SilentlyContinue
    Copy-Item -Path "Makefile" -Destination $TEMP_DIR -ErrorAction SilentlyContinue
    Copy-Item -Path "docs" -Destination $TEMP_DIR -Recurse -ErrorAction SilentlyContinue
    Copy-Item -Path "scripts" -Destination $TEMP_DIR -Recurse -ErrorAction SilentlyContinue
    Copy-Item -Path "tests" -Destination $TEMP_DIR -Recurse -ErrorAction SilentlyContinue

    # Commit and push
    Push-Location $TEMP_DIR
    
    # Check if there are changes
    git add .
    $status = git status --porcelain
    if ($status) {
        Write-Host "[WORKER] Committing changes..." -ForegroundColor Cyan
        git commit -m "Update worker service from local" 2>&1 | Out-Null
        Write-Host "[WORKER] Pushing to GitHub..." -ForegroundColor Cyan
        git push origin main
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[WORKER] SUCCESS: Changes pushed successfully!" -ForegroundColor Green
        } else {
            throw "Failed to push to GitHub"
        }
    } else {
        Write-Host "[WORKER] INFO: No changes to push" -ForegroundColor Yellow
    }
    
    Pop-Location
}
catch {
    Write-Host "[WORKER] ERROR: $_" -ForegroundColor Red
    exit 1
}
finally {
    # Cleanup
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Path $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
    }
}
