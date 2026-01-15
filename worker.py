import os
import json
import time
import tempfile
import traceback
import threading
import asyncio
import gc
from datetime import datetime, timezone
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Google Cloud imports
from google.cloud import storage, pubsub_v1, firestore
from google.api_core import exceptions as gcp_exceptions

# Import ULTRA-FAST PDF processor
from pdf_processor import UltraFastPDFProcessor

# Import Text Analysis processor
from text_analysis_processor import TextAnalysisProcessor

# Import Text Analysis Worker Metrics
from text_analysis_worker_metrics import text_analysis_worker_metrics

# FastAPI untuk health check endpoint
from fastapi import FastAPI, HTTPException
import uvicorn


class UltraFastDocumentWorker:
    """
    ULTRA-OPTIMIZED Worker untuk production
    Target: 12.6 menit â†’ 3-4 menit total processing time
    """
    
    def __init__(self):
        """Initialize ULTRA-FAST worker dengan optimized settings"""

        # Configuration constants - matching Google Cloud Run settings
        class WorkerConfig:
            PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "bni-prod-dma-bnimove-ai")
            SUBSCRIPTION_NAME = os.getenv("PUBSUB_SUBSCRIPTION", "document-processing-worker")
            RESULTS_TOPIC = os.getenv("PUBSUB_RESULTS_TOPIC", "document-processing-results")
            FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE", "document-processing-firestore")
            MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))

        # Environment variables
        self.project_id = WorkerConfig.PROJECT_ID
        self.subscription_name = WorkerConfig.SUBSCRIPTION_NAME
        self.results_topic = WorkerConfig.RESULTS_TOPIC
        self.firestore_database = WorkerConfig.FIRESTORE_DATABASE
        
        # CONCURRENT PROCESSING: Multiple workers for better throughput - HARDCODED
        self.max_workers = 16          # HARDCODED: From your env var MAX_WORKERS=16
        self.max_concurrent_chunks = 8 # HARDCODED: From your env var MAX_CONCURRENT_CHUNKS=8
        self.port = int(os.getenv("PORT", "8080"))

        # HIGH-QUALITY processing configuration for consistent AI results
        class ProcessingConfig:
            API_KEY = os.getenv("OPENWEBUI_API_KEY", "sk-c2ebcb8d36aa4361a28560915d8ab6f2")
            BASE_URL = os.getenv("OPENWEBUI_BASE_URL", "https://nexus-bnimove-369455734154.asia-southeast2.run.app")
            MODEL = os.getenv("OPENWEBUI_MODEL", "image-screening-shmshm-elektronik")
            
            # HARDCODED ULTRA-FAST SETTINGS - BYPASS ENV VAR ISSUES
            MIN_DELAY_SECONDS = 5      # HARDCODED: Was 30, now 5 (6x faster)
            SAFETY_MARGIN = 0          # HARDCODED: Was 2, now 0 (no safety margin)
            TIMEOUT_SECONDS = 300      # HARDCODED: 5 minutes for PEP model (faster timeout)
            CHUNK_SIZE = 8             # HARDCODED: Was 2, now 8 (4x larger chunks)
            
            # HARDCODED HIGH-QUALITY settings for AI consistency
            MAX_IMAGE_SIZE_KB = 8000   # HARDCODED: Was 2000, now 8000 (preserve max quality)
            BASE_IMAGE_QUALITY = 98    # HARDCODED: Was 95, now 98 (ultra-high quality)
            MIN_IMAGE_QUALITY = 97     # HARDCODED: Was 90, now 97 (never below 97%)
            PRESERVE_ORIGINAL_QUALITY = True  # HARDCODED: Always preserve quality

        # HIGH-QUALITY processor configuration for consistent AI results
        self.processor_config = {
            "api_key": ProcessingConfig.API_KEY,
            "base_url": ProcessingConfig.BASE_URL,
            "model": ProcessingConfig.MODEL,
            "min_delay_between_requests": ProcessingConfig.MIN_DELAY_SECONDS,
            "safety_margin": ProcessingConfig.SAFETY_MARGIN,
            "timeout_seconds": ProcessingConfig.TIMEOUT_SECONDS,
            "chunk_size": ProcessingConfig.CHUNK_SIZE,
            
            # HIGH-QUALITY settings
            "max_image_size_kb": ProcessingConfig.MAX_IMAGE_SIZE_KB,
            "base_image_quality": ProcessingConfig.BASE_IMAGE_QUALITY,
            "min_image_quality": ProcessingConfig.MIN_IMAGE_QUALITY,
            "preserve_original_quality": ProcessingConfig.PRESERVE_ORIGINAL_QUALITY,
            
            "max_concurrent_chunks": self.max_concurrent_chunks,  # Pass concurrency setting
        }

        # Initialize GCP clients with connection pooling
        self.storage_client = storage.Client(project=self.project_id)
        self.subscriber = pubsub_v1.SubscriberClient()
        self.publisher = pubsub_v1.PublisherClient()
        self.firestore_client = firestore.Client(
            project=self.project_id,
            database=self.firestore_database,
        )

        # Connection paths
        self.subscription_path = self.subscriber.subscription_path(
            self.project_id, self.subscription_name
        )
        self.results_topic_path = self.publisher.topic_path(
            self.project_id, self.results_topic
        )

        # Worker status tracking
        self.is_running = False
        self.last_heartbeat = datetime.now(timezone.utc)
        self.processed_jobs = 0
        self.failed_jobs = 0
        self.start_time = datetime.now(timezone.utc)

        # OPTIMIZATION: Processor instance reuse untuk avoid initialization overhead
        self.cached_processor = None
        self.last_processor_config = None

        # Text Analysis Processor initialization
        self.text_analysis_processor = None
        self.text_processor_config = {
            "api_key": ProcessingConfig.API_KEY,
            "base_url": ProcessingConfig.BASE_URL,
            "timeout_seconds": ProcessingConfig.TIMEOUT_SECONDS,
            "enable_logging": True,
            # Retry configuration for model integration
            "max_retries": 3,
            "retry_delay": 1,
            "max_retry_delay": 30
        }

        # CONCURRENT PROCESSING: Thread pools for parallel execution
        self.io_executor = ThreadPoolExecutor(max_workers=self.max_workers * 2, thread_name_prefix="FastIO")
        self.job_executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="JobWorker")
        
        # Track active jobs for monitoring
        self.active_jobs = {}
        self.active_jobs_lock = threading.Lock()

        print(f"ðŸš€ Document Processing Worker initialized (HARDCODED ULTRA-FAST MODE):")
        print(f"   Project: {self.project_id}")
        print(f"   Subscription: {self.subscription_name}")
        print(f"   Results Topic: {self.results_topic}")
        print(f"   ðŸ”„ TOPIC CONFIGURATION:")
        print(f"      - Input subscription: {self.subscription_path}")
        print(f"      - Results topic: {self.results_topic_path}")
        print(f"      - Result publishing: DISABLED (prevents circular loop)")
        print(f"   Max concurrent jobs: {self.max_workers} (HARDCODED)")
        print(f"   Max concurrent chunks per job: {self.max_concurrent_chunks} (HARDCODED)")
        print(f"   HARDCODED ULTRA-FAST settings for maximum performance:")
        print(f"      - Base image quality: {self.processor_config['base_image_quality']}% (ULTRA-HIGH)")
        print(f"      - Min image quality: {self.processor_config['min_image_quality']}% (NEVER BELOW)")
        print(f"      - Max image size: {self.processor_config['max_image_size_kb']}KB (PRESERVE MAXIMUM DETAIL)")
        print(f"      - Preserve original quality: {self.processor_config['preserve_original_quality']}")
        print(f"   HARDCODED processing settings:")
        print(f"      - Delay: {self.processor_config['min_delay_between_requests']}s (14x FASTER)")
        print(f"      - Chunk size: {self.processor_config['chunk_size']} pages (4x LARGER)")
        print(f"      - Timeout: {self.processor_config['timeout_seconds']}s (2x FASTER)")
        print(f"   ðŸ”¥ ALL SETTINGS HARDCODED - BYPASSING ENVIRONMENT VARIABLES")

    def get_ultra_fast_processor(self, document_type: str, model_name: str = None) -> UltraFastPDFProcessor:
        """
        Get cached processor instance untuk avoid initialization overhead
        """
        config = self.processor_config.copy()
        config["document_type"] = document_type
        if model_name:
            config["model"] = model_name

        # Create cache key
        config_key = f"{config['model']}_{document_type}_{config['min_delay_between_requests']}"
        
        # Reuse processor if configuration hasn't changed
        if (self.cached_processor is not None and 
            self.last_processor_config == config_key):
            print("ðŸ”„ Reusing cached processor instance")
            return self.cached_processor
        
        # Create new processor
        print("âš¡ Creating new ULTRA-FAST processor")
        self.cached_processor = UltraFastPDFProcessor(config)
        self.cached_processor.enable_logging = True
        self.last_processor_config = config_key
        
        return self.cached_processor

    def get_text_analysis_processor(self) -> TextAnalysisProcessor:
        """
        Get cached text analysis processor instance
        """
        if self.text_analysis_processor is None:
            print("âš¡ Creating new TextAnalysisProcessor")
            self.text_analysis_processor = TextAnalysisProcessor(self.text_processor_config)
        
        return self.text_analysis_processor

    def ultra_fast_download_from_gcs(self, gcs_path: str, local_path: str) -> bool:
        """
        ULTRA-FAST GCS download dengan streaming dan timeout
        """
        try:
            download_start = time.time()
            
            print(f"ðŸ” Downloading: {gcs_path} -> {local_path}")
            
            if not gcs_path.startswith("gs://"):
                raise ValueError(f"Invalid GCS path format: {gcs_path}")

            # Parse GCS path
            path_parts = gcs_path[5:].split("/", 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid GCS path structure: {gcs_path}")
                
            bucket_name = path_parts[0]
            blob_name = path_parts[1]
            
            print(f"   ðŸ“¦ Bucket: {bucket_name}")
            print(f"   ðŸ“„ Blob: {blob_name}")

            # Get bucket and blob
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Check if blob exists
            if not blob.exists():
                raise Exception(f"Blob does not exist: {blob_name} in bucket {bucket_name}")
            
            # Get blob info
            blob.reload()
            blob_size_mb = blob.size / (1024 * 1024) if blob.size else 0
            print(f"   ðŸ“Š Blob size: {blob_size_mb:.2f}MB")
            
            # Download with timeout
            with open(local_path, 'wb') as f:
                blob.download_to_file(f, timeout=30)  # Increased timeout for larger files
            
            # Verify download
            if not os.path.exists(local_path):
                raise Exception(f"Downloaded file does not exist: {local_path}")
                
            local_size_mb = os.path.getsize(local_path) / (1024 * 1024)
            if local_size_mb == 0:
                raise Exception(f"Downloaded file is empty: {local_path}")
            
            download_time = time.time() - download_start
            speed_mbps = local_size_mb / download_time if download_time > 0 else 0
            
            print(f"âœ… Download successful: {download_time:.2f}s, {local_size_mb:.1f}MB ({speed_mbps:.1f} MB/s)")
            return True

        except Exception as e:
            error_msg = f"Download failed for {gcs_path}: {str(e)}"
            print(f"âŒ {error_msg}")
            
            # Clean up partial download
            try:
                if os.path.exists(local_path):
                    os.unlink(local_path)
            except:
                pass
                
            return False

    def download_multiple_files_from_gcs(self, gcs_paths: list, job_id: str) -> list:
        """
        Download multiple files from GCS for multi-file processing
        Returns list of local file paths in order
        """
        local_paths = []
        
        print(f"ðŸ”„ Starting download of {len(gcs_paths)} files for job {job_id}")
        
        for i, gcs_path in enumerate(gcs_paths):
            try:
                print(f"ðŸ“¥ Downloading file {i+1}/{len(gcs_paths)}: {gcs_path}")
                
                # Extract file extension from GCS path
                # Handle both gs://bucket/path/file.ext and just the filename
                if '/' in gcs_path:
                    filename = gcs_path.split('/')[-1]
                else:
                    filename = gcs_path
                
                file_ext = os.path.splitext(filename)[1] or '.tmp'
                
                # Create temporary file with page number to maintain order
                with tempfile.NamedTemporaryFile(
                    suffix=f"_page_{i+1:03d}{file_ext}", 
                    delete=False
                ) as tmp_file:
                    local_path = tmp_file.name
                
                print(f"   ðŸ“‚ Local path: {local_path}")
                
                # Download the file
                download_success = self.ultra_fast_download_from_gcs(gcs_path, local_path)
                
                if download_success:
                    # Verify file was actually downloaded and has content
                    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                        local_paths.append(local_path)
                        file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
                        print(f"âœ… Downloaded page {i+1}: {filename} ({file_size_mb:.2f}MB)")
                    else:
                        print(f"âŒ Downloaded file is empty or doesn't exist: {local_path}")
                        # Clean up empty file
                        try:
                            if os.path.exists(local_path):
                                os.unlink(local_path)
                        except:
                            pass
                        # Clean up any previously downloaded files
                        for path in local_paths:
                            try:
                                os.unlink(path)
                            except:
                                pass
                        return []
                else:
                    print(f"âŒ Failed to download page {i+1}: {gcs_path}")
                    # Clean up failed download file
                    try:
                        if os.path.exists(local_path):
                            os.unlink(local_path)
                    except:
                        pass
                    # Clean up any previously downloaded files
                    for path in local_paths:
                        try:
                            os.unlink(path)
                        except:
                            pass
                    return []
                    
            except Exception as e:
                print(f"âŒ Error downloading page {i+1}: {str(e)}")
                print(f"   GCS Path: {gcs_path}")
                # Clean up any partial downloads
                for path in local_paths:
                    try:
                        os.unlink(path)
                    except:
                        pass
                return []
        
        print(f"âœ… Successfully downloaded {len(local_paths)} files for multi-file processing")
        return local_paths

    def ultra_fast_update_job_status(self, job_id: str, status: str, result: Dict = None, error: str = None):
        """
        ULTRA-FAST Firestore update dengan aggressive timeout dan atomic operations
        """
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
                print(f"âœ… Marking job {job_id} as completed with result")
            elif status == "failed":
                update_data["completed_at"] = datetime.now(timezone.utc)
                if error:
                    update_data["error"] = error
                self.failed_jobs += 1
                print(f"âŒ Marking job {job_id} as failed with error: {error}")
            elif status == "processing":
                print(f"âš¡ Marking job {job_id} as processing")

            # ULTRA-FAST: Short timeout with retry
            try:
                doc_ref.update(update_data, timeout=5.0)
            except Exception as update_error:
                print(f"âš ï¸ First update attempt failed for {job_id}: {update_error}")
                # Retry once
                time.sleep(0.5)
                doc_ref.update(update_data, timeout=10.0)
            
            update_time = time.time() - start_time
            print(f"âš¡ Status updated in {update_time:.2f}s: {job_id} â†’ {status}")

        except Exception as e:
            print(f"âŒ Firestore update failed for {job_id}: {e}")
            # Don't raise exception - continue processing

    def ultra_fast_publish_result(self, job_id: str, result: Dict, status: str):
        """
        ULTRA-FAST result publishing
        """
        try:
            start_time = time.time()
            
            message_data = {
                "job_id": job_id,
                "status": status,
                "result": result,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }

            message_json = json.dumps(message_data).encode("utf-8")
            
            # ULTRA-FAST: Short timeout
            future = self.publisher.publish(self.results_topic_path, message_json)
            message_id = future.result(timeout=5.0)

            publish_time = time.time() - start_time
            print(f"âš¡ Result published in {publish_time:.2f}s: {message_id}")

        except Exception as e:
            print(f"âŒ Publish failed: {e}")

    def ultra_fast_process_document(self, job_data: Dict) -> Dict:
        """
        ULTRA-FAST document processing dengan minimal overhead
        Supports both single and multi-file processing
        """
        job_id = job_data.get("job_id", "unknown")
        
        # CRITICAL: Validate this is actually a document processing job
        job_type = job_data.get("job_type", "document")
        if job_type == "text_analysis":
            error_msg = f"CRITICAL ERROR: Text analysis job {job_id} incorrectly routed to document processor"
            print(f"âŒ {error_msg}")
            print(f"ðŸ” Job data keys: {list(job_data.keys())}")
            return {
                "success": False,
                "error": error_msg,
                "processing_time": 0,
                "traceback": "Text analysis job incorrectly routed to document processing function"
            }
        
        # Validate required document processing fields
        required_fields = ["document_type", "gcs_path", "filename"]
        missing_fields = [field for field in required_fields if field not in job_data]
        
        if missing_fields:
            error_msg = f"Missing required document processing fields: {missing_fields}"
            print(f"âŒ {error_msg}")
            print(f"ðŸ” Available fields: {list(job_data.keys())}")
            print(f"ðŸ” Job type: {job_type}")
            return {
                "success": False,
                "error": error_msg,
                "processing_time": 0,
                "job_type": job_type,
                "available_fields": list(job_data.keys())
            }
        
        document_type = job_data["document_type"]
        gcs_path = job_data["gcs_path"]
        filename = job_data["filename"]
        model_name = job_data.get("model_name")
        is_multi_file = job_data.get("is_multi_file", False)
        file_count = job_data.get("file_count", 1)

        print(f"ðŸš€ ULTRA-FAST processing: {job_id} ({document_type} - {filename})")
        if is_multi_file:
            print(f"   ðŸ“„ Multi-file document: {file_count} files")
        
        total_start = time.time()
        local_paths = []

        try:
            # STEP 1: ULTRA-FAST setup
            setup_start = time.time()
            
            if is_multi_file:
                # Handle multiple files
                print(f"ðŸ” Multi-file processing - GCS path type: {type(gcs_path)}")
                print(f"ðŸ” GCS paths: {gcs_path}")
                
                if not isinstance(gcs_path, list):
                    raise Exception(f"Multi-file job requires list of GCS paths, got {type(gcs_path)}: {gcs_path}")
                
                if len(gcs_path) == 0:
                    raise Exception("Multi-file job has empty GCS paths list")
                
                # Download all files
                print(f"ðŸ“¥ Starting download of {len(gcs_path)} files...")
                local_paths = self.download_multiple_files_from_gcs(gcs_path, job_id)
                
                if not local_paths:
                    raise Exception(f"Failed to download multi-file document. Expected {len(gcs_path)} files, got 0")
                
                if len(local_paths) != len(gcs_path):
                    raise Exception(f"Partial download failure. Expected {len(gcs_path)} files, got {len(local_paths)}")
                
                print(f"âœ… Successfully downloaded {len(local_paths)} files")
                
                # For multi-file processing, we'll process them as separate images
                # The processor will handle them as a single document
                primary_path = local_paths[0]  # Use first file as primary for processor
                
            else:
                # Handle single file (existing logic)
                with tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(filename)[1], delete=False
                ) as tmp_file:
                    primary_path = tmp_file.name
                local_paths = [primary_path]
            
            setup_time = time.time() - setup_start

            try:
                if not is_multi_file:
                    # STEP 2: Download single file
                    download_start = time.time()
                    if not self.ultra_fast_download_from_gcs(gcs_path, primary_path):
                        raise Exception("Download failed")
                    download_time = time.time() - download_start
                else:
                    # Multi-file download already completed in setup
                    download_time = 0

                # STEP 3: Get cached processor
                processor_start = time.time()
                processor = self.get_ultra_fast_processor(document_type, model_name)
                processor_init_time = time.time() - processor_start

                # STEP 4: ULTRA-FAST processing
                processing_start = time.time()
                print(f"âš¡ Processing with ULTRA-FAST settings:")
                print(f"   - Model: {processor.model}")
                print(f"   - Delays: {processor.min_delay_between_requests}s")
                print(f"   - Chunks: {processor.chunk_size} pages")
                print(f"   - Quality: {processor.base_image_quality}%")
                if is_multi_file:
                    print(f"   - Multi-file: {file_count} files")

                if is_multi_file:
                    # Process multiple files as a single document
                    result = processor.process_multiple_files(local_paths)
                else:
                    # Process single file
                    result = processor.process_file(primary_path)
                
                processing_time = time.time() - processing_start

                total_time = time.time() - total_start
                overhead_time = total_time - processing_time

                print(f"ðŸŽ‰ ULTRA-FAST processing completed:")
                print(f"   â±ï¸ Breakdown:")
                print(f"      - Setup: {setup_time:.2f}s")
                print(f"      - Download: {download_time:.2f}s") 
                print(f"      - Processor init: {processor_init_time:.2f}s")
                print(f"      - Processing: {processing_time:.2f}s")
                print(f"   ðŸ“Š Performance:")
                print(f"      - Total time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
                print(f"      - Overhead: {overhead_time:.2f}s ({overhead_time/total_time*100:.1f}%)")
                if not is_multi_file:
                    print(f"   ðŸš€ Speedup: ~{(12.6*60)/total_time:.1f}x faster than baseline!")

                return {
                    "success": True,
                    "result": result,
                    "performance_metrics": {
                        "setup_time": round(setup_time, 2),
                        "download_time": round(download_time, 2),
                        "processor_init_time": round(processor_init_time, 2),
                        "processing_time": round(processing_time, 2),
                        "total_time": round(total_time, 2),
                        "overhead_time": round(overhead_time, 2),
                        "overhead_percentage": round(overhead_time/total_time*100, 1),
                        "speedup_factor": round((12.6*60)/total_time, 1) if not is_multi_file else None
                    },
                    "model_used": processor.model,
                    "document_type": document_type,
                    "is_multi_file": is_multi_file,
                    "file_count": file_count,
                    "ultra_fast_optimization": True,
                }

            finally:
                # ULTRA-FAST cleanup
                for path in local_paths:
                    try:
                        if os.path.exists(path):
                            os.unlink(path)
                    except Exception:
                        pass
                # Force garbage collection
                gc.collect()

        except Exception as e:
            error_time = time.time() - total_start
            error_msg = f"ULTRA-FAST processing failed: {str(e)}"
            print(f"âŒ {error_msg} (after {error_time:.2f}s)")

            # Cleanup on error
            for path in local_paths:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except Exception:
                    pass

            return {
                "success": False,
                "error": error_msg,
                "processing_time": round(error_time, 2),
                "is_multi_file": is_multi_file,
                "file_count": file_count,
                "ultra_fast_optimization": True,
                "traceback": traceback.format_exc(),
            }

    def ultra_fast_process_text_analysis(self, job_data: Dict) -> Dict:
        """
        ULTRA-FAST text analysis processing with comprehensive metrics tracking
        """
        job_id = job_data.get("job_id", "unknown")
        
        # CRITICAL: Validate this is actually a text analysis job
        job_type = job_data.get("job_type", "document")
        if job_type != "text_analysis":
            error_msg = f"CRITICAL ERROR: Document processing job {job_id} incorrectly routed to text analysis processor"
            print(f"âŒ {error_msg}")
            print(f"ðŸ” Job data keys: {list(job_data.keys())}")
            return {
                "success": False,
                "error": error_msg,
                "processing_time": 0,
                "traceback": "Document processing job incorrectly routed to text analysis function"
            }
        
        # Validate required text analysis fields
        required_fields = ["analysis_type", "entity_type", "name"]
        missing_fields = [field for field in required_fields if field not in job_data]
        
        if missing_fields:
            error_msg = f"Missing required text analysis fields: {missing_fields}"
            print(f"âŒ {error_msg}")
            print(f"ðŸ” Available fields: {list(job_data.keys())}")
            print(f"ðŸ” Job type: {job_type}")
            return {
                "success": False,
                "error": error_msg,
                "processing_time": 0,
                "job_type": job_type,
                "available_fields": list(job_data.keys())
            }
        
        analysis_type = job_data.get("analysis_type")
        entity_type = job_data.get("entity_type")
        name = job_data.get("name")
        model_name = job_data.get("model_name", "unknown")
        
        print(f"ðŸš€ ULTRA-FAST text analysis: {job_id} ({analysis_type} for {entity_type})")
        print(f"   - Name: {name[:50]}..." if name and len(name) > 50 else f"   - Name: {name}")
        
        total_start = time.time()
        
        # Record job start in worker metrics
        metrics_start_time = text_analysis_worker_metrics.record_job_start(
            job_id, analysis_type, entity_type, model_name
        )
        
        try:
            # Get text analysis processor
            processor = self.get_text_analysis_processor()
            
            # Process the text analysis
            result = processor.process_text_analysis(job_data)
            
            total_time = time.time() - total_start
            
            if result.get("success"):
                print(f"ðŸŽ‰ ULTRA-FAST text analysis completed:")
                print(f"   â±ï¸ Total time: {total_time:.2f}s")
                print(f"   ðŸ¤– Model used: {result.get('model_used')}")
                print(f"   ðŸ“Š Analysis type: {result.get('analysis_type')}")
                
                # Record successful job in worker metrics
                text_analysis_worker_metrics.record_job_success(
                    metrics_start_time,
                    job_id,
                    analysis_type,
                    result.get('model_used', model_name),
                    result.get('processing_time', 0)
                )
                
                return {
                    "success": True,
                    "result": result["result"],
                    "performance_metrics": {
                        "total_time": round(total_time, 2),
                        "processing_time": result.get("processing_time", 0)
                    },
                    "model_used": result.get("model_used"),
                    "analysis_type": result.get("analysis_type"),
                    "entity_type": result.get("entity_type"),
                    "entity_name": result.get("entity_name"),
                    "text_analysis_optimization": True
                }
            else:
                error_msg = result.get("error", "Text analysis failed")
                print(f"âŒ Text analysis failed: {error_msg}")
                
                # Record failed job in worker metrics
                text_analysis_worker_metrics.record_job_failure(
                    metrics_start_time,
                    job_id,
                    analysis_type,
                    model_name,
                    "processing_error",
                    error_msg
                )
                
                return {
                    "success": False,
                    "error": error_msg,
                    "processing_time": round(total_time, 2),
                    "analysis_type": result.get("analysis_type"),
                    "entity_type": result.get("entity_type"),
                    "entity_name": result.get("entity_name"),
                    "text_analysis_optimization": True,
                    "traceback": result.get("traceback")
                }
                
        except Exception as e:
            error_time = time.time() - total_start
            error_msg = f"ULTRA-FAST text analysis failed: {str(e)}"
            print(f"âŒ {error_msg} (after {error_time:.2f}s)")
            
            # Record failed job in worker metrics
            text_analysis_worker_metrics.record_job_failure(
                metrics_start_time,
                job_id,
                analysis_type,
                model_name,
                "exception",
                str(e)
            )
            
            return {
                "success": False,
                "error": error_msg,
                "processing_time": round(error_time, 2),
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name,
                "text_analysis_optimization": True,
                "traceback": traceback.format_exc()
            }

    def process_single_message(self, message_data: Dict, ack_id: str):
        """
        CONCURRENT single message processing - now runs in thread pool
        """
        job_id = None
        message_start_time = time.time()

        try:
            # CONCURRENT validation
            if not isinstance(message_data, dict):
                print(f"âŒ Invalid message format")
                self.subscriber.modify_ack_deadline(
                    subscription=self.subscription_path,
                    ack_ids=[ack_id],
                    ack_deadline_seconds=0,
                )
                return

            job_id = message_data.get("job_id", "unknown")
            
            # Track active job
            with self.active_jobs_lock:
                self.active_jobs[job_id] = {
                    "start_time": message_start_time,
                    "status": "starting",
                    "thread_id": threading.current_thread().ident
                }
            
            print(f"âš¡ CONCURRENT processing message: {job_id} (Thread: {threading.current_thread().name})")

            # Debug message data with better formatting
            print(f"ðŸ” Message analysis:")
            print(f"   - Job ID: {job_id}")
            print(f"   - Message keys: {sorted(list(message_data.keys()))}")
            print(f"   - Is multi-file: {message_data.get('is_multi_file', False)}")
            print(f"   - File count: {message_data.get('file_count', 1)}")
            print(f"   - GCS path type: {type(message_data.get('gcs_path'))}")
            print(f"   - Has document_type: {'document_type' in message_data}")
            print(f"   - Has status: {'status' in message_data}")
            print(f"   - Has result: {'result' in message_data}")
            print(f"   - Has processed_at: {'processed_at' in message_data}")
            
            # CRITICAL: Check if this is a result message FIRST (before any other validation)
            # Result messages have these keys: ['job_id', 'status', 'result', 'processed_at']
            # Input messages have these keys: ['job_id', 'document_type', 'gcs_path', 'filename', ...]
            
            # Detect result message by checking for result-specific fields
            is_result_message = (
                "status" in message_data and 
                "result" in message_data and 
                "processed_at" in message_data and
                "document_type" not in message_data  # Input messages always have document_type
            )
            
            if is_result_message:
                print(f"ðŸš« IGNORING result message for job {job_id}")
                print(f"   - This is a result message with keys: {list(message_data.keys())}")
                print(f"   - Result messages should go to results topic, not input topic")
                print(f"   - Acknowledging and skipping processing")
                
                # Clean up active job tracking immediately
                with self.active_jobs_lock:
                    if job_id in self.active_jobs:
                        del self.active_jobs[job_id]
                
                # ACK the message to remove it from queue
                self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                return
            
            # Now validate input message fields
            # Check job type first to determine required fields
            job_type = message_data.get("job_type", "document")  # Default to document for backward compatibility
            
            if job_type == "text_analysis":
                # Text analysis job validation
                required_fields = ["job_id", "analysis_type", "entity_type", "name"]
                missing_fields = [field for field in required_fields if not message_data.get(field)]
                
                if missing_fields:
                    error_msg = f"Missing text analysis fields: {missing_fields}"
                    print(f"âŒ Invalid text analysis message: {error_msg}")
                    print(f"ðŸ” Available fields: {list(message_data.keys())}")
                    
                    if job_id != "unknown":
                        self.ultra_fast_update_job_status(job_id, "failed", error=error_msg)
                    
                    self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                    return
            else:
                # Document processing job validation (existing logic)
                required_fields = ["job_id", "document_type", "gcs_path", "filename"]
                missing_fields = [field for field in required_fields if not message_data.get(field)]
                
                if missing_fields:
                    # Double-check: Is this actually a result message that got past our detection?
                    if "status" in message_data and "result" in message_data:
                        print(f"ðŸš« CRITICAL: Result message detected in validation phase!")
                        print(f"   - This should have been caught earlier")
                        print(f"   - Message keys: {list(message_data.keys())}")
                        print(f"   - Acknowledging and skipping to prevent circular loop")
                        
                        # Clean up and acknowledge
                        with self.active_jobs_lock:
                            if job_id in self.active_jobs:
                                del self.active_jobs[job_id]
                        
                        self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                        return
                    
                    # This is a genuine input message with missing fields
                    error_msg = f"Missing document processing fields: {missing_fields}"
                    print(f"âŒ Invalid document processing message: {error_msg}")
                    print(f"ðŸ” Available fields: {list(message_data.keys())}")
                    print(f"ðŸ” Message data: {json.dumps(message_data, indent=2, default=str)}")
                    
                    if job_id != "unknown":
                        self.ultra_fast_update_job_status(job_id, "failed", error=error_msg)
                    
                    self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                    return

            # CONCURRENT job status check with better error handling
            try:
                doc_ref = self.firestore_client.collection("jobs").document(job_id)
                job_doc = doc_ref.get(timeout=2.0)  # Very quick timeout
                
                if job_doc.exists:
                    current_status = job_doc.to_dict().get("status", "unknown")
                    if current_status in ["completed", "failed"]:
                        print(f"âš ï¸ Job {job_id} already {current_status}, skipping duplicate processing")
                        self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                        return
                    elif current_status == "processing":
                        print(f"âš ï¸ Job {job_id} already being processed by another worker, skipping")
                        self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                        return
            except Exception as status_check_error:
                print(f"âš ï¸ Status check failed for {job_id}: {status_check_error}")
                # Continue processing - don't fail just because of status check

            # Mark as processing
            with self.active_jobs_lock:
                self.active_jobs[job_id]["status"] = "processing"
            
            self.ultra_fast_update_job_status(job_id, "processing")

            # CONCURRENT processing with better error handling
            try:
                # Route to appropriate processor based on job type
                job_type = message_data.get("job_type", "document")  # Default to document for backward compatibility
                
                print(f"ðŸ” Job routing for {job_id}:")
                print(f"   - Job type: {job_type}")
                print(f"   - Available fields: {list(message_data.keys())}")
                
                if job_type == "text_analysis":
                    print(f"ðŸ” Processing text analysis job: {job_id}")
                    print(f"   - Analysis type: {message_data.get('analysis_type')}")
                    print(f"   - Entity type: {message_data.get('entity_type')}")
                    print(f"   - Name: {message_data.get('name', '')[:50]}...")
                    result = self.ultra_fast_process_text_analysis(message_data)
                else:
                    print(f"ðŸ” Processing document job: {job_id}")
                    print(f"   - Document type: {message_data.get('document_type')}")
                    print(f"   - Has GCS path: {'gcs_path' in message_data}")
                    print(f"   - Has filename: {'filename' in message_data}")
                    result = self.ultra_fast_process_document(message_data)
                
                message_time = time.time() - message_start_time
                print(f"ðŸ“Š CONCURRENT total message processing: {message_time:.2f}s (Thread: {threading.current_thread().name})")

                if result and result.get("success"):
                    # SUCCESS path - double check we have valid result
                    if result.get("result"):
                        self.ultra_fast_update_job_status(job_id, "completed", result=result["result"])
                        # DISABLED: Prevent circular loop
                        # self.ultra_fast_publish_result(job_id, result["result"], "completed")
                        
                        print(f"âœ… Job {job_id} completed successfully (result publishing disabled)")
                        
                        # ACK message
                        self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                    else:
                        # Success but no result - treat as error
                        error_msg = "Processing succeeded but no result returned"
                        print(f"âš ï¸ Job {job_id}: {error_msg}")
                        self.ultra_fast_update_job_status(job_id, "failed", error=error_msg)
                        self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])
                else:
                    # FAILURE path
                    error_msg = result.get("error", "Unknown processing error") if result else "No result returned"
                    self.ultra_fast_update_job_status(job_id, "failed", error=error_msg)
                    # DISABLED: Prevent circular loop
                    # self.ultra_fast_publish_result(job_id, {"error": error_msg}, "failed")
                    
                    print(f"âŒ Job {job_id} failed: {error_msg} (result publishing disabled)")
                    
                    # ACK failed job
                    self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])

            except Exception as processing_error:
                error_msg = f"Processing exception: {str(processing_error)}"
                print(f"âŒ {error_msg}")
                print(f"âŒ Traceback: {traceback.format_exc()}")
                
                self.ultra_fast_update_job_status(job_id, "failed", error=error_msg)
                self.subscriber.acknowledge(subscription=self.subscription_path, ack_ids=[ack_id])

        except Exception as e:
            error_msg = f"Message error: {str(e)}"
            print(f"âŒ {error_msg}")
            print(f"âŒ Message processing traceback: {traceback.format_exc()}")
            
            if job_id and job_id != "unknown":
                try:
                    self.ultra_fast_update_job_status(job_id, "failed", error=error_msg)
                except Exception as update_error:
                    print(f"âŒ Failed to update job status: {update_error}")
            
            # NACK untuk retry
            try:
                self.subscriber.modify_ack_deadline(
                    subscription=self.subscription_path,
                    ack_ids=[ack_id],
                    ack_deadline_seconds=0,
                )
            except Exception as nack_error:
                print(f"âŒ Failed to NACK message: {nack_error}")
        finally:
            # Clean up active job tracking
            with self.active_jobs_lock:
                if job_id in self.active_jobs:
                    del self.active_jobs[job_id]

    def start_ultra_fast_polling_worker(self):
        """
        Start ULTRA-FAST polling worker
        """
        print(f"ðŸš€ Starting ULTRA-FAST polling worker...")
        print(f"Subscription: {self.subscription_path}")

        self.is_running = True
        consecutive_empty = 0
        max_empty_polls = 12

        try:
            while self.is_running:
                try:
                    # Heartbeat
                    self.last_heartbeat = datetime.now(timezone.utc)

                    # ULTRA-FAST message pulling with better timeout handling
                    try:
                        response = self.subscriber.pull(
                            subscription=self.subscription_path,
                            max_messages=self.max_workers,
                            timeout=30.0,  # Increased timeout to handle larger messages
                        )
                    except Exception as pull_error:
                        if "504" in str(pull_error) or "Deadline Exceeded" in str(pull_error):
                            # This is normal - just means no messages available
                            response = None
                        else:
                            # This is an actual error
                            print(f"âŒ Pub/Sub pull error: {pull_error}")
                            time.sleep(5)
                            continue

                    if response and response.received_messages:
                        consecutive_empty = 0
                        print(f"ðŸ“¨ Received {len(response.received_messages)} messages (CONCURRENT mode)")

                        # Process messages CONCURRENTLY using thread pool
                        futures = []
                        for received_message in response.received_messages:
                            try:
                                raw_data = received_message.message.data

                                if not raw_data:
                                    self.subscriber.modify_ack_deadline(
                                        subscription=self.subscription_path,
                                        ack_ids=[received_message.ack_id],
                                        ack_deadline_seconds=0,
                                    )
                                    continue

                                # CONCURRENT JSON parsing with debugging
                                try:
                                    decoded_data = raw_data.decode("utf-8")
                                    message_data = json.loads(decoded_data)
                                    
                                    # Debug message content
                                    job_id = message_data.get('job_id', 'unknown')
                                    job_type = message_data.get('job_type', 'not_specified')
                                    print(f"ðŸ“¨ Parsed message for job {job_id}")
                                    print(f"   - Job type: {job_type}")
                                    print(f"   - Keys: {list(message_data.keys())}")
                                    
                                    # Log specific fields based on job type
                                    if job_type == "text_analysis":
                                        print(f"   - Analysis type: {message_data.get('analysis_type')}")
                                        print(f"   - Entity type: {message_data.get('entity_type')}")
                                        print(f"   - Name: {message_data.get('name', '')[:30]}...")
                                    else:
                                        print(f"   - Document type: {message_data.get('document_type')}")
                                        print(f"   - Has GCS path: {'gcs_path' in message_data}")
                                        print(f"   - Has filename: {'filename' in message_data}")
                                    
                                except (UnicodeDecodeError, json.JSONDecodeError) as parse_error:
                                    print(f"âŒ Message parsing failed: {parse_error}")
                                    print(f"   - Raw data length: {len(raw_data)}")
                                    print(f"   - Raw data preview: {raw_data[:200]}...")
                                    self.subscriber.modify_ack_deadline(
                                        subscription=self.subscription_path,
                                        ack_ids=[received_message.ack_id],
                                        ack_deadline_seconds=0,
                                    )
                                    continue

                                # Submit job to thread pool for CONCURRENT processing
                                future = self.job_executor.submit(
                                    self.process_single_message,
                                    message_data,
                                    received_message.ack_id
                                )
                                futures.append(future)
                                
                                print(f"ðŸš€ Submitted job {message_data.get('job_id', 'unknown')} to thread pool")

                            except Exception as e:
                                print(f"âŒ Error submitting message to thread pool: {e}")
                                continue
                        
                        # Log concurrent processing status
                        if futures:
                            active_count = len([f for f in futures if not f.done()])
                            print(f"ðŸ“Š CONCURRENT STATUS: {len(futures)} jobs submitted, {active_count} active")
                            
                            # Show active jobs
                            with self.active_jobs_lock:
                                if self.active_jobs:
                                    print(f"ðŸ”„ Active jobs: {list(self.active_jobs.keys())}")

                        # Don't wait for completion - let them run concurrently
                    else:
                        consecutive_empty += 1
                        if consecutive_empty == 1:
                            print(f"ðŸ“­ No messages (ULTRA-FAST worker ready)")
                        elif consecutive_empty >= max_empty_polls:
                            print(f"ðŸ’“ ULTRA-FAST heartbeat - active and optimized...")
                            consecutive_empty = 0

                        time.sleep(3)  # Short sleep

                except KeyboardInterrupt:
                    print("\nðŸ›‘ ULTRA-FAST worker shutdown requested")
                    break
                except Exception as e:
                    error_str = str(e)
                    if "504" in error_str or "Deadline Exceeded" in error_str:
                        print(f"â° Pub/Sub timeout (normal) - no messages available")
                        time.sleep(1)  # Short sleep for timeout
                    else:
                        print(f"âŒ ULTRA-FAST polling error: {e}")
                        time.sleep(5)  # Longer sleep for real errors

        except Exception as e:
            print(f"âŒ ULTRA-FAST worker failed: {e}")
            raise
        finally:
            self.is_running = False
            # Cleanup thread pool
            self.io_executor.shutdown(wait=True)

        print("âœ… ULTRA-FAST worker shutdown complete")

    def get_health_status(self):
        """Get CONCURRENT worker health status with text analysis metrics"""
        now = datetime.now(timezone.utc)
        uptime = (now - self.start_time).total_seconds()
        time_since_heartbeat = (now - self.last_heartbeat).total_seconds()
        
        # Get thread pool status
        job_executor_active = getattr(self.job_executor, '_threads', set())
        active_thread_count = len([t for t in job_executor_active if t.is_alive()]) if job_executor_active else 0
        
        with self.active_jobs_lock:
            active_jobs_info = dict(self.active_jobs)

        # Get text analysis worker metrics
        text_analysis_worker_metrics_data = text_analysis_worker_metrics.get_worker_metrics()

        return {
            "status": "healthy" if self.is_running and time_since_heartbeat < 60 else "unhealthy",
            "is_running": self.is_running,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "uptime_seconds": round(uptime, 1),
            "time_since_heartbeat": round(time_since_heartbeat, 2),
            "processed_jobs": self.processed_jobs,
            "failed_jobs": self.failed_jobs,
            "success_rate": round(
                self.processed_jobs / max(1, self.processed_jobs + self.failed_jobs) * 100, 2,
            ),
            "subscription": self.subscription_name,
            "project_id": self.project_id,
            "concurrent_processing": {
                "max_concurrent_jobs": self.max_workers,
                "max_concurrent_chunks_per_job": self.max_concurrent_chunks,
                "active_jobs_count": len(active_jobs_info),
                "active_jobs": list(active_jobs_info.keys()),
                "active_threads": active_thread_count,
                "job_executor_queue_size": self.job_executor._work_queue.qsize() if hasattr(self.job_executor, '_work_queue') else 0
            },
            "optimization_version": "CONCURRENT v3.0",
            "concurrent_optimizations": {
                "concurrent_jobs": f"{self.max_workers} jobs in parallel",
                "concurrent_chunks": f"{self.max_concurrent_chunks} API calls per job",
                "delay_reduction": "70s â†’ 15s (5x faster)",
                "chunk_size_optimized": "2 â†’ 4 pages",
                "image_quality_optimized": "88% â†’ 80%",
                "timeout_reduced": "150s â†’ 90s",
                "processor_caching": "enabled",
                "thread_pool_processing": "enabled",
                "parallel_api_calls": "enabled",
                "target_speedup": "10-20x faster overall with concurrency"
            },
            "text_analysis_support": {
                "enabled": True,
                "processor_initialized": self.text_analysis_processor is not None,
                "supported_analysis_types": ["pep-analysis", "negative-news", "law-involvement", "corporate-negative-news", "corporate-law-involvement"],
                "supported_entity_types": ["person", "corporate"],
                "metrics": text_analysis_worker_metrics_data
            },
            "combined_performance": {
                "total_jobs_all_types": self.processed_jobs + self.failed_jobs + text_analysis_worker_metrics_data["overview"]["total_jobs_processed"],
                "combined_success_rate": self._calculate_combined_success_rate(text_analysis_worker_metrics_data),
                "document_processing_jobs": self.processed_jobs + self.failed_jobs,
                "text_analysis_jobs": text_analysis_worker_metrics_data["overview"]["total_jobs_processed"]
            }
        }
    
    def _calculate_combined_success_rate(self, text_metrics: Dict) -> float:
        """Calculate combined success rate across document and text analysis processing"""
        doc_total = self.processed_jobs + self.failed_jobs
        doc_success = self.processed_jobs
        
        text_total = text_metrics["overview"]["total_jobs_processed"]
        text_success = text_metrics["overview"]["successful_jobs"]
        
        total_jobs = doc_total + text_total
        total_success = doc_success + text_success
        
        if total_jobs == 0:
            return 100.0
        
        return round((total_success / total_jobs) * 100, 2)


