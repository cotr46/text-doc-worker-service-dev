"""
Text Analysis Model Client for handling HTTP requests to text-based AI models
Provides authentication, request formatting, response processing, and error handling with retry logic
"""

import requests
import json
import time
import logging
import random
from datetime import datetime, timezone
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


class TextModelClient:
    """
    HTTP client for text-based analysis model APIs
    Handles authentication, request formatting, response processing, and error handling with retry logic
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize text model client with configuration
        
        Args:
            config: Configuration dictionary with keys:
                - api_key: API key for authentication
                - base_url: Base URL for the model API
                - timeout_seconds: Request timeout in seconds
                - enable_logging: Whether to enable logging
                - max_retries: Maximum number of retry attempts (default: 3)
                - retry_delay: Base delay between retries in seconds (default: 1)
                - max_retry_delay: Maximum delay between retries in seconds (default: 60)
        """
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")
        self.timeout_seconds = config.get("timeout_seconds", 60)
        self.enable_logging = config.get("enable_logging", True)
        
        # Retry configuration
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 1)
        self.max_retry_delay = config.get("max_retry_delay", 60)
        
        # Validate required configuration
        if not self.api_key:
            raise ValueError("API key is required for text model client")
        if not self.base_url:
            raise ValueError("Base URL is required for text model client")
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        if self.enable_logging:
            logging.basicConfig(level=logging.INFO)
        
        # API endpoint - FIXED: Use correct /api/chat/completions endpoint
        self.chat_endpoint = f"{self.base_url}/api/chat/completions"
        
        self.log(f"🤖 TextModelClient initialized")
        self.log(f"   - Base URL: {self.base_url}")
        self.log(f"   - Chat endpoint: {self.chat_endpoint}")
        self.log(f"   - Timeout: {self.timeout_seconds}s")
        self.log(f"   - Max retries: {self.max_retries}")
        self.log(f"   - Retry delay: {self.retry_delay}s - {self.max_retry_delay}s")
    
    def log(self, message: str) -> None:
        """Log message with timestamp"""
        if not self.enable_logging:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] ModelClient: {message}"
        print(log_msg, flush=True)
        if self.logger:
            self.logger.info(message)
    
    def call_model(self, model_name: str, prompt: str, **kwargs) -> ModelResponse:
        """
        Call text analysis model with the given prompt, including retry logic and error handling
        
        Args:
            model_name: Name of the AI model to call
            prompt: Text prompt to send to the model
            **kwargs: Additional parameters for the model call
                - temperature: Model temperature (optional, uses model default if not specified)
                - max_tokens: Maximum tokens to generate (default: 2000)
                - stream: Whether to stream response (default: False)
                - tool_ids: List of tool IDs to enable (e.g., ["web_search_with_google"])
        
        Returns:
            ModelResponse object with structured response data
            
        Raises:
            Exception: If the model call fails after all retries
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                return self._make_model_request(model_name, prompt, attempt, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Check if this is a retryable error
                if not self._is_retryable_error(e):
                    self.log(f"❌ Non-retryable error on attempt {attempt + 1}: {str(e)}")
                    raise e
                
                # If this was the last attempt, raise the exception
                if attempt >= self.max_retries:
                    self.log(f"❌ All {self.max_retries + 1} attempts failed for model {model_name}")
                    break
                
                # Calculate delay with exponential backoff and jitter
                delay = self._calculate_retry_delay(attempt)
                self.log(f"⚠️ Attempt {attempt + 1} failed: {str(e)}")
                self.log(f"🔄 Retrying in {delay:.2f}s... ({attempt + 1}/{self.max_retries} retries)")
                
                time.sleep(delay)
        
        # If we get here, all retries failed
        error_msg = f"Model call failed after {self.max_retries + 1} attempts. Last error: {str(last_exception)}"
        self.log(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    def _make_model_request(self, model_name: str, prompt: str, attempt: int, **kwargs) -> ModelResponse:
        """
        Make a single model request attempt
        
        Args:
            model_name: Name of the AI model to call
            prompt: Text prompt to send to the model
            attempt: Current attempt number (0-based)
            **kwargs: Additional parameters for the model call
        
        Returns:
            ModelResponse object with structured response data
        """
        start_time = time.time()
        
        try:
            # Prepare request payload
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": kwargs.get("max_tokens", 2000),
                "stream": kwargs.get("stream", False)
            }
            
            # Add temperature only if specified (let model use default otherwise)
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            
            # Add tool_ids if specified (for web search, etc.)
            if "tool_ids" in kwargs and kwargs["tool_ids"]:
                payload["tool_ids"] = kwargs["tool_ids"]
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "TextAnalysisProcessor/1.0"
            }
            
            if attempt == 0:  # Only log details on first attempt
                self.log(f"📤 Calling model: {model_name}")
                self.log(f"   - Endpoint: {self.chat_endpoint}")
                self.log(f"   - Prompt length: {len(prompt)} characters")
                self.log(f"   - Temperature: {payload.get('temperature', 'default')}")
                self.log(f"   - Max tokens: {payload['max_tokens']}")
            else:
                self.log(f"📤 Retry attempt {attempt + 1} for model: {model_name}")
            
            # Make HTTP request
            response = requests.post(
                self.chat_endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds
            )
            
            response_time = time.time() - start_time
            
            # Check response status
            if response.status_code == 429:
                # Rate limit error - always retryable
                error_msg = f"Rate limit exceeded (HTTP 429). Response: {response.text[:200]}"
                raise Exception(error_msg)
            elif response.status_code >= 500:
                # Server error - retryable
                error_msg = f"Server error (HTTP {response.status_code}). Response: {response.text[:200]}"
                raise Exception(error_msg)
            elif response.status_code == 503:
                # Service unavailable - retryable
                error_msg = f"Service unavailable (HTTP 503). Model may be loading. Response: {response.text[:200]}"
                raise Exception(error_msg)
            elif response.status_code != 200:
                # Other client errors - not retryable
                error_msg = f"Model API returned status {response.status_code}: {response.text[:200]}"
                self.log(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # Parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse model response as JSON: {str(e)}. Response: {response.text[:200]}"
                self.log(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # Validate response structure
            if "choices" not in response_data or not response_data["choices"]:
                error_msg = f"Invalid model response: no choices returned. Response: {json.dumps(response_data)[:200]}"
                self.log(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            # Extract content from response
            choice = response_data["choices"][0]
            if "message" not in choice or "content" not in choice["message"]:
                error_msg = f"Invalid model response: no message content. Choice: {json.dumps(choice)[:200]}"
                self.log(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            content = choice["message"]["content"]
            usage = response_data.get("usage", {})
            
            if attempt == 0:
                self.log(f"✅ Model response received")
            else:
                self.log(f"✅ Model response received on retry attempt {attempt + 1}")
            self.log(f"   - Response time: {response_time:.2f}s")
            self.log(f"   - Content length: {len(content)} characters")
            self.log(f"   - Usage: {usage}")
            
            return ModelResponse(
                content=content,
                model=model_name,
                usage=usage,
                response_time=response_time,
                status_code=response.status_code,
                raw_response=response_data
            )
            
        except requests.exceptions.Timeout:
            error_msg = f"Model API call timed out after {self.timeout_seconds}s"
            self.log(f"❌ {error_msg}")
            raise Exception(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Failed to connect to model API: {str(e)}"
            self.log(f"❌ {error_msg}")
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Model API request failed: {str(e)}"
            self.log(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            # Re-raise with additional context if not already handled
            if "Model API" not in str(e) and "Invalid model response" not in str(e):
                error_msg = f"Model client error: {str(e)}"
                self.log(f"❌ {error_msg}")
                raise Exception(error_msg)
            else:
                raise e
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error is retryable
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if the error should be retried, False otherwise
        """
        error_str = str(error).lower()
        
        # Retryable conditions
        retryable_conditions = [
            "timeout",
            "connection",
            "rate limit",
            "429",  # Rate limit HTTP status
            "500",  # Internal server error
            "502",  # Bad gateway
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "service unavailable",
            "server error",
            "network",
            "dns",
            "ssl"
        ]
        
        # Check if any retryable condition is present
        for condition in retryable_conditions:
            if condition in error_str:
                return True
        
        # Non-retryable conditions (client errors)
        non_retryable_conditions = [
            "400",  # Bad request
            "401",  # Unauthorized
            "403",  # Forbidden
            "404",  # Not found
            "invalid model response",
            "failed to parse",
            "no choices returned",
            "no message content"
        ]
        
        # Check if any non-retryable condition is present
        for condition in non_retryable_conditions:
            if condition in error_str:
                return False
        
        # Default to retryable for unknown errors
        return True
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff and jitter
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: base_delay * (2 ^ attempt)
        delay = self.retry_delay * (2 ** attempt)
        
        # Add jitter (random factor between 0.5 and 1.5)
        jitter = random.uniform(0.5, 1.5)
        delay *= jitter
        
        # Cap at maximum delay
        delay = min(delay, self.max_retry_delay)
        
        return delay
    
    def validate_model_availability(self, model_name: str) -> bool:
        """
        Check if a model is available by making a simple test call with retry logic
        
        Args:
            model_name: Name of the model to test
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            self.log(f"🔍 Checking availability of model: {model_name}")
            
            # Make a simple test call with minimal tokens to reduce cost
            test_prompt = "Test"
            response = self.call_model(
                model_name=model_name,
                prompt=test_prompt,
                max_tokens=5,  # Minimal tokens for availability check
                temperature=0.1
            )
            
            # If we get a response, the model is available
            if response.content:
                self.log(f"✅ Model {model_name} is available")
                return True
            else:
                self.log(f"⚠️ Model {model_name} returned empty response")
                return False
                
        except Exception as e:
            self.log(f"❌ Model {model_name} is not available: {str(e)}")
            return False
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """
        Get information about a specific model
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with model information
        """
        return {
            "name": model_name,
            "endpoint": self.chat_endpoint,
            "timeout": self.timeout_seconds,
            "available": self.validate_model_availability(model_name)
        }
    
    def format_analysis_request(self, name: str, analysis_type: str, entity_type: str, 
                              additional_context: Optional[str] = None) -> str:
        """
        Format a text analysis request into a proper prompt
        
        Args:
            name: Name to analyze
            analysis_type: Type of analysis to perform
            entity_type: Type of entity (person/corporate)
            additional_context: Optional additional context
            
        Returns:
            Formatted prompt string
        """
        # Base prompt templates for different analysis types
        prompt_templates = {
            "pep-analysis": {
                "person": f"""Analyze the following person name for Politically Exposed Person (PEP) status:

