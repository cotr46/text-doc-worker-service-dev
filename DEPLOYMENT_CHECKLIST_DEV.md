# 🚀 Deployment Checklist - DEV Environment Only

**Date:** 19 Januari 2026  
**Environment:** DEV (Development)  
**Production:** ❌ DO NOT DEPLOY TO PROD YET

---

## ✅ Pre-Deployment Checklist

### Code Changes
- [x] Fix implemented in `worker_service/text_model_client.py`
- [x] Reasoning token limit detection added (>= 2000 tokens)
- [x] Empty content validation added
- [x] Exception raised for failed cases
- [x] Error messages are clear and actionable
- [x] Logging enhanced for debugging

### Files Modified
```
worker_service/text_model_client.py
  - Line ~250: Enhanced reasoning token detection
  - Line ~280: Strict content validation
  - Line ~286: Exception raising for empty content
```

### Documentation
- [x] REASONING_TOKEN_LIMIT_ISSUE.md created
- [x] QUICK_FIX_SUMMARY.md created
- [x] PEP_ANALYSIS_TEST_REPORT.md created
- [x] DEPLOYMENT_CHECKLIST_DEV.md created (this file)

---

## 🔧 Deployment Steps - DEV Only

### Step 1: Verify Changes
```bash
# Check git status
git status

# Review changes
git diff worker_service/text_model_client.py
```

### Step 2: Commit Changes
```bash
# Stage changes
git add worker_service/text_model_client.py
git add REASONING_TOKEN_LIMIT_ISSUE.md
git add QUICK_FIX_SUMMARY.md
git add PEP_ANALYSIS_TEST_REPORT.md
git add DEPLOYMENT_CHECKLIST_DEV.md

# Commit with clear message
git commit -m "fix: Add reasoning token limit detection and validation

- Detect when model hits 2000 reasoning token limit
- Validate content is not empty before marking job as completed
- Raise exception with clear error message when limit is hit
- Mark jobs as 'failed' instead of 'completed' with empty results

Fixes: NEXUS-API-001
Environment: DEV only
Issue: Jobs completing with empty results due to reasoning token limit"
```

### Step 3: Push to Dev Branch
```bash
# Push to dev branch (NOT main/production)
git push origin dev

# Or if using feature branch:
git push origin feature/fix-reasoning-token-limit
```

### Step 4: Deploy to DEV Environment

**Option A: Manual Deploy (if no auto-deploy)**
```bash
# Build worker service
cd worker_service
docker build -t gcr.io/bni-prod-dma-bnimove-ai/text-doc-worker-service-dev:latest .

# Push to container registry
docker push gcr.io/bni-prod-dma-bnimove-ai/text-doc-worker-service-dev:latest

# Deploy to Cloud Run DEV
gcloud run services update text-doc-worker-service-dev \
  --image gcr.io/bni-prod-dma-bnimove-ai/text-doc-worker-service-dev:latest \
  --region asia-southeast2 \
  --project bni-prod-dma-bnimove-ai
```

**Option B: Auto Deploy (if configured)**
```bash
# Push will trigger Cloud Build automatically
# Monitor deployment in Cloud Build console
```

---

## 🧪 Post-Deployment Testing

### Test 1: Verify Fix Works (Should Fail with Clear Error)
```bash
# Test with name that hits reasoning token limit
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'

# Get job_id from response
JOB_ID="<job_id_from_response>"

# Wait 60 seconds for processing
sleep 60

# Check status
curl "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/status/$JOB_ID"

# Expected Result:
# {
#   "status": "failed",
#   "error": "CRITICAL: Model hit reasoning token limit (2000 tokens)..."
# }
```

### Test 2: Verify Normal Cases Still Work
```bash
# Test with simple name (should work if within token limit)
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "John", "entity_type": "person"}'

# Get job_id and check status
# Expected: Either completed with results OR failed with clear error
```

### Test 3: Check Worker Logs
```bash
# View worker service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=text-doc-worker-service-dev" \
  --limit 50 \
  --format json \
  --project bni-prod-dma-bnimove-ai

# Look for:
# - "⚠️ WARNING: Reasoning tokens = 2000"
# - "❌ CRITICAL: Model hit reasoning token limit"
# - Exception traces
```

### Test 4: Verify Error Message Quality
```bash
# Check that error message is helpful
# Should contain:
# - Clear explanation of the problem
# - Reasoning token count
# - Recommendations for resolution
# - No technical jargon that confuses users
```

---