# Global worker instance
worker = None

# FastAPI app
app = FastAPI(title="CONCURRENT Document Processing & Text Analysis Worker", version="3.0.0")

@app.get("/")
async def root():
    return {
        "service": "Document Processing & Text Analysis Worker",
        "status": "running",
        "version": "3.0.0",
        "description": "Async document processing and text analysis worker with configurable optimizations",
        "features": [
            "Configurable processing delays",
            "Adjustable chunk sizes",
            "Processor caching",
            "Production ready",
            "Health monitoring",
            "Text analysis support",
            "Person and corporate name analysis",
            "PEP, negative news, and law involvement screening"
        ]
    }

@app.get("/health")
async def health():
    """
    HTTP Health Check endpoint for Cloud Run
    Returns detailed concurrent processing status
    """
    global worker
    
    if not worker:
        # During initialization
        return {
            "status": "initializing", 
            "message": "CONCURRENT Worker initializing...",
            "ready": False
        }
    
    try:
        health_status = worker.get_health_status()
        
        # Determine if worker is truly healthy for HTTP health check
        is_healthy = (
            health_status.get("status") == "healthy" and
            health_status.get("is_running", False) and
            health_status.get("time_since_heartbeat", 999) < 120  # Less than 2 minutes since heartbeat
        )
        
        # Add HTTP-specific fields
        health_status["ready"] = is_healthy
        health_status["http_health_check"] = True
        
        # Return appropriate HTTP status code
        if is_healthy:
            return health_status  # HTTP 200
        else:
            # Return 503 Service Unavailable for unhealthy worker
            raise HTTPException(
                status_code=503, 
                detail={
                    **health_status,
                    "message": "Worker unhealthy - check concurrent processing status"
                }
            )
            
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        # Return 503 for any health check errors
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "ready": False,
                "http_health_check": True
            }
        )

