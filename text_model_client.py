"""
Text Analysis Model Client
HTTP client for text-based AI model APIs with retry logic
"""

import requests
import json
import time
import random
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class ModelResponse:
    """Structured response from text analysis model"""
    content: str
    model: str
    usage: Dict[str, Any]
    response_time: float
    status_code: int
    raw_response: Dict[str, Any]
    sources: List[Dict[str, Any]] = None


class TextModelClient:
    """HTTP client for text analysis model APIs"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize client"""
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
        self.timeout_seconds = config.get("timeout_seconds", 180)  # Increased to 180s for Google search
        self.enable_logging = config.get("enable_logging", True)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 1)
        self.max_retry_delay = config.get("max_retry_delay", 60)
        
        if not self.api_key or not self.base_url:
            raise ValueError("API key and base URL are required")
        
        self.chat_endpoint = f"{self.base_url}/api/chat/completions"
        self.log(f"🤖 TextModelClient initialized - Endpoint: {self.chat_endpoint}")
    
    def log(self, message: str) -> None:
        """Log with timestamp"""
        if not self.enable_logging:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] ModelClient: {message}", flush=True)
    
    def call_model(self, model_name: str, prompt: str, **kwargs) -> ModelResponse:
        """Call model with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return self._make_request(model_name, prompt, attempt, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not self._is_retryable(e) or attempt >= self.max_retries:
                    break
                
                delay = self._calculate_delay(attempt)
                self.log(f"⚠️ Attempt {attempt + 1} failed, retrying in {delay:.1f}s...")
                time.sleep(delay)
        
        raise Exception(f"Model call failed after {self.max_retries + 1} attempts: {last_exception}")

    def _make_request(self, model_name: str, prompt: str, attempt: int, **kwargs) -> ModelResponse:
        """Make single model request"""
        start_time = time.time()
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "tool_ids": kwargs.get("tool_ids", ["web_search_with_google"])
        }
        
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            payload["max_tokens"] = kwargs["max_tokens"]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if attempt == 0:
            self.log(f"📤 Calling model: {model_name}")
        
        response = requests.post(
            self.chat_endpoint,
            headers=headers,
            json=payload,
            timeout=self.timeout_seconds
        )
        
        response_time = time.time() - start_time
        
        # Handle errors
        if response.status_code == 429:
            raise Exception("Rate limit exceeded (HTTP 429)")
        elif response.status_code >= 500:
            raise Exception(f"Server error (HTTP {response.status_code})")
        elif response.status_code != 200:
            raise Exception(f"API error (HTTP {response.status_code}): {response.text[:200]}")
        
        # Parse response
        response_data = response.json()
        
        if "choices" not in response_data or not response_data["choices"]:
            raise Exception("Invalid response: no choices")
        
        message = response_data["choices"][0].get("message", {})
        content = message.get("content", "")
        
        if not content or content.strip() == "":
            usage = response_data.get("usage", {})
            reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
            if reasoning_tokens >= 2000:
                raise Exception("Model hit reasoning token limit - empty response")
            raise Exception("Model returned empty content")
        
        sources = response_data.get("sources", [])
        
        self.log(f"✅ Response received in {response_time:.2f}s ({len(content)} chars)")
        
        return ModelResponse(
            content=content,
            model=model_name,
            usage=response_data.get("usage", {}),
            response_time=response_time,
            status_code=response.status_code,
            raw_response=response_data,
            sources=sources
        )
    
    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable"""
        error_str = str(error).lower()
        retryable = ["timeout", "connection", "rate limit", "429", "500", "502", "503", "504"]
        non_retryable = ["400", "401", "403", "404", "reasoning token limit"]
        
        for condition in non_retryable:
            if condition in error_str:
                return False
        
        for condition in retryable:
            if condition in error_str:
                return True
        
        return True
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate retry delay with jitter"""
        delay = self.retry_delay * (2 ** attempt)
        delay *= random.uniform(0.5, 1.5)
        return min(delay, self.max_retry_delay)

    def format_analysis_request(self, name: str, analysis_type: str, entity_type: str,
                               additional_context: Optional[str] = None) -> str:
        """Format analysis request into prompt"""
        
        prompts = {
            "pep-analysis": {
                "person": f"""Analyze the following person name for Politically Exposed Person (PEP) status:

Name: {name}

Provide analysis including:
1. PEP status (Yes/No/Unknown)
2. Political positions held (if any)
3. Family connections to PEPs
4. Risk level assessment
5. Sources and references

Format response as JSON:
{{"status": "positive|negative|neutral|unknown", "summary": "...", "details": [...], "sources": [...], "confidence": 0.85}}"""
            },
            "negative-news": {
                "person": f"""Analyze the following person name for negative news:

Name: {name}

Provide analysis including:
1. Negative news status
2. Summary of negative coverage
3. Types of issues identified
4. Risk assessment
5. Sources

Format response as JSON:
{{"status": "positive|negative|neutral|unknown", "summary": "...", "details": [...], "sources": [...], "confidence": 0.85}}""",
                "corporate": f"""Analyze the following company for negative news:

Company: {name}

Provide analysis including:
1. Negative news status
2. Summary of negative coverage
3. Types of issues (regulatory, legal, financial)
4. Risk assessment
5. Sources

Format response as JSON:
{{"status": "positive|negative|neutral|unknown", "summary": "...", "details": [...], "sources": [...], "confidence": 0.85}}"""
            },
            "law-involvement": {
                "person": f"""Analyze the following person name for legal involvement:

Name: {name}

Provide analysis including:
1. Legal involvement status
2. Types of legal cases
3. Case outcomes and status
4. Risk assessment
5. Sources

Format response as JSON:
{{"status": "positive|negative|neutral|unknown", "summary": "...", "details": [...], "sources": [...], "confidence": 0.85}}""",
                "corporate": f"""Analyze the following company for legal involvement:

Company: {name}

Provide analysis including:
1. Legal involvement status
2. Types of legal cases
3. Case outcomes and status
4. Risk assessment
5. Sources

Format response as JSON:
{{"status": "positive|negative|neutral|unknown", "summary": "...", "details": [...], "sources": [...], "confidence": 0.85}}"""
            }
        }
        
        # Handle corporate-specific types
        actual_type = analysis_type
        if analysis_type == "corporate-negative-news":
            actual_type = "negative-news"
        elif analysis_type == "corporate-law-involvement":
            actual_type = "law-involvement"
        
        # Get prompt
        if actual_type in prompts and entity_type in prompts[actual_type]:
            prompt = prompts[actual_type][entity_type]
        else:
            prompt = f"""Analyze the following {entity_type} for {analysis_type}:

Name: {name}

Provide comprehensive analysis with JSON response including status, summary, details, sources, and confidence."""
        
        if additional_context:
            prompt += f"\n\nAdditional Context: {additional_context}"
        
        return prompt
