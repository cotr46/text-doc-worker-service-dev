# 🚀 Deployment Guide - DEV & PROD Environments

**Date:** 19 Januari 2026  
**Fix:** Reasoning Token Limit Detection  
**Affected Service:** Worker Service Only

---

## 🏗️ Environment Architecture

### DEV Environment
- **API Service:** `text-doc-api-service-dev`
  - URL: `https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app`
  - Region: `asia-southeast2` (likely)
  - Purpose: Testing and validation

- **Worker Service:** `text-doc-worker-service-dev`
  - Region: `asia-southeast2` (likely)
  - Pub/Sub Subscription: `document-processing-worker-dev` (likely)
  - Purpose: Process dev jobs

### PROD Environment
- **API Service:** `text-doc-api-service`
  - Region: `asia-southeast1`
  - Purpose: Production traffic

- **Worker Service:** `text-doc-worker-service`
  - Region: `asia-southeast1`
  - Pub/Sub Subscription: `document-processing-worker`
  - Purpose: Process production jobs

---

## 📦 What's Being Deployed

### Changed File
- `worker_service/text_model_client.py`

### Changes
1. ✅ Detect reasoning token limit (>= 2000 tokens)
2. ✅ Validate content is not empty
3. ✅ Raise exception with clear error message
4. ✅ Mark jobs as "failed" instead of "completed" with empty results

### Impact
- **API Service:** ❌ No changes needed
- **Worker Service:** ✅ Needs deployment

---

## 🔧 Deployment Steps

### Phase 1: Deploy to DEV (Do This First!)

#### Step 1: Verify Current DEV Service
```bash
# Check if dev service exists
gcloud run services list --region=asia-southeast2 | grep text-doc-worker-service-dev

# Get current dev service details
gcloud run services describe text-doc-worker-service-dev \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai
```

#### Step 2: Build DEV Image
```bash
# Navigate to worker service directory
cd worker_service

# Build Docker image for DEV
docker build -t gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:dev-latest .

# Push to Container Registry
docker push gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:dev-latest
```

#### Step 3: Deploy to DEV Cloud Run
```bash
# Deploy to DEV service
gcloud run deploy text-doc-worker-service-dev \
  --image gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:dev-latest \
  --region=asia-southeast2 \
  --project=bni-prod-dma-bnimove-ai \
  --platform=managed \
  --allow-unauthenticated \
  --memory=4Gi \
  --cpu=2 \
  --timeout=900 \
  --min-instances=1 \
  --max-instances=10 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=bni-prod-dma-bnimove-ai,GCS_BUCKET_NAME=sbp-wrapper-bucket,PUBSUB_SUBSCRIPTION=document-processing-worker-dev,FIRESTORE_DATABASE=document-processing-firestore"
```

#### Step 4: Test DEV Deployment
```bash
# Test 1: Should fail with clear error (reasoning token limit)
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'

# Get job_id from response
JOB_ID="<job_id_from_response>"

# Wait 60 seconds
sleep 60

# Check status - should be "failed" with clear error
curl "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/status/$JOB_ID"

# Expected result:
# {
#   "status": "failed",
#   "error": "CRITICAL: Model hit reasoning token limit (2000 tokens)..."
# }
```

#### Step 5: Monitor DEV (24-48 Hours)
```bash
# Check worker health
curl "https://text-doc-worker-service-dev-<hash>.a.run.app/health"

# View logs
gcloud logging read "resource.type=cloud_run_revision AND 
  resource.labels.service_name=text-doc-worker-service-dev" \
  --limit 50 \
  --project=bni-prod-dma-bnimove-ai

# Monitor error rate
gcloud logging read "resource.type=cloud_run_revision AND 
  resource.labels.service_name=text-doc-worker-service-dev AND 
  textPayload=~'reasoning token limit'" \
  --limit 20 \
  --project=bni-prod-dma-bnimove-ai
```

---

### Phase 2: Deploy to PROD (After DEV Validation!)

⚠️ **WAIT 24-48 HOURS AFTER DEV DEPLOYMENT**

#### Prerequisites
- [ ] DEV deployment successful
- [ ] DEV tests passed
- [ ] No unexpected errors in DEV
- [ ] Team approval obtained
- [ ] Deployment window scheduled

#### Step 1: Create PROD Image
```bash
# Navigate to worker service directory
cd worker_service

# Build Docker image for PROD with commit SHA
COMMIT_SHA=$(git rev-parse --short HEAD)

docker build -t gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:$COMMIT_SHA \
  -t gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:latest .

# Push both tags
docker push gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:$COMMIT_SHA
docker push gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:latest
```

#### Step 2: Update PROD YAML
```bash
# Update worker_service.yaml with new image
sed -i "s|image: .*|image: gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:$COMMIT_SHA|g" worker_service.yaml
```

#### Step 3: Deploy to PROD
```bash
# Deploy using YAML configuration
gcloud run services replace worker_service.yaml \
  --region=asia-southeast1 \
  --project=bni-prod-dma-bnimove-ai

# Or deploy directly
gcloud run deploy text-doc-worker-service \
  --image gcr.io/bni-prod-dma-bnimove-ai/document-processing-text-analysis-worker:$COMMIT_SHA \
  --region=asia-southeast1 \
  --project=bni-prod-dma-bnimove-ai \
  --platform=managed
```