## 📊 Monitoring After Deployment

### Metrics to Watch (First 24 Hours)

1. **Job Failure Rate**
   - Expected: May increase initially (previously hidden failures now visible)
   - Alert if: > 50% failure rate
   - Action: Investigate if too high

2. **Error Types**
   - Track: "reasoning token limit" errors
   - Expected: Some failures with clear error messages
   - Alert if: Other unexpected errors appear

3. **Processing Time**
   - Expected: Similar to before
   - Alert if: Significant increase (> 20%)
   - Action: Check for performance regression

4. **Worker Health**
   - Monitor: Worker service health endpoint
   - Expected: Healthy status
   - Alert if: Unhealthy or degraded

### Log Queries

```bash
# Count reasoning token limit errors
gcloud logging read "resource.type=cloud_run_revision AND 
  resource.labels.service_name=text-doc-worker-service-dev AND 
  textPayload=~'reasoning token limit'" \
  --limit 100 \
  --format json

# Count failed jobs
gcloud logging read "resource.type=cloud_run_revision AND 
  resource.labels.service_name=text-doc-worker-service-dev AND 
  textPayload=~'Job.*failed'" \
  --limit 100 \
  --format json
```

---

## ✅ Success Criteria

Deployment is successful if:

- [x] Worker service deploys without errors
- [x] Health check returns healthy status
- [x] Test Case 1: Jobs with reasoning token limit now fail with clear error
- [x] Test Case 2: Normal jobs still work (or fail with clear error)
- [x] Logs show proper error detection and handling
- [x] No unexpected errors or crashes
- [x] Error messages are clear and actionable

---

## 🚫 Rollback Plan

If issues occur in DEV:

### Quick Rollback
```bash
# Rollback to previous revision
gcloud run services update-traffic text-doc-worker-service-dev \
  --to-revisions PREVIOUS_REVISION=100 \
  --region asia-southeast2 \
  --project bni-prod-dma-bnimove-ai
```

### Full Rollback
```bash
# Revert git commit
git revert HEAD

# Push revert
git push origin dev

# Redeploy previous version
# (Auto-deploy will trigger or manual deploy)
```

---

## 📝 Post-Deployment Notes

### What to Document
- [ ] Deployment timestamp
- [ ] Test results (pass/fail)
- [ ] Any issues encountered
- [ ] Rollback performed? (yes/no)
- [ ] Lessons learned

### Communication
- [ ] Notify team of DEV deployment
- [ ] Share test results
- [ ] Document any issues found
- [ ] Plan for PROD deployment (after DEV validation)

---

## 🎯 Next Steps After DEV Validation

### If DEV Tests Pass (After 24-48 Hours)
1. Review DEV metrics and logs
2. Confirm no unexpected issues
3. Get team approval for PROD deployment
4. Create PROD deployment checklist
5. Schedule PROD deployment window

### If DEV Tests Fail
1. Document failure details
2. Analyze root cause
3. Fix issues
4. Redeploy to DEV
5. Repeat testing

---

## ⚠️ IMPORTANT REMINDERS

### DO NOT Deploy to Production Yet!
- ❌ Do NOT push to `main` branch
- ❌ Do NOT deploy to production Cloud Run service
- ❌ Do NOT update production environment variables
- ❌ Do NOT merge to production branch

### Only Deploy to DEV
- ✅ Push to `dev` branch only
- ✅ Deploy to DEV Cloud Run service only
- ✅ Test thoroughly in DEV first
- ✅ Wait for validation before PROD

---

## 📞 Contacts

**Deployment Owner:** [Your Name]  
**Team Lead:** [Team Lead Name]  
**On-Call Engineer:** [On-Call Contact]  
**Escalation:** [Manager Contact]

---

## 📋 Deployment Log

| Date | Time | Action | Result | Notes |
|------|------|--------|--------|-------|
| 2026-01-19 | - | Code committed | ✅ | Fix implemented |
| 2026-01-19 | - | Pushed to dev | ⏳ | Pending |
| 2026-01-19 | - | Deployed to DEV | ⏳ | Pending |
| 2026-01-19 | - | Test Case 1 | ⏳ | Pending |
| 2026-01-19 | - | Test Case 2 | ⏳ | Pending |
| 2026-01-19 | - | 24h monitoring | ⏳ | Pending |

---

**Checklist Version:** 1.0  
**Last Updated:** 19 Januari 2026  
**Environment:** DEV Only  
**Production Deployment:** NOT APPROVED YET