Name: {name}

Provide a comprehensive analysis including:
1. PEP status (Yes/No/Unknown)
2. Political positions held (if any)
3. Family connections to PEPs (if any)
4. Risk level assessment
5. Sources and references

Format the response as structured JSON with the following structure:
{{
    "status": "positive|negative|neutral|unknown",
    "summary": "Brief summary of findings",
    "details": [
        {{"type": "position", "description": "Political position details"}},
        {{"type": "connection", "description": "Family/associate connections"}},
        {{"type": "risk", "description": "Risk assessment details"}}
    ],
    "sources": ["source1", "source2"],
    "confidence": 0.85
}}"""
            },
            "negative-news": {
                "person": f"""Analyze the following person name for negative news and media coverage:

Name: {name}

Provide a comprehensive analysis including:
1. Negative news status (Positive/Negative/Neutral/Unknown)
2. Summary of negative coverage (if any)
3. Types of issues identified
4. Risk assessment
5. Sources and references

Format the response as structured JSON with the following structure:
{{
    "status": "positive|negative|neutral|unknown",
    "summary": "Brief summary of findings",
    "details": [
        {{"type": "news", "description": "Negative news details"}},
        {{"type": "issue", "description": "Type of issues identified"}},
        {{"type": "risk", "description": "Risk assessment details"}}
    ],
    "sources": ["source1", "source2"],
    "confidence": 0.85
}}""",
                "corporate": f"""Analyze the following corporate entity for negative news and media coverage:

