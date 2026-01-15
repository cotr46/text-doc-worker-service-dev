"""
Text Analysis Processor for handling text-based analysis models
Supports person and corporate name analysis for PEP, negative news, and law involvement
"""

import json
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import os

# Import the new model client
from text_model_client import TextModelClient


class TextAnalysisProcessor:
    """
    Text Analysis Processor for handling text-based analysis models
    Supports person and corporate name analysis for PEP, negative news, and law involvement
    """
    
    def __init__(self, config: Dict):
        """Initialize text analysis processor with configuration"""
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
        self.timeout_seconds = config.get("timeout_seconds", 60)
        self.enable_logging = config.get("enable_logging", True)
        
        # Initialize the model client
        self.model_client = TextModelClient(config)
        
        # Text analysis model configuration
        self.text_model_config = {
            "pep-analysis": {
                "model": "politically-exposed-person-v2",
                "entity_types": ["person"],
                "description": "Political Exposure Person Analysis v2"
            },
            "negative-news": {
                "model": "negative-news", 
                "entity_types": ["person"],
                "description": "Individual Negative News Analysis"
            },
            "law-involvement": {
                "model": "law-involvement",
                "entity_types": ["person"], 
                "description": "Individual Law Involvement Analysis"
            },
            "corporate-negative-news": {
                "model": "negative-news-corporate",
                "entity_types": ["corporate"],
                "description": "Corporate Negative News Analysis"
            },
            "corporate-law-involvement": {
                "model": "law-involvement-corporate",
                "entity_types": ["corporate"],
                "description": "Corporate Law Involvement Analysis"
            }
        }
        
        self.log("ðŸš€ TextAnalysisProcessor initialized")
        self.log(f"   - Base URL: {self.base_url}")
        self.log(f"   - Timeout: {self.timeout_seconds}s")
        self.log(f"   - Available models: {list(self.text_model_config.keys())}")
        self.log(f"   - Model client initialized: {self.model_client is not None}")

    def log(self, message: str) -> None:
        """Log message with timestamp"""
        if not self.enable_logging:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] TextAnalysis: {message}"
        print(log_msg, flush=True)

    def process_text_analysis(self, job_data: Dict) -> Dict:
        """
        Process text-based analysis job with enhanced error handling and logging
        
        Args:
            job_data: Dictionary containing job information with keys:
                - job_id: Unique job identifier
                - analysis_type: Type of analysis (pep-analysis, negative-news, etc.)
                - entity_type: Type of entity (person, corporate)
                - name: Name to analyze
                - additional_context: Optional additional context
                - model_name: AI model to use
        
        Returns:
            Dictionary with processing result
        """
        start_time = time.time()
        
        job_id = job_data.get("job_id", "unknown")
        analysis_type = job_data.get("analysis_type")
        entity_type = job_data.get("entity_type")
        name = job_data.get("name")
        additional_context = job_data.get("additional_context")
        
        self.log(f"ðŸ” Processing text analysis job {job_id}")
        self.log(f"   - Analysis type: {analysis_type}")
        self.log(f"   - Entity type: {entity_type}")
        self.log(f"   - Name: {name[:50]}..." if name and len(name) > 50 else f"   - Name: {name}")
        
        try:
            # Validate required fields
            if not all([job_id, analysis_type, entity_type, name]):
                missing_fields = [field for field, value in [
                    ("job_id", job_id), ("analysis_type", analysis_type),
                    ("entity_type", entity_type), ("name", name)
                ] if not value]
                error_msg = f"Missing required fields: {missing_fields}"
                self.log_error(job_id, "VALIDATION_ERROR", error_msg)
                raise ValueError(error_msg)
            
            # Get model configuration
            if analysis_type not in self.text_model_config:
                available_types = list(self.text_model_config.keys())
                error_msg = f"Unsupported analysis type '{analysis_type}'. Available: {available_types}"
                self.log_error(job_id, "CONFIGURATION_ERROR", error_msg)
                raise ValueError(error_msg)
            
            model_config = self.text_model_config[analysis_type]
            
            # Validate entity type compatibility
            if entity_type not in model_config["entity_types"]:
                supported_entities = model_config["entity_types"]
                error_msg = f"Entity type '{entity_type}' not supported for '{analysis_type}'. Supported: {supported_entities}"
                self.log_error(job_id, "COMPATIBILITY_ERROR", error_msg)
                raise ValueError(error_msg)            # Model availability check removed - model confirmed working via Postman
            # Direct call to model for better performance and reliability
            model_name = model_config["model"]
            
            # Call AI model for analysis with retry logic
            self.log(f"ðŸ¤– Calling AI model: {model_name}")
            
            try:
                analysis_result = self.call_text_analysis_model(
                    model_name=model_name,
                    name=name,
                    analysis_type=analysis_type,
                    entity_type=entity_type,
                    additional_context=additional_context
                )
            except Exception as model_error:
                error_msg = f"Model call failed: {str(model_error)}"
                self.log_error(job_id, "MODEL_ERROR", error_msg, {
                    "model_name": model_name,
                    "analysis_type": analysis_type,
                    "entity_type": entity_type
                })
                raise Exception(error_msg)
            
            # Format the result
            try:
                formatted_result = self.format_analysis_result(
                    analysis_result=analysis_result,
                    analysis_type=analysis_type,
                    entity_type=entity_type,
                    name=name,
                    model_name=model_name
                )
            except Exception as format_error:
                error_msg = f"Result formatting failed: {str(format_error)}"
                self.log_error(job_id, "FORMATTING_ERROR", error_msg, {
                    "model_name": model_name,
                    "raw_response_length": len(str(analysis_result))
                })
                raise Exception(error_msg)
            
            processing_time = time.time() - start_time
            
            self.log(f"âœ… Text analysis completed for job {job_id} in {processing_time:.2f}s")
            self.log_success(job_id, processing_time, model_name, analysis_type)
            
            return {
                "success": True,
                "result": formatted_result,
                "processing_time": round(processing_time, 2),
                "model_used": model_name,
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Text analysis failed for job {job_id}: {str(e)}"
            self.log(f"âŒ {error_msg}")
            self.log(f"âŒ Traceback: {traceback.format_exc()}")
            
            # Log structured error for monitoring
            self.log_error(job_id, "PROCESSING_ERROR", error_msg, {
                "processing_time": processing_time,
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "traceback": traceback.format_exc()
            })
            
            return {
                "success": False,
                "error": error_msg,
                "processing_time": round(processing_time, 2),
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name,
                "traceback": traceback.format_exc()
            }

    def call_text_analysis_model(self, model_name: str, name: str, analysis_type: str, 
                                entity_type: str, additional_context: Optional[str] = None) -> Dict:
        """
        Call text analysis AI model API using the model client
        
        Args:
            model_name: Name of the AI model to call
            name: Name to analyze
            analysis_type: Type of analysis being performed
            entity_type: Type of entity (person/corporate)
            additional_context: Optional additional context
            
        Returns:
            Raw response from AI model
        """
        try:
            self.log(f"ðŸ“¤ Calling model via client: {model_name}")
            self.log(f"   - Analysis type: {analysis_type}")
            self.log(f"   - Entity type: {entity_type}")
            self.log(f"   - Name: {name[:50]}..." if len(name) > 50 else f"   - Name: {name}")
            
            # Format the analysis prompt using the model client
            prompt = self.model_client.format_analysis_request(
                name=name,
                analysis_type=analysis_type,
                entity_type=entity_type,
                additional_context=additional_context
            )
            
            # Call the model using the client
            # Use temperature=1 for PEP model (doesn't support 0.1)
            temperature = 1.0 if "pep" in model_name.lower() or "politically" in model_name.lower() else 0.1
            response = self.model_client.call_model(
                model_name=model_name,
                prompt=prompt,
                temperature=temperature,  # Low temperature for consistent results
                max_tokens=2000
            )
            
            self.log(f"âœ… Model response received via client")
            self.log(f"   - Response time: {response.response_time:.2f}s")
            self.log(f"   - Content length: {len(response.content)} characters")
            self.log(f"   - Usage: {response.usage}")
            
            return {
                "content": response.content,
                "model": response.model,
                "usage": response.usage,
                "response_time": response.response_time,
                "status_code": response.status_code,
                "raw_response": response.raw_response
            }
            
        except Exception as e:
            error_msg = f"Model client call failed: {str(e)}"
            self.log(f"âŒ {error_msg}")
            raise Exception(error_msg)

    def format_analysis_result(self, analysis_result: Dict, analysis_type: str, entity_type: str, 
                             name: str, model_name: str) -> Dict:
        """
        Format the analysis result into a standardized structure
        
        Args:
            analysis_result: Raw result from AI model
            analysis_type: Type of analysis performed
            entity_type: Type of entity analyzed
            name: Name that was analyzed
            model_name: AI model used
            
        Returns:
            Formatted result dictionary
        """
        try:
            # Extract content from model response
            content = analysis_result.get("content", "")
            
            # Try to parse JSON from the content
            parsed_result = self.extract_json_from_content(content)
            
            # Create standardized result structure
            formatted_result = {
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name,
                "model_used": model_name,
                "confidence_score": self.extract_confidence_score(parsed_result),
                "findings": {
                    "status": self.extract_status(parsed_result, analysis_type),
                    "summary": self.extract_summary(parsed_result),
                    "details": self.extract_details(parsed_result),
                    "sources": self.extract_sources(parsed_result),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                },
                "metadata": {
                    "processing_time": analysis_result.get("response_time", 0),
                    "model_version": model_name,
                    "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                    "usage": analysis_result.get("usage", {})
                },
                "raw_response": content,  # Include raw response for debugging
                    "parsed_result": parsed_result  # Include parsed result
            }
            
            return formatted_result
            
        except Exception as e:
            self.log(f"âš ï¸ Error formatting result, using fallback: {str(e)}")
            
            # Fallback formatting
            return {
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name,
                "model_used": model_name,
                "confidence_score": None,
                "findings": {
                    "status": "unknown",
                    "summary": "Analysis completed but result formatting failed",
                    "details": [{"error": "Result formatting failed", "raw_content": content[:500]}],
                    "sources": [],
                    "last_updated": datetime.now(timezone.utc).isoformat()
                },
                "metadata": {
                    "processing_time": analysis_result.get("response_time", 0),
                    "model_version": model_name,
                    "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                    "formatting_error": str(e)
                },
                "raw_response": content
            }

    def extract_json_from_content(self, content: str) -> Dict:
        """Extract JSON data from model response content"""
        try:
            # Log content for debugging
            self.log(f"ðŸ“„ Extracting JSON from content (length: {len(content)} chars)")
            if len(content) > 0:
                self.log(f"   Preview: {content[:200]}")
            # Try to parse the entire content as JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON within the content
            import re
            json_pattern = r'\{.*\}'
            matches = re.findall(json_pattern, content, re.DOTALL)
            
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            
            # If no valid JSON found, return empty dict
            return {}

    def extract_confidence_score(self, parsed_result: Dict) -> Optional[float]:
        """Extract confidence score from parsed result"""
        # Look for common confidence score fields
        confidence_fields = ["confidence", "confidence_score", "certainty", "probability"]
        
        for field in confidence_fields:
            if field in parsed_result:
                try:
                    return float(parsed_result[field])
                except (ValueError, TypeError):
                    continue
        
        return None

    def extract_status(self, parsed_result: Dict, analysis_type: str) -> str:
        """Extract status from parsed result based on analysis type"""
        # Common status fields
        status_fields = ["status", "result", "finding", "conclusion"]
        
        for field in status_fields:
            if field in parsed_result:
                status = str(parsed_result[field]).lower()
                
                # Normalize status values
                if any(word in status for word in ["positive", "yes", "found", "identified"]):
                    return "positive"
                elif any(word in status for word in ["negative", "no", "not found", "clean"]):
                    return "negative"
                elif any(word in status for word in ["neutral", "unclear", "mixed"]):
                    return "neutral"
                else:
                    return "unknown"
        
        return "unknown"

    def extract_summary(self, parsed_result: Dict) -> str:
        """Extract summary from parsed result"""
        summary_fields = ["summary", "description", "overview", "analysis"]
        
        for field in summary_fields:
            if field in parsed_result and parsed_result[field]:
                return str(parsed_result[field])
        
        return "Analysis completed"

    def extract_details(self, parsed_result: Dict) -> List[Dict]:
        """Extract detailed findings from parsed result"""
        details = []
        
        # Look for details in various fields
        detail_fields = ["details", "findings", "items", "results", "cases"]
        
        for field in detail_fields:
            if field in parsed_result:
                field_data = parsed_result[field]
                
                if isinstance(field_data, list):
                    for item in field_data:
                        if isinstance(item, dict):
                            details.append(item)
                        else:
                            details.append({"description": str(item)})
                elif isinstance(field_data, dict):
                    details.append(field_data)
                elif field_data:
                    details.append({"description": str(field_data)})
        
        # If no structured details found, create from other fields
        if not details:
            for key, value in parsed_result.items():
                if key not in ["status", "summary", "confidence", "sources"] and value:
                    details.append({"field": key, "value": str(value)})
        
        return details

    def extract_sources(self, parsed_result: Dict) -> List[str]:
        """Extract sources from parsed result"""
        sources = []
        
        source_fields = ["sources", "references", "links", "urls"]
        
        for field in source_fields:
            if field in parsed_result:
                field_data = parsed_result[field]
                
                if isinstance(field_data, list):
                    sources.extend([str(item) for item in field_data if item])
                elif field_data:
                    sources.append(str(field_data))
        
        return sources

    def check_model_availability(self, model_name: str) -> bool:
        """
        Check if a text analysis model is available
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            return self.model_client.validate_model_availability(model_name)
        except Exception as e:
            self.log(f"âŒ Error checking model availability for {model_name}: {str(e)}")
            return False
    
    def get_available_models(self) -> Dict[str, bool]:
        """
        Get availability status for all configured text analysis models
        
        Returns:
            Dictionary mapping model names to availability status
        """
        availability = {}
        for analysis_type, config in self.text_model_config.items():
            model_name = config["model"]
            availability[model_name] = self.check_model_availability(model_name)
        return availability

    def log_error(self, job_id: str, error_type: str, error_message: str, context: Dict = None) -> None:
        """
        Log structured error information for monitoring
        
        Args:
            job_id: Job identifier
            error_type: Type of error (VALIDATION_ERROR, MODEL_ERROR, etc.)
            error_message: Error message
            context: Additional context information
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        error_log = {
            "timestamp": timestamp,
            "job_id": job_id,
            "error_type": error_type,
            "error_message": error_message,
            "service": "text_analysis_processor"
        }
        
        if context:
            error_log["context"] = context
        
        # Log as structured JSON for monitoring systems
        self.log(f"ðŸš¨ ERROR: {json.dumps(error_log)}")
        
        # Also log human-readable format
        self.log(f"âŒ [{error_type}] Job {job_id}: {error_message}")
    
    def log_success(self, job_id: str, processing_time: float, model_name: str, analysis_type: str) -> None:
        """
        Log successful processing for monitoring
        
        Args:
            job_id: Job identifier
            processing_time: Time taken to process
            model_name: Model used
            analysis_type: Type of analysis performed
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        success_log = {
            "timestamp": timestamp,
            "job_id": job_id,
            "processing_time": processing_time,
            "model_name": model_name,
            "analysis_type": analysis_type,
            "service": "text_analysis_processor",
            "status": "success"
        }
        
        # Log as structured JSON for monitoring systems
        self.log(f"âœ… SUCCESS: {json.dumps(success_log)}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for monitoring (placeholder for future implementation)
        
        Returns:
            Dictionary with error statistics
        """
        # This would typically connect to a logging/monitoring system
        # For now, return basic information
        return {
            "service": "text_analysis_processor",
            "available_models": self.get_available_models(),
            "configured_analysis_types": list(self.text_model_config.keys()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


