import os
import json
import time
import logging
from typing import Any, Callable, Dict, Optional, Type, Union
from google import genai
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from .errors import AIExtractionError
from .logger import logger

class AIExtractor:
    """
    Resilient wrapper for Gemini AI extraction with retries and fallbacks.
    """

    def __init__(
        self,
        api_key: str,
        primary_model: str = "gemini-2.0-flash-001",
        fallback_model: str = "gemini-2.0-flash-lite-preview-02-05",
        mock_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
        mock_env_var: str = "MOCK_AI"
    ):
        self.client = genai.Client(api_key=api_key)
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.mock_fn = mock_fn
        self.mock_env_var = mock_env_var

    def _is_offline(self) -> bool:
        return os.getenv(self.mock_env_var, "false").lower() == "true"

    def extract(
        self, 
        prompt: str, 
        response_model: Optional[Type[BaseModel]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calls the LLM to extract structured data.
        Implements the retry chain: 5 attempts -> Fallback Model -> Mock Fn.
        """
        if self._is_offline():
            logger.info("AIExtractor: Offline mode active. Calling mock_fn.")
            return self._call_mock(prompt)

        try:
            return self._extract_with_retry(prompt, response_model, config)
        except Exception as e:
            logger.warning(f"AIExtractor: Primary chain failed: {str(e)}. Attempting mock_fn fallback.")
            return self._call_mock(prompt, original_error=e)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(min=4, max=20),
        before_sleep=before_sleep_log(logger, logging.INFO),
        reraise=True
    )
    def _extract_with_retry(
        self, 
        prompt: str, 
        response_model: Optional[Type[BaseModel]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # Determine which model to use based on attempt number
        # tenacity doesn't easily expose attempt number to the decorated function
        # but we can track it or just try primary then fallback.
        # For simplicity and following the design, we attempt primary first.
        
        current_model = self.primary_model
        
        try:
            response = self.client.models.generate_content(
                model=current_model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": response_model,
                    **(config or {})
                }
            )
            
            # If we get a valid response, parse and return
            if response.text:
                return json.loads(response.text)
            
            raise AIExtractionError("Empty response from Gemini")

        except Exception as e:
            logger.warning(f"AIExtractor: Failed with {current_model}: {str(e)}")
            
            # Try fallback model if it's not the same
            if self.fallback_model and self.fallback_model != current_model:
                logger.info(f"AIExtractor: Attempting fallback model {self.fallback_model}")
                try:
                    response = self.client.models.generate_content(
                        model=self.fallback_model,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": response_model,
                            **(config or {})
                        }
                    )
                    if response.text:
                        return json.loads(response.text)
                except Exception as fe:
                    logger.warning(f"AIExtractor: Fallback model also failed: {str(fe)}")
            
            # Re-raise to trigger tenacity retry
            raise

    def _call_mock(self, prompt: str, original_error: Optional[Exception] = None) -> Dict[str, Any]:
        if self.mock_fn:
            try:
                return self.mock_fn(prompt)
            except Exception as me:
                logger.error(f"AIExtractor: Mock function failed: {str(me)}")
                if original_error:
                    raise AIExtractionError(f"AI failed and mock failed: {str(me)}") from original_error
                raise AIExtractionError(f"Mock function failed: {str(me)}") from me
        
        if original_error:
            raise AIExtractionError(f"AI extraction failed after all retries: {str(original_error)}") from original_error
        
        raise AIExtractionError("AI extraction failed and no mock_fn provided.")
