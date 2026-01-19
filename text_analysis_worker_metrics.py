"""
Text Analysis Worker Metrics Module
Tracks worker-side metrics for text analysis processing
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from collections import defaultdict, deque


class TextAnalysisWorkerMetrics:
    """Worker-side metrics tracking for text analysis operations"""
    
    def __init__(self, max_samples: int = 500):
        """Initialize metrics tracking"""
        self._lock = threading.RLock()
        self.max_samples = max_samples
        self.total_jobs_processed = 0
        self.successful_jobs = 0
        self.failed_jobs = 0
        self.jobs_by_analysis_type = defaultdict(int)
        self.failures_by_analysis_type = defaultdict(int)
        self.processing_times = deque(maxlen=max_samples)
        self.processing_times_by_type = defaultdict(lambda: deque(maxlen=max_samples))
        self.model_call_times = defaultdict(lambda: deque(maxlen=max_samples))
        self.model_success_count = defaultdict(int)
        self.model_failure_count = defaultdict(int)
        self.error_types = defaultdict(int)
        self.recent_errors = deque(maxlen=100)
        self.start_time = datetime.now(timezone.utc)
        self.last_job_time = None
        print("📊 TextAnalysisWorkerMetrics initialized")

    def record_job_start(self, job_id: str, analysis_type: str, entity_type: str, model_name: str) -> float:
        """Record job start, returns start timestamp"""
        start_time = time.time()
        with self._lock:
            self.total_jobs_processed += 1
            self.jobs_by_analysis_type[analysis_type] += 1
            self.last_job_time = datetime.now(timezone.utc)
        return start_time
    
    def record_job_success(self, start_time: float, job_id: str, analysis_type: str,
                          model_name: str, model_response_time: Optional[float] = None):
        """Record successful job"""
        processing_time = time.time() - start_time
        with self._lock:
            self.successful_jobs += 1
            self.processing_times.append(processing_time)
            self.processing_times_by_type[analysis_type].append(processing_time)
            self.model_success_count[model_name] += 1
            if model_response_time:
                self.model_call_times[model_name].append(model_response_time)
    
    def record_job_failure(self, start_time: float, job_id: str, analysis_type: str,
                          model_name: str, error_type: str, error_message: str):
        """Record failed job"""
        processing_time = time.time() - start_time
        with self._lock:
            self.failed_jobs += 1
            self.failures_by_analysis_type[analysis_type] += 1
            self.model_failure_count[model_name] += 1
            self.error_types[error_type] += 1
            self.processing_times.append(processing_time)
            self.recent_errors.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_id": job_id,
                "analysis_type": analysis_type,
                "error_type": error_type,
                "error_message": error_message[:200]
            })
    
    def get_worker_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics"""
        with self._lock:
            current_time = datetime.now(timezone.utc)
            uptime = (current_time - self.start_time).total_seconds()
            total_completed = self.successful_jobs + self.failed_jobs
            success_rate = (self.successful_jobs / max(total_completed, 1)) * 100
            avg_time = sum(self.processing_times) / max(len(self.processing_times), 1)
            jobs_per_hour = total_completed / max(uptime / 3600, 1/3600)
            
            return {
                "overview": {
                    "total_jobs": self.total_jobs_processed,
                    "successful": self.successful_jobs,
                    "failed": self.failed_jobs,
                    "success_rate": round(success_rate, 2),
                    "avg_processing_time_ms": round(avg_time * 1000, 2),
                    "jobs_per_hour": round(jobs_per_hour, 2),
                    "uptime_seconds": round(uptime, 2)
                },
                "by_analysis_type": dict(self.jobs_by_analysis_type),
                "errors": {
                    "by_type": dict(self.error_types),
                    "recent": list(self.recent_errors)[-5:]
                },
                "timestamp": current_time.isoformat()
            }


# Global instance
text_analysis_worker_metrics = TextAnalysisWorkerMetrics()
