# 🤖 Auto-Deploy Configuration

**Status:** ✅ Auto-Deploy Enabled  
**Trigger:** Push to `main` branch

---

## 📋 Cloud Build Triggers yang Aktif

### DEV Environment
**Trigger Name:** `text-doc-worker-service-v2-auto-deploy-dev`
- **GitHub Repo:** `cotr46/text-doc-worker-service-dev`
- **Branch:** `main`
- **Config File:** `cloudbuild.yaml`
- **Action:** Auto-deploy to `text-doc-worker-service-dev`
- **Region:** `asia-southeast2`

### PROD Environment (V2)
**Trigger Name:** `text-doc-worker-service-v2-auto-deploy`
- **GitHub Repo:** `cotr46/text-doc-worker-service`
- **Branch:** `main`
- **Config File:** `cloudbuild.yaml`
- **Action:** Auto-deploy to `text-doc-worker-service-v2`
- **Region:** `asia-southeast2`

---

## 🚀 Cara Kerja Auto-Deploy

### Workflow
```
1. Push code ke GitHub
   ↓
2. GitHub webhook trigger Cloud Build
   ↓
3. Cloud Build runs cloudbuild.yaml
   ↓
4. Build Docker image
   ↓
5. Push to Container Registry
   ↓
6. Deploy to Cloud Run
   ↓
7. Service updated automatically
```

---

## ✅ Deployment Steps dengan Auto-Deploy

### Deploy ke DEV

#### Option 1: Push ke GitHub (Auto-Deploy) ✅ RECOMMENDED
```bash
# 1. Commit changes
git add worker_service/text_model_client.py
git add *.md
git commit -m "fix: Add reasoning token limit detection and validation

- Detect when model hits 2000 reasoning token limit
- Validate content is not empty
- Raise exception with clear error message
- Mark jobs as failed instead of completed with empty results

Fixes: NEXUS-API-001
Environment: DEV
Issue: Jobs completing with empty results"

# 2. Push to main branch of DEV repo
git push origin main

# 3. Monitor Cloud Build
gcloud builds list --project=bni-prod-dma-bnimove-ai --limit=5

# 4. Watch build logs
gcloud builds log <BUILD_ID> --project=bni-prod-dma-bnimove-ai --stream
```

#### Option 2: Manual Deploy (Jika Auto-Deploy Gagal)
```bash
cd worker_service
docker build -t asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-dev:latest .
docker push asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-dev:latest
gcloud run deploy text-doc-worker-service-dev \
  --image asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-dev:latest \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

---

### Deploy ke PROD V2

⚠️ **IMPORTANT:** Anda punya 2 GitHub repos berbeda!
- DEV: `cotr46/text-doc-worker-service-dev`
- PROD: `cotr46/text-doc-worker-service`

#### Cara Deploy ke PROD V2:

**Option A: Merge dari DEV ke PROD Repo (Recommended)**
```bash
# 1. Clone PROD repo (jika belum)
git clone https://github.com/cotr46/text-doc-worker-service.git prod-repo
cd prod-repo

# 2. Add DEV repo as remote
git remote add dev https://github.com/cotr46/text-doc-worker-service-dev.git

# 3. Fetch DEV changes
git fetch dev

# 4. Merge DEV main to PROD main
git checkout main
git merge dev/main

# 5. Push to PROD main (triggers auto-deploy)
git push origin main

# 6. Monitor deployment
gcloud builds list --project=bni-prod-dma-bnimove-ai --limit=5
```

**Option B: Manual Copy & Push**
```bash
# 1. Copy fixed file from DEV to PROD repo
cp /path/to/dev-repo/worker_service/text_model_client.py /path/to/prod-repo/worker_service/

# 2. Commit in PROD repo
cd /path/to/prod-repo
git add worker_service/text_model_client.py
git commit -m "fix: Add reasoning token limit detection (from DEV)"

# 3. Push to PROD main (triggers auto-deploy)
git push origin main
```

---

## 📊 Monitoring Auto-Deploy

### Check Build Status
```bash
# List recent builds
gcloud builds list --project=bni-prod-dma-bnimove-ai --limit=10

# Watch specific build
gcloud builds log <BUILD_ID> --project=bni-prod-dma-bnimove-ai --stream

# Check build for specific trigger
gcloud builds list \
  --filter="trigger_id=eab0d5aa-6f70-4116-863a-9b678e890b7f" \
  --project=bni-prod-dma-bnimove-ai \
  --limit=5