Company: {name}

Provide a comprehensive analysis including:
1. Negative news status (Positive/Negative/Neutral/Unknown)
2. Summary of negative coverage (if any)
3. Types of issues identified (regulatory, legal, financial, etc.)
4. Risk assessment
5. Sources and references

Format the response as structured JSON with the following structure:
{{
    "status": "positive|negative|neutral|unknown",
    "summary": "Brief summary of findings",
    "details": [
        {{"type": "news", "description": "Negative news details"}},
        {{"type": "issue", "description": "Type of issues identified"}},
        {{"type": "risk", "description": "Risk assessment details"}}
    ],
    "sources": ["source1", "source2"],
    "confidence": 0.85
}}"""
            },
            "law-involvement": {
                "person": f"""Analyze the following person name for legal involvement and court cases:

Name: {name}

Provide a comprehensive analysis including:
1. Legal involvement status (Yes/No/Unknown)
2. Types of legal cases (criminal, civil, regulatory)
3. Case outcomes and current status
4. Risk assessment
5. Sources and references

Format the response as structured JSON with the following structure:
{{
    "status": "positive|negative|neutral|unknown",
    "summary": "Brief summary of findings",
    "details": [
        {{"type": "case", "description": "Legal case details"}},
        {{"type": "outcome", "description": "Case outcomes"}},
        {{"type": "risk", "description": "Risk assessment details"}}
    ],
    "sources": ["source1", "source2"],
    "confidence": 0.85
}}""",
                "corporate": f"""Analyze the following corporate entity for legal involvement and court cases:

Company: {name}

Provide a comprehensive analysis including:
1. Legal involvement status (Yes/No/Unknown)
2. Types of legal cases (regulatory, civil, criminal, compliance)
3. Case outcomes and current status
4. Risk assessment
5. Sources and references

Format the response as structured JSON with the following structure:
{{
    "status": "positive|negative|neutral|unknown",
    "summary": "Brief summary of findings",
    "details": [
        {{"type": "case", "description": "Legal case details"}},
        {{"type": "outcome", "description": "Case outcomes"}},
        {{"type": "risk", "description": "Risk assessment details"}}
    ],
    "sources": ["source1", "source2"],
    "confidence": 0.85
}}"""
            }
        }
        
        # Handle corporate-specific analysis types
        if analysis_type == "corporate-negative-news":
            analysis_type = "negative-news"
        elif analysis_type == "corporate-law-involvement":
            analysis_type = "law-involvement"
        
        # Get the appropriate prompt template
        if analysis_type in prompt_templates and entity_type in prompt_templates[analysis_type]:
            prompt = prompt_templates[analysis_type][entity_type]
        else:
            # Fallback generic prompt
            prompt = f"""Analyze the following {entity_type} name for {analysis_type}:

Name: {name}

Provide a comprehensive analysis with structured JSON response including status, summary, details, sources, and confidence score."""
        
        # Add additional context if provided
        if additional_context:
            prompt += f"\n\nAdditional Context: {additional_context}"
        
        return prompt