@app.get("/debug/last-messages")
async def get_last_messages():
    """Debug endpoint to see recent message processing"""
    global worker
    if worker:
        with worker.active_jobs_lock:
            active_jobs = dict(worker.active_jobs)
        
        return {
            "active_jobs": active_jobs,
            "processed_jobs": worker.processed_jobs,
            "failed_jobs": worker.failed_jobs,
            "is_running": worker.is_running,
            "last_heartbeat": worker.last_heartbeat.isoformat() if worker.last_heartbeat else None,
            "subscription_path": worker.subscription_path,
            "debug_info": "Check logs for detailed message processing information"
        }
    else:
        return {"error": "Worker not initialized"}

@app.get("/debug/config")
async def get_worker_config():
    """Debug endpoint to see worker configuration"""
    global worker
    if worker:
        return {
            "project_id": worker.project_id,
            "subscription_name": worker.subscription_name,
            "subscription_path": worker.subscription_path,
            "max_workers": worker.max_workers,
            "max_concurrent_chunks": worker.max_concurrent_chunks,
            "processor_config": {
                "api_key": "***" + worker.processor_config["api_key"][-4:] if worker.processor_config.get("api_key") else None,
                "base_url": worker.processor_config.get("base_url"),
                "timeout_seconds": worker.processor_config.get("timeout_seconds"),
            },
            "text_processor_config": {
                "api_key": "***" + worker.text_processor_config["api_key"][-4:] if worker.text_processor_config.get("api_key") else None,
                "base_url": worker.text_processor_config.get("base_url"),
                "timeout_seconds": worker.text_processor_config.get("timeout_seconds"),
                "max_retries": worker.text_processor_config.get("max_retries"),
            }
        }
    else:
        return {"error": "Worker not initialized"}

