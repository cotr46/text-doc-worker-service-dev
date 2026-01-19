# 🚀 Deploy Reasoning Token Limit Fix

**Date:** 19 Januari 2026  
**Fix:** Reasoning Token Limit Detection & Validation  
**Service:** Worker Service Only

---

## 📋 Services yang Akan Di-Deploy

### ✅ DEV (Deploy Sekarang)
- **Service:** `text-doc-worker-service-dev`
- **Region:** `asia-southeast2`
- **URL:** https://text-doc-worker-service-dev-lh5pr6ewdq-et.a.run.app

### ⏳ PROD V2 (Deploy Setelah DEV OK)
- **Service:** `text-doc-worker-service-v2`
- **Region:** `asia-southeast2`
- **URL:** https://text-doc-worker-service-v2-lh5pr6ewdq-et.a.run.app

---

## 🟢 Step 1: Deploy ke DEV

### Build & Deploy
```bash
# Navigate to worker service
cd worker_service

# Build image
docker build -t asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-dev:latest .

# Push image
docker push asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-dev:latest

# Deploy to DEV
gcloud run deploy text-doc-worker-service-dev \
  --image asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-dev:latest \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

### Test DEV
```bash
# Test PEP analysis (should fail with clear error)
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'

# Save job_id from response, then wait 60 seconds
sleep 60

# Check status (replace <JOB_ID> with actual job_id)
curl "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/status/<JOB_ID>"

# Expected: status="failed" with error about reasoning token limit
```

### Check DEV Health
```bash
# Check worker health
curl "https://text-doc-worker-service-dev-lh5pr6ewdq-et.a.run.app/health"

# View recent logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-dev" \
  --limit 20 \
  --project=bni-prod-dma-bnimove-ai
```

---

## 🔴 Step 2: Deploy ke PROD V2 (Setelah 24-48 Jam)

⚠️ **JANGAN DEPLOY KE PROD DULU!**
- Tunggu DEV validation selesai
- Monitor DEV selama 24-48 jam
- Pastikan tidak ada issue
- Dapatkan approval dari team

### Build & Deploy PROD V2
```bash
# Navigate to worker service
cd worker_service

# Build image with commit SHA
COMMIT_SHA=$(git rev-parse --short HEAD)
docker build -t asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-v2:$COMMIT_SHA .

# Push image
docker push asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-v2:$COMMIT_SHA

# Deploy to PROD V2
gcloud run deploy text-doc-worker-service-v2 \
  --image asia-southeast2-docker.pkg.dev/bni-prod-dma-bnimove-ai/cloud-run-source-deploy/text-doc-worker-service-v2:$COMMIT_SHA \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

### Test PROD V2
```bash
# Test PEP analysis
curl -X POST "https://text-doc-api-service-v2-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Name", "entity_type": "person"}'

# Check status
curl "https://text-doc-api-service-v2-lh5pr6ewdq-et.a.run.app/api/status/<JOB_ID>"

# Check worker health
curl "https://text-doc-worker-service-v2-lh5pr6ewdq-et.a.run.app/health"
```

---

## 🔄 Rollback (Jika Diperlukan)

### Rollback DEV
```bash
# List revisions
gcloud run revisions list \
  --service=text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# Rollback to previous revision
gcloud run services update-traffic text-doc-worker-service-dev \
  --to-revisions=<PREVIOUS_REVISION>=100 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

### Rollback PROD V2
```bash
# List revisions
gcloud run revisions list \
  --service=text-doc-worker-service-v2 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# Rollback to previous revision
gcloud run services update-traffic text-doc-worker-service-v2 \
  --to-revisions=<PREVIOUS_REVISION>=100 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

---

## 📊 Monitoring

### View Logs
```bash
# DEV logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-dev" \
  --limit 50 \
  --project=bni-prod-dma-bnimove-ai

# PROD V2 logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-v2" \
  --limit 50 \
  --project=bni-prod-dma-bnimove-ai

# Filter for reasoning token limit errors
gcloud logging read "resource.labels.service_name=text-doc-worker-service-dev AND textPayload=~'reasoning token limit'" \
  --limit 20 \
  --project=bni-prod-dma-bnimove-ai
```

### Check Service Status
```bash
# DEV status
gcloud run services describe text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# PROD V2 status
gcloud run services describe text-doc-worker-service-v2 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

---

## ✅ Deployment Checklist

### DEV Deployment
- [ ] Navigate to worker_service directory
- [ ] Build Docker image
- [ ] Push to Container Registry
- [ ] Deploy to text-doc-worker-service-dev
- [ ] Check health endpoint
- [ ] Test PEP analysis (should fail with clear error)
- [ ] Review logs for proper error detection
- [ ] Monitor for 24-48 hours
- [ ] Document any issues

### PROD V2 Deployment (After DEV OK)
- [ ] DEV validated successfully
- [ ] No issues found in DEV
- [ ] Team approval obtained
- [ ] Build Docker image with commit SHA
- [ ] Push to Container Registry
- [ ] Deploy to text-doc-worker-service-v2
- [ ] Check health endpoint
- [ ] Run smoke tests
- [ ] Monitor logs
- [ ] Verify no performance degradation
- [ ] Document deployment

---

## 🎯 Expected Results

### Before Fix
```json
{
  "status": "completed",
  "result": {
    "raw_response": "",
    "findings": {"status": "unknown"}
  }
}
```

### After Fix
```json
{
  "status": "failed",
  "error": "CRITICAL: Model hit reasoning token limit (2000 tokens). The model stopped mid-reasoning and returned empty content..."
}
```

---

## 📞 Support

**Issue:** Reasoning Token Limit Detection  
**Priority:** High  
**Affected Service:** Worker Service Only  
**API Service:** No changes needed

---

**Ready to Deploy:** ✅ DEV  
**Ready to Deploy:** ❌ PROD V2 (pending DEV validation)  
**Last Updated:** 19 Januari 2026
