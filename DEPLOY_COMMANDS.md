# 🚀 Quick Deploy Commands

## 📋 Environment Info

### DEV Environment
- **API Service:** `text-doc-api-service-dev`
- **Worker Service:** `text-doc-worker-service-dev`
- **Region:** `asia-southeast2` (likely)
- **URL:** `https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app`

### PROD Environment
- **API Service:** `text-doc-api-service`
- **Worker Service:** `text-doc-worker-service`
- **Region:** `asia-southeast1`
- **Project:** `bni-prod-dma-bnimove-ai`

---

## 🟢 Deploy to DEV (Do This First!)

### Quick Deploy
```bash
# 1. Navigate to worker service
cd worker_service

# 2. Build and push DEV image
docker build -t gcr.io/bni-prod-dma-bnimove-ai/text-analysis-worker:dev-latest .
docker push gcr.io/bni-prod-dma-bnimove-ai/text-analysis-worker:dev-latest

# 3. Deploy to DEV (adjust region if needed)
gcloud run deploy text-doc-worker-service-dev \
  --image gcr.io/bni-prod-dma-bnimove-ai/text-analysis-worker:dev-latest \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai \
  --memory=4Gi \
  --cpu=2 \
  --timeout=900 \
  --min-instances=1 \
  --max-instances=10

# 4. Test
curl "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'
```

### Check DEV Service
```bash
# List services
gcloud run services list --region=asia-southeast2 --project=bni-prod-dma-bnimove-ai

# Get service details
gcloud run services describe text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# View logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-dev" \
  --limit 20 \
  --project=bni-prod-dma-bnimove-ai
```

---

## 🔴 Deploy to PROD V2 (After DEV Validation!)

⚠️ **WAIT 24-48 HOURS AFTER DEV DEPLOYMENT**

### Quick Deploy
```bash
# 1. Navigate to worker service
cd worker_service

# 2. Build and push PROD V2 image
COMMIT_SHA=$(git rev-parse --short HEAD)
docker build -t gcr.io/bni-prod-dma-bnimove-ai/text-analysis-worker:v2-$COMMIT_SHA .
docker push gcr.io/bni-prod-dma-bnimove-ai/text-analysis-worker:v2-$COMMIT_SHA

# 3. Deploy to PROD V2
gcloud run deploy text-doc-worker-service-v2 \
  --image gcr.io/bni-prod-dma-bnimove-ai/text-analysis-worker:v2-$COMMIT_SHA \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai \
  --memory=4Gi \
  --cpu=2 \
  --timeout=900 \
  --min-instances=1 \
  --max-instances=10
```

### Check PROD V2 Service
```bash
# List services
gcloud run services list --region=asia-southeast2 --project=bni-prod-dma-bnimove-ai

# Get service details
gcloud run services describe text-doc-worker-service-v2 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# View logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-v2" \
  --limit 20 \
  --project=bni-prod-dma-bnimove-ai
```

---

## 🔄 Rollback Commands

### Rollback DEV
```bash
# List revisions
gcloud run revisions list \
  --service=text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai

# Rollback to previous
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

# Rollback to previous
gcloud run services update-traffic text-doc-worker-service-v2 \
  --to-revisions=<PREVIOUS_REVISION>=100 \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

---

## 🧪 Test Commands

### Test DEV
```bash
# Test PEP analysis (should fail with clear error)
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'

# Check job status
curl "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/status/<JOB_ID>"

# Check worker health
curl "https://<worker-dev-url>/health"
```

### Test PROD V2
```bash
# Test PEP analysis
curl -X POST "https://text-doc-api-service-v2-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Name", "entity_type": "person"}'

# Check job status
curl "https://text-doc-api-service-v2-lh5pr6ewdq-et.a.run.app/api/status/<JOB_ID>"

# Check worker health
curl "https://text-doc-worker-service-v2-lh5pr6ewdq-et.a.run.app/health"
```

---

## 📊 Monitoring Commands

### View Logs
```bash
# DEV logs
gcloud logging read "resource.labels.service_name=text-doc-worker-service-dev" \
  --limit 50 \
  --project=bni-prod-dma-bnimove-ai

# PROD logs (V2)
gcloud logging read "resource.labels.service_name=text-doc-worker-service-v2" \
  --limit 50 \
  --project=bni-prod-dma-bnimove-ai

# Filter for errors
gcloud logging read "resource.labels.service_name=text-doc-worker-service-v2 AND severity>=ERROR" \
  --limit 20 \
  --project=bni-prod-dma-bnimove-ai
```

### Check Metrics
```bash
# Get service metrics
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision" AND resource.labels.service_name="text-doc-worker-service-dev"' \
  --project=bni-prod-dma-bnimove-ai
```

---

## ✅ Deployment Checklist

### Before Deploy
- [ ] Code changes committed
- [ ] Tests passed locally
- [ ] Documentation updated
- [ ] Team notified

### DEV Deploy
- [ ] Build DEV image
- [ ] Push to registry
- [ ] Deploy to DEV Cloud Run
- [ ] Health check passed
- [ ] Test executed
- [ ] Logs reviewed

### PROD Deploy (After 24-48h DEV validation)
- [ ] DEV validated
- [ ] Team approval
- [ ] Build PROD image
- [ ] Push to registry
- [ ] Deploy to PROD Cloud Run
- [ ] Health check passed
- [ ] Smoke tests passed
- [ ] Monitoring active

---

**Quick Reference Version:** 1.0  
**Last Updated:** 19 Januari 2026
