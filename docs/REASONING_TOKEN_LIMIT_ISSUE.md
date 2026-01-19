# 🚨 Reasoning Token Limit Issue - Critical Bug Fix

**Issue ID:** NEXUS-API-001  
**Severity:** Critical  
**Status:** Fixed  
**Date:** 19 Januari 2026

---

## 📋 Problem Summary

Text analysis jobs (PEP analysis, negative news, law involvement) complete successfully but return **empty results** due to Nexus API reasoning token limit.

### Symptoms
- Job status: `completed` ✅
- Response: `raw_response: ""` (empty) ❌
- Findings: All fields empty/null ❌
- No error message ❌
- Client receives "Analysis completed" but no actual data ❌

---

## 🔍 Root Cause Analysis

### Technical Details

**Nexus API Limitation:**
- Hard limit: **2000 reasoning tokens**
- Model uses reasoning mode for complex analysis
- When limit is hit, model stops mid-reasoning
- API returns HTTP 200 with empty content
- No error is raised by the API

**What Happens:**

```
1. Client submits: "Juhana S.E" for PEP analysis
   ↓
2. API Service creates job and publishes to Pub/Sub
   ↓
3. Worker Service picks up job
   ↓
4. Text Model Client calls Nexus API
   ↓
5. Model starts reasoning process
   ↓
6. Model uses 2000 reasoning tokens (HIT LIMIT!)
   ↓
7. Model stops mid-reasoning, cannot generate output
   ↓
8. Nexus API returns: HTTP 200, content: ""
   ↓
9. Worker marks job as "completed" (no error detected)
   ↓
10. Client receives empty result ❌
```

### Evidence from Logs

**Job ID:** `723009c7-57b6-4837-9543-d2b30141ff37`

```json
{
  "status": "completed",
  "result": {
    "raw_response": "",
    "parsed_result": {},
    "findings": {
      "status": "unknown",
      "summary": "Analysis completed",
      "details": [],
      "sources": []
    },
    "metadata": {
      "usage": {
        "prompt_tokens": 3641,
        "completion_tokens": 2000,
        "completion_tokens_details": {
          "reasoning_tokens": 2000  // ⚠️ HIT LIMIT!
        }
      }
    }
  }
}
```

**Key Indicators:**
- `reasoning_tokens: 2000` (exactly at limit)
- `raw_response: ""` (empty)
- `completion_tokens: 2000` (all used for reasoning, none for output)

---

## ✅ Solution Implemented

### Code Changes

**File:** `worker_service/text_model_client.py`

**Change 1: Enhanced Detection**
```python
# CRITICAL: Check for reasoning token limit truncation
usage = response_data.get("usage", {})
completion_details = usage.get("completion_tokens_details", {})
reasoning_tokens = completion_details.get("reasoning_tokens", 0)

# If reasoning tokens is exactly 2000, model likely hit reasoning limit
if reasoning_tokens == 2000:
    self.log(f"⚠️ WARNING: Reasoning tokens = 2000 (likely hit limit)")
    self.log(f"   - This may cause truncated/empty response")
    self.log(f"   - Model may have stopped mid-reasoning")
    
    # Check if content is empty - this indicates the limit was actually hit
    # We'll validate this after extracting content below
```

**Change 2: Strict Validation & Error Raising**
```python
# Get content (might be empty if tool_calls present)
content = message.get("content", "")

# CRITICAL: Validate content is not empty (unless tool_calls present)
if not content or content.strip() == "":
    self.log(f"⚠️ WARNING: Model returned empty content")
    self.log(f"   - Message keys: {list(message.keys())}")
    self.log(f"   - Finish reason: {choice.get('finish_reason', 'unknown')}")
    self.log(f"   - Reasoning tokens: {reasoning_tokens}")
    
    # Check if this is due to reasoning token limit
    if reasoning_tokens >= 2000:
        error_msg = (
            f"CRITICAL: Model hit reasoning token limit ({reasoning_tokens} tokens). "
            f"The model stopped mid-reasoning and returned empty content. "
            f"This is a Nexus API limitation. "
            f"Recommendations: "
            f"1) Contact Nexus API provider to increase reasoning token limit, "
            f"2) Simplify the prompt, "
            f"3) Use a model without reasoning mode."
        )
        self.log(f"❌ {error_msg}")
        # CRITICAL: Raise exception to mark job as failed
        raise Exception(error_msg)
    
    # If no tool_calls and no reasoning limit, this is unexpected
    if "tool_calls" not in message or not message["tool_calls"]:
        error_msg = (
            f"Model returned empty content without tool_calls or reasoning limit. "
            f"Finish reason: {choice.get('finish_reason', 'unknown')}. "
            f"This is unexpected behavior."
        )
        self.log(f"❌ {error_msg}")
        # CRITICAL: Raise exception to mark job as failed
        raise Exception(error_msg)
```

### Behavior After Fix

**Before Fix:**
```json
{
  "status": "completed",
  "result": {
    "raw_response": "",
    "findings": { "status": "unknown" }
  },
  "error": null
}
```

**After Fix:**
```json
{
  "status": "failed",
  "result": null,
  "error": "CRITICAL: Model hit reasoning token limit (2000 tokens). The model stopped mid-reasoning and returned empty content. This is a Nexus API limitation. Recommendations: 1) Contact Nexus API provider to increase reasoning token limit, 2) Simplify the prompt, 3) Use a model without reasoning mode."
}
```

---

## 🎯 Impact

### Before Fix
- ❌ Jobs marked as "completed" with empty results
- ❌ No error message for clients
- ❌ Silent failure - hard to debug
- ❌ Clients receive "Analysis completed" but no data
- ❌ Wasted processing time and API calls

