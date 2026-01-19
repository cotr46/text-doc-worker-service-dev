# Text Analysis Worker Service

Background worker for processing character prescreening jobs (PEP, negative news, law involvement).

## Overview

This service consumes Pub/Sub messages and processes text-based name analysis for debtor candidate screening.

## Analysis Types

| Type | Model | Entity | Description |
|------|-------|--------|-------------|
| `pep-analysis` | politically-exposed-person-v2 | person | PEP screening |
| `negative-news` | negative-news | person | Individual negative news |
| `law-involvement` | law-involvement | person | Individual law involvement |
| `corporate-negative-news` | negative-news-corporate | corporate | Corporate negative news |
| `corporate-law-involvement` | law-involvement-corporate | corporate | Corporate law involvement |

## Local Development

```bash
pip install -r requirements.txt
python worker.py
```

## Environment Variables

- `GOOGLE_CLOUD_PROJECT`: GCP project ID
- `PUBSUB_SUBSCRIPTION`: Pub/Sub subscription name
- `FIRESTORE_DATABASE`: Firestore database name
- `TEXT_MODEL_BASE_URL`: Custom search API URL
- `TEXT_MODEL_API_KEY`: API key for model service
- `MAX_WORKERS`: Concurrent worker threads (default: 16)

## Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- `GET /metrics` - Worker metrics

## Deployment

Push to `text-analysis-worker` branch triggers Cloud Build deployment.