@app.get("/metrics")
async def metrics():
    global worker
    if worker:
        status = worker.get_health_status()
        
        # Get text analysis worker metrics
        text_analysis_metrics = text_analysis_worker_metrics.get_worker_metrics()
        
        return {
            "document_processing": {
                "processed_jobs": status["processed_jobs"],
                "failed_jobs": status["failed_jobs"],
                "success_rate": status["success_rate"],
                "uptime_seconds": status["uptime_seconds"],
                "concurrent_processing": status["concurrent_processing"],
                "optimization_version": status["optimization_version"],
                "concurrent_optimizations": status["concurrent_optimizations"]
            },
            "text_analysis": text_analysis_metrics,
            "combined_metrics": {
                "total_jobs": status["processed_jobs"] + status["failed_jobs"] + text_analysis_metrics["overview"]["total_jobs_processed"],
                "overall_success_rate": _calculate_combined_success_rate(status, text_analysis_metrics),
                "service_uptime_seconds": status["uptime_seconds"]
            },
            "capabilities": {
                "document_processing": True,
                "text_analysis": True,
                "concurrent_processing": True,
                "metrics_tracking": True
            }
        }
    else:
        return {"message": "CONCURRENT Worker not initialized"}

def _calculate_combined_success_rate(doc_status: Dict, text_metrics: Dict) -> float:
    """Calculate combined success rate across document and text analysis processing"""
    doc_total = doc_status["processed_jobs"] + doc_status["failed_jobs"]
    doc_success = doc_status["processed_jobs"]
    
    text_total = text_metrics["overview"]["total_jobs_processed"]
    text_success = text_metrics["overview"]["successful_jobs"]
    
    total_jobs = doc_total + text_total
    total_success = doc_success + text_success
    
    if total_jobs == 0:
        return 100.0
    
    return round((total_success / total_jobs) * 100, 2)

