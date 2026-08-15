import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Union

import google.genai as genai

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from theJSON responses."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


class GeminiClient:    
    def __init__(self, api_key: str = None, model: str = None):
        # Support multiple API keys separated by comma
        api_keys_str = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        
        if not self.api_keys:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Get a key from https://aistudio.google.com/apikey"
            )
        
        self.current_key_index = 0
        self.model = model or os.environ.get("SUNBRIDGE_MODEL", "models/gemini-3.5-flash")
        logger.info(f"Initialized with {len(self.api_keys)} API key(s)")
    
    def _get_client(self) -> genai.Client:
        """Get client with current API key."""
        return genai.Client(api_key=self.api_keys[self.current_key_index])
    
    def _rotate_key(self):
        """Switch to next API key."""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.info(f"Rotated to API key {self.current_key_index + 1}/{len(self.api_keys)}")
    
    def _is_rate_limit_error(self, error_message: str) -> bool:
        """Check if error is rate limit related."""
        return any(keyword in error_message.lower() for keyword in 
                   ["429", "503", "resource_exhausted", "quota", "rate limit", "unavailable"])
    
    def generate_text(
        self,
        system_prompt: str,
        user_content: str,
        max_retries: int = 5,
        initial_delay: float = 3.0,
    ) -> str:
        """Generate text response from Gemini with retry logic."""
        parts = [system_prompt, user_content]
        delay = initial_delay
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=parts,
                )
                return response.text.strip()
                
            except Exception as e:
                last_exception = e
                error_message = str(e)
                
                if self._is_rate_limit_error(error_message):
                    if attempt < max_retries - 1:
                        self._rotate_key()
                        logger.warning(
                            "Rate limit hit (attempt %d/%d). Retrying in %.1fs...",
                            attempt + 1,
                            max_retries,
                            delay
                        )
                        time.sleep(delay)
                        delay *= 2
                        continue
                    else:
                        raise RuntimeError(
                            f"Rate limit exceeded after {max_retries} retries."
                        ) from e
                else:
                    raise
        
        raise RuntimeError(
            f"Failed after {max_retries} retries. Last error: {last_exception}"
        ) from last_exception
        
    def generate_json(
        self,
        system_prompt: str,
        user_content,
        max_retries: int = 5,
        initial_delay: float = 3.0,
    ) -> dict:
        """Generate JSON response from Gemini with retry logic."""
        if isinstance(user_content, str):
            parts = [system_prompt, user_content]
        else:
            parts = [system_prompt] + user_content
        delay = initial_delay
        last_exception = None
        for attempt in range(max_retries):
            try:
                client = self._get_client()
                response = client.models.generate_content(
                    model=self.model,
                    contents=parts,
                )
                raw = response.text.strip()
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw).strip()
                return json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning("JSON parse failed attempt %d: %s", attempt, e)
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise
            except Exception as e:
                last_exception = e
                if self._is_rate_limit_error(str(e)):
                    if attempt < max_retries - 1:
                        self._rotate_key()
                        logger.warning("Rate limit, rotating key, retrying in %.1fs...", delay)
                        time.sleep(delay)
                        delay *= 2
                        continue
                raise
        raise RuntimeError(f"Failed after {max_retries} retries. Last error: {last_exception}")
