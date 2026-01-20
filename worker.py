"""
Text Analysis Worker Service - Character Prescreening for Debtor Candidates
Consumes Pub/Sub messages and processes text-based name analysis jobs
"""

import os
import json
import time
import traceback
import threading
import base64
from datetime import datetime, timezone
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Google Cloud imports
from google.cloud import pubsub_v1, firestore

# Import Text Analysis processor
from text_analysis_processor import TextAnalysisProcessor

# Import Text Analysis Worker Metrics
from text_analysis_worker_metrics import text_analysis_worker_metrics

# FastAPI for health check endpoint
from fastapi import FastAPI, HTTPException
import uvicorn


class TextAnalysisWorker:
    """
    Worker for processing text-based character prescreening jobs
    Consumes messages from Pub/Sub and calls custom search API
    """
    
    def __init__(self):
        """Initialize text analysis worker"""
        
        # Configuration
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "bni-prod-dma-bnimove-ai")
        self.subscription_name = os.getenv("PUBSUB_SUBSCRIPTION", "text-analysis-worker")
        self.firestore_database = os.getenv("FIRESTORE_DATABASE", "text-analysis-firestore")
        self.port = int(os.getenv("PORT", "8080"))
        
        # Worker settings
        self.max_workers = int(os.getenv("MAX_WORKERS", "16"))
        
        # Model API configuration
        self.text_processor_config = {
            "api_key": os.getenv("TEXT_MODEL_API_KEY", "sk-c2ebcb8d36aa4361a28560915d8ab6f2"),
            "base_url": os.getenv("TEXT_MODEL_BASE_URL", "https://nexus-bnimove-369455734154.asia-southeast2.run.app"),
            "timeout_seconds": int(os.getenv("TEXT_MODEL_TIMEOUT", "180")),
            "enable_logging": True,
            "max_retries": 3,
            "retry_delay": 1,
            "max_retry_delay": 30
        }
        
        # Initialize GCP clients
        self.subscriber = pubsub_v1.SubscriberClient()
        self.firestore_client = firestore.Client(
            project=self.project_id,
            database=self.firestore_database
        )
        
        # Subscription path
        self.subscription_path = self.subscriber.subscription_path(
            self.project_id, self.subscription_name
        )
        
        # Worker status
        self.is_running = False
        self.processed_jobs = 0
        self.failed_jobs = 0
        self.start_time = datetime.now(timezone.utc)
        
        # Text Analysis Processor
        self.text_analysis_processor = None
        
        # Thread pool for concurrent processing
        self.job_executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="TextWorker")
        
        # Active jobs tracking
        self.active_jobs = {}
        self.active_jobs_lock = threading.Lock()
        
        print(f"🚀 Text Analysis Worker initialized:")
        print(f"   Project: {self.project_id}")
        print(f"   Subscription: {self.subscription_name}")
        print(f"   Firestore DB: {self.firestore_database}")
        print(f"   Max workers: {self.max_workers}")
        print(f"   Model API: {self.text_processor_config['base_url']}")

    def get_text_analysis_processor(self) -> TextAnalysisProcessor:
        """Get cached text analysis processor instance"""
        if self.text_analysis_processor is None:
            print("⚡ Creating new TextAnalysisProcessor")
            self.text_analysis_processor = TextAnalysisProcessor(self.text_processor_config)
        return self.text_analysis_processor
    
    def update_job_status(self, job_id: str, status: str, result: Dict = None, error: str = None):
        """Update job status in Firestore"""
        try:
            start_time = time.time()
            doc_ref = self.firestore_client.collection("jobs").document(job_id)
            
            update_data = {
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
            
            if status == "completed":
                update_data["completed_at"] = datetime.now(timezone.utc)
                if result:
                    update_data["result"] = result
                self.processed_jobs += 1
                print(f"✅ Job {job_id} completed")
            elif status == "failed":
                update_data["completed_at"] = datetime.now(timezone.utc)
                if error:
                    update_data["error"] = error
                self.failed_jobs += 1
                print(f"❌ Job {job_id} failed: {error}")
            elif status == "processing":
                print(f"⚡ Job {job_id} processing")
            
            doc_ref.update(update_data, timeout=10.0)
            
            update_time = time.time() - start_time
            print(f"⚡ Status updated in {update_time:.2f}s: {job_id} → {status}")
            
        except Exception as e:
            print(f"❌ Firestore update failed for {job_id}: {e}")

    def process_text_analysis_job(self, job_data: Dict) -> Dict:
        """Process a text analysis job"""
        job_id = job_data.get("job_id", "unknown")
        analysis_type = job_data.get("analysis_type")
        entity_type = job_data.get("entity_type")
        name = job_data.get("name")
        model_name = job_data.get("model_name", "unknown")
        
        print(f"🔍 Processing text analysis job: {job_id}")
        print(f"   - Analysis type: {analysis_type}")
        print(f"   - Entity type: {entity_type}")
        print(f"   - Model: {model_name}")
        
        # Record job start in metrics
        start_time = text_analysis_worker_metrics.record_job_start(
            job_id, analysis_type, entity_type, model_name
        )
        
        try:
            # Update status to processing
            self.update_job_status(job_id, "processing")
            
            # Get processor and process
            processor = self.get_text_analysis_processor()
            result = processor.process_text_analysis(job_data)
            
            if result.get("success"):
                # Record success metrics
                text_analysis_worker_metrics.record_job_success(
                    start_time, job_id, analysis_type, model_name,
                    result.get("processing_time")
                )
                
                # Update job as completed
                self.update_job_status(job_id, "completed", result=result.get("result"))
                
                return result
            else:
                # Record failure metrics
                error_msg = result.get("error", "Unknown error")
                text_analysis_worker_metrics.record_job_failure(
                    start_time, job_id, analysis_type, model_name,
                    "PROCESSING_ERROR", error_msg
                )
                
                # Update job as failed
                self.update_job_status(job_id, "failed", error=error_msg)
                
                return result
                
        except Exception as e:
            error_msg = f"Text analysis failed: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            
            # Record failure metrics
            text_analysis_worker_metrics.record_job_failure(
                start_time, job_id, analysis_type, model_name,
                "EXCEPTION", error_msg
            )
            
            # Update job as failed
            self.update_job_status(job_id, "failed", error=error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }

    def process_message(self, message):
        """Process a single Pub/Sub message"""
        job_id = "unknown"
        
        try:
            # Parse message data
            message_data = json.loads(message.data.decode("utf-8"))
            job_id = message_data.get("job_id", "unknown")
            job_type = message_data.get("job_type", "text_analysis")
            
            print(f"📨 Received message for job: {job_id} (type: {job_type})")
            
            # Track active job
            with self.active_jobs_lock:
                self.active_jobs[job_id] = {
                    "start_time": datetime.now(timezone.utc),
                    "job_type": job_type
                }
            
            # Validate job type
            if job_type != "text_analysis":
                error_msg = f"Invalid job type: {job_type}. Expected: text_analysis"
                print(f"❌ {error_msg}")
                self.update_job_status(job_id, "failed", error=error_msg)
                message.ack()
                return
            
            # Process the job
            result = self.process_text_analysis_job(message_data)
            
            # Acknowledge message
            message.ack()
            print(f"✅ Message acknowledged for job: {job_id}")
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse message JSON: {e}")
            message.ack()  # Ack to prevent redelivery of invalid message
        except Exception as e:
            print(f"❌ Error processing message for job {job_id}: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            message.nack()  # Nack to allow retry
        finally:
            # Remove from active jobs
            with self.active_jobs_lock:
                self.active_jobs.pop(job_id, None)

    def start_subscriber(self):
        """Start the Pub/Sub subscriber"""
        print(f"🔄 Starting Pub/Sub subscriber...")
        print(f"   Subscription: {self.subscription_path}")
        
        self.is_running = True
        
        # Configure flow control
        flow_control = pubsub_v1.types.FlowControl(
            max_messages=self.max_workers,
            max_bytes=100 * 1024 * 1024  # 100MB
        )
        
        # Start streaming pull
        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path,
            callback=self.process_message,
            flow_control=flow_control
        )
        
        print(f"✅ Subscriber started, waiting for messages...")
        
        return streaming_pull_future

    def get_worker_status(self) -> Dict[str, Any]:
        """Get current worker status"""
        current_time = datetime.now(timezone.utc)
        uptime_seconds = (current_time - self.start_time).total_seconds()
        
        with self.active_jobs_lock:
            active_job_count = len(self.active_jobs)
            active_job_ids = list(self.active_jobs.keys())
        
        return {
            "status": "running" if self.is_running else "stopped",
            "uptime_seconds": round(uptime_seconds, 2),
            "processed_jobs": self.processed_jobs,
            "failed_jobs": self.failed_jobs,
            "active_jobs": active_job_count,
            "active_job_ids": active_job_ids[:10],  # Limit to 10
            "max_workers": self.max_workers,
            "subscription": self.subscription_name,
            "project_id": self.project_id,
            "start_time": self.start_time.isoformat()
        }


# Initialize FastAPI app for health checks
app = FastAPI(
    title="Text Analysis Worker - Character Prescreening",
    description="Background worker for processing character prescreening jobs",
    version="1.0.0"
)

# Global worker instance
worker = None


@app.on_event("startup")
async def startup_event():
    """Initialize worker on startup"""
    global worker
    worker = TextAnalysisWorker()
    
    # Start subscriber in background thread
    def run_subscriber():
        try:
            streaming_pull_future = worker.start_subscriber()
            streaming_pull_future.result()  # Block until cancelled
        except Exception as e:
            print(f"❌ Subscriber error: {e}")
    
    subscriber_thread = threading.Thread(target=run_subscriber, daemon=True)
    subscriber_thread.start()
    print("✅ Worker startup complete")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Text Analysis Worker - Character Prescreening",
        "status": "running",
        "version": "1.0.0",
        "purpose": "Process character prescreening jobs from Pub/Sub"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    if worker is None:
        return {"status": "unhealthy", "error": "Worker not initialized"}
    
    worker_status = worker.get_worker_status()
    
    return {
        "status": "healthy" if worker_status["status"] == "running" else "degraded",
        "worker": worker_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics")
async def metrics():
    """Get worker metrics"""
    if worker is None:
        return {"error": "Worker not initialized"}
    
    return {
        "success": True,
        "worker_status": worker.get_worker_status(),
        "processing_metrics": text_analysis_worker_metrics.get_worker_metrics(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/process")
async def process_pubsub_push(request: Dict[str, Any]):
    """
    Handle Pub/Sub push messages
    This endpoint receives messages pushed from Pub/Sub subscription
    """
    if worker is None:
        raise HTTPException(status_code=503, detail="Worker not initialized")
    
    try:
        # Extract message from Pub/Sub push format
        message = request.get("message", {})
        message_data = message.get("data", "")
        
        if not message_data:
            print("⚠️ Empty message data received")
            return {"status": "ok", "message": "Empty message ignored"}
        
        # Decode base64 message data
        decoded_data = base64.b64decode(message_data).decode("utf-8")
        job_data = json.loads(decoded_data)
        
        job_id = job_data.get("job_id", "unknown")
        job_type = job_data.get("job_type", "text_analysis")
        
        print(f"📨 Received push message for job: {job_id} (type: {job_type})")
        
        # Track active job
        with worker.active_jobs_lock:
            worker.active_jobs[job_id] = {
                "start_time": datetime.now(timezone.utc),
                "job_type": job_type
            }
        
        try:
            # Validate job type
            if job_type != "text_analysis":
                error_msg = f"Invalid job type: {job_type}. Expected: text_analysis"
                print(f"❌ {error_msg}")
                worker.update_job_status(job_id, "failed", error=error_msg)
                return {"status": "ok", "message": error_msg}
            
            # Process the job
            result = worker.process_text_analysis_job(job_data)
            
            return {
                "status": "ok",
                "job_id": job_id,
                "success": result.get("success", False)
            }
            
        finally:
            # Remove from active jobs
            with worker.active_jobs_lock:
                worker.active_jobs.pop(job_id, None)
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse message JSON: {e}")
        return {"status": "ok", "message": f"Invalid JSON: {e}"}
    except Exception as e:
        print(f"❌ Error processing push message: {e}")
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Main entry point"""
    print("🚀 Starting Text Analysis Worker Service...")
    
    # Get port from environment
    port = int(os.getenv("PORT", "8080"))
    
    # Run FastAPI with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
