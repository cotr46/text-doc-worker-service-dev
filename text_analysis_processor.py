"""
Text Analysis Processor for handling text-based analysis models
Supports person and corporate name analysis for PEP, negative news, and law involvement
"""

import json
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from text_model_client import TextModelClient


class TextAnalysisProcessor:
    """
    Text Analysis Processor for character prescreening
    Handles PEP, negative news, and law involvement analysis
    """
    
    def __init__(self, config: Dict):
        """Initialize text analysis processor"""
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
        self.timeout_seconds = config.get("timeout_seconds", 60)
        self.enable_logging = config.get("enable_logging", True)
        
        # Initialize model client
        self.model_client = TextModelClient(config)
        
        # Model configuration
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
        
        self.log("🚀 TextAnalysisProcessor initialized")
        self.log(f"   - Base URL: {self.base_url}")
        self.log(f"   - Available models: {list(self.text_model_config.keys())}")

    def log(self, message: str) -> None:
        """Log message with timestamp"""
        if not self.enable_logging:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] TextAnalysis: {message}", flush=True)

    def process_text_analysis(self, job_data: Dict) -> Dict:
        """
        Process text-based analysis job
        
        Args:
            job_data: Job data with analysis_type, entity_type, name, etc.
        
        Returns:
            Dictionary with processing result
        """
        start_time = time.time()
        
        job_id = job_data.get("job_id", "unknown")
        analysis_type = job_data.get("analysis_type")
        entity_type = job_data.get("entity_type")
        name = job_data.get("name")
        additional_context = job_data.get("additional_context")
        
        self.log(f"🔍 Processing job {job_id}")
        self.log(f"   - Analysis: {analysis_type}, Entity: {entity_type}")
        self.log(f"   - Name: {name[:50]}..." if name and len(name) > 50 else f"   - Name: {name}")
        
        try:
            # Validate required fields
            if not all([job_id, analysis_type, entity_type, name]):
                missing = [f for f, v in [("job_id", job_id), ("analysis_type", analysis_type),
                          ("entity_type", entity_type), ("name", name)] if not v]
                raise ValueError(f"Missing required fields: {missing}")
            
            # Get model configuration
            if analysis_type not in self.text_model_config:
                raise ValueError(f"Unsupported analysis type: {analysis_type}")
            
            model_config = self.text_model_config[analysis_type]
            
            # Validate entity type
            if entity_type not in model_config["entity_types"]:
                raise ValueError(f"Entity type '{entity_type}' not supported for {analysis_type}")
            
            model_name = model_config["model"]
            
            # Call AI model
            self.log(f"🤖 Calling model: {model_name}")
            
            analysis_result = self.call_text_analysis_model(
                model_name=model_name,
                name=name,
                analysis_type=analysis_type,
                entity_type=entity_type,
                additional_context=additional_context
            )
            
            # Format result
            formatted_result = self.format_analysis_result(
                analysis_result=analysis_result,
                analysis_type=analysis_type,
                entity_type=entity_type,
                name=name,
                model_name=model_name
            )
            
            processing_time = time.time() - start_time
            
            self.log(f"✅ Job {job_id} completed in {processing_time:.2f}s")
            
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
            error_msg = f"Text analysis failed: {str(e)}"
            self.log(f"❌ {error_msg}")
            
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
        """Call text analysis AI model"""
        try:
            # Format prompt
            prompt = self.model_client.format_analysis_request(
                name=name,
                analysis_type=analysis_type,
                entity_type=entity_type,
                additional_context=additional_context
            )
            
            # Call model (no temperature parameter - model doesn't support it)
            response = self.model_client.call_model(
                model_name=model_name,
                prompt=prompt,
                max_tokens=2000
            )
            
            self.log(f"✅ Model response received in {response.response_time:.2f}s")
            
            return {
                "content": response.content,
                "model": response.model,
                "usage": response.usage,
                "response_time": response.response_time,
                "sources": response.sources
            }
            
        except Exception as e:
            raise Exception(f"Model call failed: {str(e)}")

    def format_analysis_result(self, analysis_result: Dict, analysis_type: str,
                              entity_type: str, name: str, model_name: str) -> Dict:
        """Format analysis result into standardized structure"""
        try:
            content = analysis_result.get("content", "")
            parsed_result = self.extract_json_from_content(content)
            
            return {
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name,
                "model_used": model_name,
                "confidence_score": self.extract_confidence_score(parsed_result),
                "findings": {
                    "status": self.extract_status(parsed_result),
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
                "raw_response": content
            }
        except Exception as e:
            self.log(f"⚠️ Formatting error, using fallback: {str(e)}")
            return {
                "analysis_type": analysis_type,
                "entity_type": entity_type,
                "entity_name": name,
                "model_used": model_name,
                "findings": {
                    "status": "unknown",
                    "summary": "Analysis completed but formatting failed",
                    "details": [],
                    "sources": []
                },
                "raw_response": analysis_result.get("content", "")
            }

    def extract_json_from_content(self, content: str) -> Dict:
        """Extract JSON from model response"""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            import re
            matches = re.findall(r'\{.*\}', content, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            return {}

    def extract_confidence_score(self, parsed_result: Dict) -> Optional[float]:
        """Extract confidence score"""
        for field in ["confidence", "confidence_score", "certainty"]:
            if field in parsed_result:
                try:
                    return float(parsed_result[field])
                except (ValueError, TypeError):
                    continue
        return None

    def extract_status(self, parsed_result: Dict) -> str:
        """Extract status from result"""
        for field in ["status", "result", "finding"]:
            if field in parsed_result:
                status = str(parsed_result[field]).lower()
                if any(w in status for w in ["positive", "yes", "found"]):
                    return "positive"
                elif any(w in status for w in ["negative", "no", "clean"]):
                    return "negative"
                elif any(w in status for w in ["neutral", "unclear"]):
                    return "neutral"
        return "unknown"

    def extract_summary(self, parsed_result: Dict) -> str:
        """Extract summary"""
        for field in ["summary", "description", "overview"]:
            if field in parsed_result and parsed_result[field]:
                return str(parsed_result[field])
        return "Analysis completed"

    def extract_details(self, parsed_result: Dict) -> List[Dict]:
        """Extract details"""
        details = []
        for field in ["details", "findings", "items", "results"]:
            if field in parsed_result:
                data = parsed_result[field]
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            details.append(item)
                        else:
                            details.append({"description": str(item)})
                elif isinstance(data, dict):
                    details.append(data)
        return details

    def extract_sources(self, parsed_result: Dict) -> List[str]:
        """Extract sources"""
        sources = []
        for field in ["sources", "references", "links"]:
            if field in parsed_result:
                data = parsed_result[field]
                if isinstance(data, list):
                    sources.extend([str(item) for item in data if item])
                elif data:
                    sources.append(str(data))
        return sources