def main():
    """Main entry point untuk ULTRA-FAST worker"""
    global worker

    try:
        print("ðŸš€ Initializing CONCURRENT Document Processing & Text Analysis Worker...")

        # Initialize worker
        worker = UltraFastDocumentWorker()

        # Start worker thread
        worker_thread = threading.Thread(
            target=worker.start_ultra_fast_polling_worker, daemon=True
        )
        worker_thread.start()

        print(f"âœ… CONCURRENT Worker thread started")
        print(f"ðŸŒ Starting HTTP server on port {worker.port}")
        print(f"ðŸŽ¯ Target performance: 1-2 minutes with concurrency (was 12.6 minutes)")
        print(f"ðŸ”„ Concurrent jobs: {worker.max_workers}")
        print(f"âš¡ Concurrent chunks per job: {worker.max_concurrent_chunks}")
        print(f"ðŸ“ Text analysis support: Enabled")
        print(f"ðŸ” Supported analysis types: PEP, negative news, law involvement")
        print(f"ðŸ‘¥ Supported entity types: Person, corporate")

        # Start HTTP server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=worker.port,
            log_level="info",
        )

    except KeyboardInterrupt:
        print("\nðŸ›‘ CONCURRENT Worker stopped by user")
        if worker:
            worker.is_running = False
    except Exception as e:
        print(f"âŒ CONCURRENT Worker failed to start: {e}")
        print(traceback.format_exc())
        exit(1)


if __name__ == "__main__":
    main()

