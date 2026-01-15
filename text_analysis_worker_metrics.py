"""
Text Analysis Worker Metrics Module
Tracks worker-side metrics for text analysis processing
Requirements: 8.1, 10.1, 10.3
"""

import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from collections import defaultdict, deque


class TextAnalysisWorkerMetrics:
    """
    Worker-side metrics tracking for text analysis operations
    Thread-safe implementation for concurrent processing
    """
    
    def __init__(self, max_samples: int = 500):
        """
        Initialize worker metrics tracking
        
        Args:
            max_samples: Maximum number of samples to keep in memory
        """
        self._lock = threading.RLock()
        self.max_samples = max_samples
        
        # Job processing metrics
        self.total_jobs_processed = 0
        self.successful_jobs = 0
        self.failed_jobs = 0
        self.jobs_by_analysis_type = defaultdict(int)
        self.failures_by_analysis_type = defaultdict(int)
        
        # Processing time metrics
        self.processing_times = deque(maxlen=max_samples)
        self.processing_times_by_type = defaultdict(lambda: deque(maxlen=max_samples))
        
        # Model performance metrics
        self.model_call_times = defaultdict(lambda: deque(maxlen=max_samples))
        self.model_success_count = defaultdict(int)
        self.model_failure_count = defaultdict(int)
        self.model_timeout_count = defaultdict(int)
        
        # Error tracking
        self.error_types = defaultdict(int)
        self.recent_errors = deque(maxlen=100)  # Keep last 100 errors
        
        # Worker performance
        self.start_time = datetime.now(timezone.utc)
        self.last_job_time = None
        
        print("📊 TextAnalysisWorkerMetrics initialized")
    
    def record_job_start(self, job_id: str, analysis_type: str, entity_type: str, model_name: str) -> float:
        """
        Record the start of a text analysis job processing
        
        Args:
            job_id: Job identifier
            analysis_type: Type of analysis
            entity_type: Type of entity
            model_name: Model being used
            
        Returns:
            Start timestamp for duration calculation
        """
        start_time = time.time()
        
        with self._lock:
            self.total_jobs_processed += 1
            self.jobs_by_analysis_type[analysis_type] += 1
            self.last_job_time = datetime.now(timezone.utc)
        
        return start_time
    
    def record_job_success(self, start_time: float, job_id: str, analysis_type: str, 
                          model_name: str, model_response_time: Optional[float] = None):
        """
        Record successful job completion
        
        Args:
            start_time: Start timestamp from record_job_start
            job_id: Job identifier
            analysis_type: Type of analysis
            model_name: Model used
            model_response_time: Time taken by model call
        """
        end_time = time.time()
        total_processing_time = end_time - start_time
        
        with self._lock:
            self.successful_jobs += 1
            
            # Record processing times
            self.processing_times.append(total_processing_time)
            self.processing_times_by_type[analysis_type].append(total_processing_time)
            
            # Record model performance
            self.model_success_count[model_name] += 1
            
            if model_response_time is not None:
                self.model_call_times[model_name].append(model_response_time)
    
    def record_job_failure(self, start_time: float, job_id: str, analysis_type: str, 
                          model_name: str, error_type: str, error_message: str):
        """
        Record failed job
        
        Args:
            start_time: Start timestamp from record_job_start
            job_id: Job identifier
            analysis_type: Type of analysis
            model_name: Model attempted
            error_type: Type of error
            error_message: Error message
        """
        end_time = time.time()
        total_processing_time = end_time - start_time
        
        with self._lock:
            self.failed_jobs += 1
            self.failures_by_analysis_type[analysis_type] += 1
            self.model_failure_count[model_name] += 1
            self.error_types[error_type] += 1
            
            # Record processing time even for failures
            self.processing_times.append(total_processing_time)
            
            # Record error details
            error_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "job_id": job_id,
                "analysis_type": analysis_type,
                "model_name": model_name,
                "error_type": error_type,
                "error_message": error_message[:200],  # Truncate long messages
                "processing_time": total_processing_time
            }
            self.recent_errors.append(error_record)
    
    def record_model_timeout(self, model_name: str):
        """Record model timeout"""
        with self._lock:
            self.model_timeout_count[model_name] += 1
    
    def get_worker_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive worker metrics
        
        Returns:
            Dictionary containing all worker metrics
        """
        with self._lock:
            current_time = datetime.now(timezone.utc)
            uptime_seconds = (current_time - self.start_time).total_seconds()
            
            # Calculate success rate
            total_completed = self.successful_jobs + self.failed_jobs
            success_rate = (self.successful_jobs / max(total_completed, 1)) * 100
            
            # Calculate average processing times
            avg_processing_time = sum(self.processing_times) / max(len(self.processing_times), 1)
            
            # Calculate jobs per hour
            jobs_per_hour = (total_completed / max(uptime_seconds / 3600, 1/3600))
            
            # Model performance statistics
            model_stats = {}
            for model_name in set(list(self.model_success_count.keys()) + list(self.model_failure_count.keys())):
                successes = self.model_success_count[model_name]
                failures = self.model_failure_count[model_name]
                timeouts = self.model_timeout_count[model_name]
                total_calls = successes + failures
                
                avg_response_time = None
                if model_name in self.model_call_times and self.model_call_times[model_name]:
                    avg_response_time = sum(self.model_call_times[model_name]) / len(self.model_call_times[model_name])
                
                model_stats[model_name] = {
                    "total_calls": total_calls,
                    "successes": successes,
                    "failures": failures,
                    "timeouts": timeouts,
                    "success_rate": (successes / max(total_calls, 1)) * 100,
                    "avg_response_time_ms": round(avg_response_time * 1000, 2) if avg_response_time else None
                }
            
            # Analysis type performance
            analysis_type_stats = {}
            for analysis_type in self.jobs_by_analysis_type:
                total_jobs = self.jobs_by_analysis_type[analysis_type]
                failures = self.failures_by_analysis_type[analysis_type]
                successes = total_jobs - failures
                
                avg_processing_time_type = None
                if analysis_type in self.processing_times_by_type and self.processing_times_by_type[analysis_type]:
                    avg_processing_time_type = sum(self.processing_times_by_type[analysis_type]) / len(self.processing_times_by_type[analysis_type])
                
                analysis_type_stats[analysis_type] = {
                    "total_jobs": total_jobs,
                    "successes": successes,
                    "failures": failures,
                    "success_rate": (successes / max(total_jobs, 1)) * 100,
                    "avg_processing_time_ms": round(avg_processing_time_type * 1000, 2) if avg_processing_time_type else None
                }
            
            return {
                "overview": {
                    "total_jobs_processed": self.total_jobs_processed,
                    "successful_jobs": self.successful_jobs,
                    "failed_jobs": self.failed_jobs,
                    "success_rate": round(success_rate, 2),
                    "avg_processing_time_ms": round(avg_processing_time * 1000, 2),
                    "jobs_per_hour": round(jobs_per_hour, 2),
                    "uptime_seconds": round(uptime_seconds, 2),
                    "last_job_time": self.last_job_time.isoformat() if self.last_job_time else None
                },
                "by_analysis_type": dict(analysis_type_stats),
                "by_model": dict(model_stats),
                "error_analysis": {
                    "error_types": dict(self.error_types),
                    "recent_errors": list(self.recent_errors)[-10:]  # Last 10 errors
                },
                "performance": {
                    "processing_time_percentiles": self._calculate_processing_time_percentiles()
                },
                "metadata": {
                    "metrics_collected_at": current_time.isoformat(),
                    "worker_start_time": self.start_time.isoformat(),
                    "sample_sizes": {
                        "processing_time_samples": len(self.processing_times),
                        "max_samples_per_metric": self.max_samples
                    }
                }
            }
    
    def _calculate_processing_time_percentiles(self) -> Dict[str, float]:
        """Calculate processing time percentiles"""
        if not self.processing_times:
            return {}
        
        sorted_times = sorted(self.processing_times)
        n = len(sorted_times)
        
        percentiles = {}
        for p in [50, 75, 90, 95, 99]:
            index = int((p / 100) * n) - 1
            if index < 0:
                index = 0
            elif index >= n:
                index = n - 1
            percentiles[f"p{p}"] = round(sorted_times[index] * 1000, 2)  # Convert to ms
        
        return percentiles
    
    def reset_metrics(self):
        """Reset all metrics"""
        with self._lock:
            self.__init__(self.max_samples)
            print("📊 TextAnalysisWorkerMetrics reset")


# Global worker metrics instance
text_analysis_worker_metrics = TextAnalysisWorkerMetrics()