#### Step 4: Verify PROD Deployment
```bash
# Check service status
gcloud run services describe text-doc-worker-service \
  --region=asia-southeast1 \
  --project=bni-prod-dma-bnimove-ai

# Check health
PROD_URL=$(gcloud run services describe text-doc-worker-service \
  --region=asia-southeast1 \
  --project=bni-prod-dma-bnimove-ai \
  --format="value(status.url)")

curl "$PROD_URL/health"
```

#### Step 5: Monitor PROD (First 24 Hours)
```bash
# Monitor logs
gcloud logging read "resource.type=cloud_run_revision AND 
  resource.labels.service_name=text-doc-worker-service" \
  --limit 100 \
  --project=bni-prod-dma-bnimove-ai

# Monitor errors
gcloud logging read "resource.type=cloud_run_revision AND 
  resource.labels.service_name=text-doc-worker-service AND 
  severity>=ERROR" \
  --limit 50 \
  --project=bni-prod-dma-bnimove-ai
```

---

## 🔄 Alternative: Using Cloud Build

### For DEV
```bash
# Trigger Cloud Build for DEV
gcloud builds submit \
  --config=worker_service/cloudbuild.yaml \
  --substitutions=_ENV=dev,_REGION=asia-southeast2 \
  worker_service/
```

### For PROD
```bash
# Trigger Cloud Build for PROD
gcloud builds submit \
  --config=worker_service/cloudbuild.yaml \
  --substitutions=_ENV=prod,_REGION=asia-southeast1 \
  worker_service/
```

---

## 📊 Monitoring Checklist

### DEV Monitoring (24-48 Hours)
- [ ] Worker service health: Healthy
- [ ] Job failure rate: Acceptable (may increase initially)
- [ ] Error messages: Clear and helpful
- [ ] No unexpected crashes
- [ ] Logs show proper error detection
- [ ] Reasoning token limit errors properly caught

### PROD Monitoring (First Week)
- [ ] Worker service health: Healthy
- [ ] Job failure rate: Within acceptable range
- [ ] No performance degradation
- [ ] Error messages helpful for users
- [ ] No unexpected issues
- [ ] Metrics tracking working

---

## 🚨 Rollback Procedures

### Rollback DEV
```bash
# Get previous revision
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

### Rollback PROD
```bash
# Get previous revision
gcloud run revisions list \
  --service=text-doc-worker-service \
  --region=asia-southeast1 \
  --project=bni-prod-dma-bnimove-ai

# Rollback to previous revision
gcloud run services update-traffic text-doc-worker-service \
  --to-revisions=<PREVIOUS_REVISION>=100 \
  --region=asia-southeast1 \
  --project=bni-prod-dma-bnimove-ai
```

---

## ✅ Deployment Checklist

### DEV Deployment
- [ ] Code changes committed
- [ ] Docker image built for DEV
- [ ] Image pushed to registry
- [ ] Deployed to DEV Cloud Run
- [ ] Health check passed
- [ ] Test Case 1 executed (should fail with clear error)
- [ ] Test Case 2 executed (normal case)
- [ ] Logs reviewed
- [ ] No unexpected errors
- [ ] Team notified

### PROD Deployment (After DEV Validation)
- [ ] DEV validated for 24-48 hours
- [ ] No issues found in DEV
- [ ] Team approval obtained
- [ ] Deployment window scheduled
- [ ] Docker image built for PROD
- [ ] Image pushed to registry
- [ ] YAML updated with new image
- [ ] Deployed to PROD Cloud Run
- [ ] Health check passed
- [ ] Smoke tests executed
- [ ] Monitoring configured
- [ ] Team notified
- [ ] Documentation updated

---

## 📞 Contacts

**Deployment Owner:** [Your Name]  
**Team Lead:** [Team Lead Name]  
**On-Call Engineer:** [On-Call Contact]  
**Escalation:** [Manager Contact]

---

## 📝 Deployment Log

### DEV Deployment
| Date | Time | Action | Result | Notes |
|------|------|--------|--------|-------|
| 2026-01-19 | - | Code committed | ⏳ | Pending |
| 2026-01-19 | - | Image built | ⏳ | Pending |
| 2026-01-19 | - | Deployed to DEV | ⏳ | Pending |
| 2026-01-19 | - | Tests executed | ⏳ | Pending |
| 2026-01-19 | - | 24h monitoring | ⏳ | Pending |

### PROD Deployment
| Date | Time | Action | Result | Notes |
|------|------|--------|--------|-------|
| - | - | DEV validated | ⏳ | Waiting for DEV |
| - | - | Approval obtained | ⏳ | Waiting for DEV |
| - | - | Deployed to PROD | ⏳ | Waiting for DEV |
| - | - | Tests executed | ⏳ | Waiting for DEV |
| - | - | Monitoring | ⏳ | Waiting for DEV |

---

**Document Version:** 1.0  
**Last Updated:** 19 Januari 2026  
**Status:** Ready for DEV Deployment