### After Fix
- ✅ Jobs marked as "failed" with clear error message
- ✅ Error message explains the issue and provides recommendations
- ✅ Easy to identify and debug
- ✅ Clients know the analysis failed and why
- ✅ Can implement retry logic or alternative approaches

---

## 📊 Testing

### Test Case 1: "Juhana S.E"

**Before Fix:**
```bash
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'

# Result: status="completed", raw_response=""
```

**After Fix:**
```bash
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "Juhana S.E", "entity_type": "person"}'

# Result: status="failed", error="CRITICAL: Model hit reasoning token limit..."
```

### Test Case 2: Simple Name (Should Work)

```bash
curl -X POST "https://text-doc-api-service-dev-lh5pr6ewdq-et.a.run.app/api/analyze-text/pep-analysis" \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "entity_type": "person"}'

# Expected: status="completed" with actual results (if within token limit)
# OR: status="failed" with clear error (if hits limit)
```

---

## 🔧 Long-term Solutions

### Option 1: Increase Reasoning Token Limit (Recommended)
**Action:** Contact Nexus API provider  
**Request:** Increase reasoning token limit from 2000 to 8000  
**Impact:** Allows complex analysis to complete  
**Timeline:** Depends on provider

### Option 2: Simplify Prompts
**Action:** Reduce prompt complexity  
**Implementation:**
- Remove verbose instructions
- Use more concise prompts
- Split complex analysis into multiple calls
**Impact:** May reduce analysis quality  
**Timeline:** 1-2 days

### Option 3: Disable Reasoning Mode
**Action:** Use model without reasoning mode  
**Implementation:** Remove reasoning-specific parameters  
**Impact:** May reduce analysis accuracy  
**Timeline:** 1 day

### Option 4: Implement Fallback Logic
**Action:** Retry with simplified prompt if limit hit  
**Implementation:**
```python
try:
    result = call_model_with_full_prompt(name)
except ReasoningTokenLimitError:
    result = call_model_with_simplified_prompt(name)
```
**Impact:** Better success rate, may reduce quality  
**Timeline:** 2-3 days

### Option 5: Use Alternative Model
**Action:** Switch to model without reasoning token limit  
**Implementation:** Configure different model endpoint  
**Impact:** Need to evaluate new model performance  
**Timeline:** 1 week (including testing)

---

## 📈 Monitoring

### Metrics to Track

1. **Reasoning Token Usage**
   - Track reasoning tokens per request
   - Alert when > 1800 (approaching limit)
   - Dashboard showing distribution

2. **Empty Response Rate**
   - Track % of requests with empty responses
   - Alert when > 5%
   - Trend analysis

3. **Job Failure Reasons**
   - Categorize failures by reason
   - Track "reasoning token limit" failures
   - Identify patterns

4. **Processing Time**
   - Track time to hit reasoning limit
   - Compare with successful requests
   - Optimize prompt length

### Alerting Rules

```yaml
alerts:
  - name: reasoning_token_limit_approaching
    condition: reasoning_tokens > 1800
    severity: warning
    action: log_and_notify
    
  - name: reasoning_token_limit_hit
    condition: reasoning_tokens >= 2000 AND content == ""
    severity: critical
    action: fail_job_and_alert
    
  - name: high_empty_response_rate
    condition: empty_response_rate > 5%
    severity: high
    action: alert_team
```

---

## 📝 Documentation Updates

### API Documentation

Add to API docs:

```markdown
## Known Limitations

### Reasoning Token Limit

Text analysis models have a reasoning token limit of 2000 tokens. 
If the analysis requires more reasoning tokens, the job will fail with:

**Error:** "CRITICAL: Model hit reasoning token limit (2000 tokens)..."

**Recommendations:**
1. Simplify the name or context
2. Contact support for assistance
3. Try again with less additional context

**Affected Endpoints:**
- POST /api/analyze-text/pep-analysis
- POST /api/analyze-text/negative-news
- POST /api/analyze-text/law-involvement
- POST /api/analyze-text/corporate-negative-news
- POST /api/analyze-text/corporate-law-involvement
```

### Error Handling Guide

Add to developer guide:

```python
# Example: Handle reasoning token limit error
response = requests.post(
    "https://api.example.com/api/analyze-text/pep-analysis",
    json={"name": "John Doe", "entity_type": "person"}
)

job_id = response.json()["job_id"]

# Poll for result
status = requests.get(f"https://api.example.com/api/status/{job_id}")

if status.json()["status"] == "failed":
    error = status.json()["error"]
    
    if "reasoning token limit" in error:
        # Handle reasoning token limit error
        print("Analysis too complex, try with simpler input")
        # Implement retry logic or alternative approach
    else:
        # Handle other errors
        print(f"Analysis failed: {error}")
```

---

## ✅ Deployment Checklist

- [x] Code changes implemented in `text_model_client.py`
- [x] Error messages are clear and actionable
- [x] Logging added for debugging
- [ ] Unit tests added for reasoning token limit detection
- [ ] Integration tests updated
- [ ] API documentation updated
- [ ] Error handling guide updated
- [ ] Monitoring alerts configured
- [ ] Team notified of changes
- [ ] Deployed to staging environment
- [ ] Tested in staging
- [ ] Deployed to production
- [ ] Production monitoring verified

---

## 📞 Contact

**Issue Owner:** Development Team  
**Nexus API Provider Contact:** [Contact Info]  
**Escalation:** [Manager Contact]

---

**Document Version:** 1.0  
**Last Updated:** 19 Januari 2026  
**Next Review:** After Nexus API provider response