```

### Check Deployment Status
```bash
# DEV service status
gcloud run services describe text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# PROD V2 service status
gcloud run services describe text-doc-worker-service-v2 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# Check latest revision
gcloud run revisions list \
  --service=text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai \
  --limit=5
```

### View Build Logs in Console
```
https://console.cloud.google.com/cloud-build/builds?project=bni-prod-dma-bnimove-ai
```

---

## ⚠️ Important Notes

### 1. Separate GitHub Repositories
Anda punya **2 GitHub repos berbeda**:
- **DEV:** `cotr46/text-doc-worker-service-dev`
- **PROD:** `cotr46/text-doc-worker-service`

**Ini berarti:**
- Push ke DEV repo → Deploy ke DEV
- Push ke PROD repo → Deploy ke PROD V2
- **Tidak ada auto-sync** antara DEV dan PROD

### 2. Branch yang Di-Monitor
- **Branch:** `main` (bukan `dev` atau `master`)
- Push ke branch lain **tidak akan trigger** auto-deploy

### 3. CloudBuild.yaml Required
- Auto-deploy menggunakan `cloudbuild.yaml` di root repo
- Pastikan file ini ada dan valid

### 4. Build Time
- Build + Deploy biasanya **5-10 menit**
- Monitor progress di Cloud Build console

---

## 🔄 Recommended Workflow

### For DEV Deployment
```bash
# 1. Work in DEV repo
cd /path/to/text-doc-worker-service-dev

# 2. Make changes
# Edit worker_service/text_model_client.py

# 3. Commit and push
git add .
git commit -m "fix: reasoning token limit detection"
git push origin main

# 4. Auto-deploy triggers automatically
# Monitor: https://console.cloud.google.com/cloud-build/builds

# 5. Wait 5-10 minutes for deployment

# 6. Test
curl "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -X POST -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'
```

### For PROD V2 Deployment (After DEV Validation)
```bash
# 1. Validate DEV for 24-48 hours
# 2. Get team approval
# 3. Merge DEV changes to PROD repo
# 4. Push to PROD main branch
# 5. Auto-deploy triggers automatically
# 6. Monitor and validate
```

---

## 🚨 Troubleshooting

### Build Fails
```bash
# Check build logs
gcloud builds log <BUILD_ID> --project=bni-prod-dma-bnimove-ai

# Common issues:
# - cloudbuild.yaml syntax error
# - Docker build fails
# - Permission issues
# - Image push fails
```

### Deployment Fails
```bash
# Check Cloud Run logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-dev" \
  --limit=50 \
  --project=bni-prod-dma-bnimove-ai

# Common issues:
# - Container startup fails
# - Health check fails
# - Environment variables missing
# - Resource limits exceeded
```

### Auto-Deploy Not Triggering
```bash
# Check trigger status
gcloud builds triggers describe text-doc-worker-service-v2-auto-deploy-dev \
  --project=bni-prod-dma-bnimove-ai

# Verify:
# - Pushed to correct branch (main)
# - Pushed to correct repo
# - GitHub webhook configured
# - Trigger is enabled
```

---

## ✅ Deployment Checklist

### Before Push
- [ ] Code changes tested locally
- [ ] Commit message is clear
- [ ] Pushing to correct repo (DEV or PROD)
- [ ] Pushing to main branch

### After Push
- [ ] Cloud Build triggered
- [ ] Build completed successfully
- [ ] Deployment completed
- [ ] Health check passed
- [ ] Service is running
- [ ] Test endpoints working

### Validation
- [ ] Test with sample request
- [ ] Check logs for errors
- [ ] Monitor for 1-2 hours
- [ ] Document any issues

---

## 📞 Quick Reference

**DEV Repo:** https://github.com/cotr46/text-doc-worker-service-dev  
**PROD Repo:** https://github.com/cotr46/text-doc-worker-service  
**Cloud Build Console:** https://console.cloud.google.com/cloud-build/builds?project=bni-prod-dma-bnimove-ai  
**Cloud Run Console:** https://console.cloud.google.com/run?project=bni-prod-dma-bnimove-ai

---

**Auto-Deploy:** ✅ Enabled  
**Trigger Branch:** `main`  
**Build Time:** ~5-10 minutes  
**Last Updated:** 19 Januari 2026
