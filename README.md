# Document Processing & Text Analysis Worker Service

Async worker service that processes document processing and text analysis jobs. This service consumes messages from Pub/Sub and performs the actual processing work.

## 🚀 Features

### Document Processing
- PDF to image conversion with quality optimization
- Multi-page document handling
- Image quality enhancement and resizing
- Google Cloud Storage integration

### Text Analysis Processing
- **Person Analysis**: PEP screening, negative news, law involvement
- **Corporate Analysis**: Corporate negative news and law involvement
- **Model Integration**: Direct API calls to text analysis models
- **Result Formatting**: Structured JSON response formatting

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│ Worker Service  │    │ Text Models     │
│                 │    │                 │
│ • Job Processing│◄──►│ • PEP Analysis  │
│ • Text Analysis │    │ • Negative News │
│ • Doc Processing│    │ • Law Involvement│
│ • Result Storage│    │ • Corporate Models│
└─────────────────┘    └─────────────────┘
         ▲
         │
┌─────────────────┐
│ Google Cloud    │
│                 │
│ • Pub/Sub       │
│ • Firestore     │
│ • Cloud Storage │
└─────────────────┘
```

## 🛠️ Technology Stack

- **Runtime**: Python 3.13
- **Framework**: FastAPI (for health endpoints)
- **Cloud Platform**: Google Cloud Run
- **Message Queue**: Google Pub/Sub
- **Database**: Google Firestore
- **Storage**: Google Cloud Storage
- **Image Processing**: Pillow, pdf2image

## 📦 Core Components

### Main Worker (`worker.py`)
- Message processing from Pub/Sub
- Job routing (document vs text analysis)
- Health check endpoints
- Metrics collection

### Text Analysis Processor (`text_analysis_processor.py`)
- Text analysis job processing
- Model API integration
- Result formatting and validation
- Error handling and retries

### Text Model Client (`text_model_client.py`)
- HTTP client for text analysis models
- Authentication handling
- Request/response formatting
- Timeout and retry logic

### PDF Processor (`pdf_processor.py`)
- Document processing logic
- PDF to image conversion
- Image quality optimization
- Multi-page handling

## 🚀 Deployment

### Prerequisites
- Google Cloud Project: `bni-prod-dma-bnimove-ai`
- Service Account: `document-processing-sa@bni-prod-dma-bnimove-ai.iam.gserviceaccount.com`
- Container Registry access
- Text analysis model endpoint: `https://nexus-bnimove-369455734154.asia-southeast2.run.app`
- Pub/Sub subscription: `document-processing-worker`

### Auto Deployment
Push to `main` branch triggers automatic deployment via Cloud Build:

```bash
# Setup GitHub trigger
gcloud builds triggers create github \
  --repo-name=your-worker-repo-name \
  --repo-owner=your-github-username \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

### Manual Deployment
```bash
# Build and deploy
gcloud run services replace worker_service.yaml --region=asia-southeast1
```

## ⚙️ Configuration

### Environment Variables
- `GOOGLE_CLOUD_PROJECT`: bni-prod-dma-bnimove-ai
- `TEXT_MODEL_BASE_URL`: https://nexus-bnimove-369455734154.asia-southeast2.run.app
- `TEXT_MODEL_API_KEY`: sk-c2ebcb8d36aa4361a28560915d8ab6f2
- `GCS_BUCKET_NAME`: sbp-wrapper-bucket
- `PUBSUB_SUBSCRIPTION`: document-processing-worker
- `FIRESTORE_DATABASE`: document-processing-firestore

### Scaling
- **Min Instances**: 1
- **Max Instances**: 10
- **CPU**: 2 vCPU
- **Memory**: 4 GiB
- **Timeout**: 900 seconds

### Processing Configuration
- **Max Workers**: 3
- **Max Concurrent Chunks**: 2
- **Chunk Size**: 2
- **Base Image Quality**: 95%
- **PDF DPI**: 200

## 🔄 Message Processing

### Job Types
1. **Document Processing**: `job_type: "document"`
2. **Text Analysis**: `job_type: "text_analysis"`

### Message Format
```json
{
  "job_id": "unique-job-id",
  "job_type": "text_analysis",
  "analysis_type": "pep-analysis",
  "entity_type": "person",
  "name": "John Doe",
  "model_name": "politically-exposed-person-v2"
}
```

## 📊 Monitoring

- Health check endpoint: `/health`
- Metrics collection via `text_analysis_worker_metrics.py`
- Job processing statistics
- Performance monitoring
- Error tracking

## 🏃‍♂️ Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_CLOUD_PROJECT=bni-prod-dma-bnimove-ai
export TEXT_MODEL_BASE_URL=https://nexus-bnimove-369455734154.asia-southeast2.run.app

# Run locally
python worker.py
```

## 📄 License

Internal BNI project - All rights reserved.