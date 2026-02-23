import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Type, TypeVar

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class OllamaConfig:
    """Configuration for Ollama client."""
    base_url: str = "http://localhost:11434"
    model: str = "qwen3:4b"
    timeout: float = 120.0
    temperature: float = 0.1
    # For qwen3 models that use <think> tags
    strip_thinking: bool = True


class OllamaClient:
    """
    Client for Ollama API with structured output support.

    Uses Ollama's native JSON mode with format parameter for
    guaranteed structured responses matching Pydantic schemas.
    """

    def __init__(self, config: OllamaConfig | None = None):
        self.config = config or OllamaConfig()
        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout
        )

    def check_model_available(self) -> bool:
        """Check if the configured model is available in Ollama."""
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            # Check for exact match or partial match (e.g., "qwen3:4b" in "qwen3:4b-fp16")
            return any(
                self.config.model == name or self.config.model in name
                for name in model_names
            )
        except Exception as e:
            logger.warning(f"Failed to check model availability: {e}")
            return False

    def list_models(self) -> list[str]:
        """List available models in Ollama."""
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return [m.get("name", "") for m in models]
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            return []

    def generate(self, prompt: str, system: str | None = None) -> str:
        """
        Generate a text response from the model.

        Args:
            prompt: The user prompt
            system: Optional system prompt

        Returns:
            The model's text response
        """
        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature
            }
        }

        if system:
            payload["system"] = system

        response = self._client.post("/api/generate", json=payload)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system: str | None = None
    ) -> T:
        """
        Generate a structured response matching a Pydantic model.

        Uses Ollama's format parameter for guaranteed JSON structure.

        Args:
            prompt: The user prompt
            response_model: Pydantic model class defining the response schema
            system: Optional system prompt

        Returns:
            Instance of response_model with the model's response
        """
        schema = response_model.model_json_schema()

        # Build prompt for structured JSON output
        # Only include required fields to avoid confusion
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        fields_desc = []
        for field_name in required:
            if field_name in properties:
                prop = properties[field_name]
                desc = prop.get("description", "")
                fields_desc.append(f'  "{field_name}": <{desc}>')

        for field_name in properties:
            if field_name not in required:
                prop = properties[field_name]
                desc = prop.get("description", "")
                fields_desc.append(f'  "{field_name}": <{desc}> (optional)')

        fields_example = ",\n".join(fields_desc)

        enhanced_prompt = f"""{prompt}

Respond with a JSON object with these fields:
{{
{fields_example}
}}

Fill in the actual values based on the input. Output ONLY valid JSON."""

        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": enhanced_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.config.temperature
            }
        }

        if system:
            payload["system"] = system

        logger.debug(f"Ollama request model={self.config.model}")
        response = self._client.post("/api/generate", json=payload)
        response.raise_for_status()

        result = response.json()
        response_text = result.get("response", "")

        # qwen3 models put structured output in 'thinking' field when using JSON format
        if not response_text and "thinking" in result:
            response_text = result.get("thinking", "")
            logger.debug("Using 'thinking' field for response (qwen3 behavior)")

        # Log raw response for debugging
        logger.debug(f"Ollama raw response ({len(response_text)} chars): {response_text[:500]}")

        # Strip thinking tags if present (qwen3 models)
        if self.config.strip_thinking and response_text:
            cleaned = self._strip_thinking_tags(response_text)
            if cleaned != response_text:
                logger.info(f"After stripping thinking tags ({len(cleaned)} chars): {cleaned[:500]}")
            response_text = cleaned

        # Handle empty response
        if not response_text or not response_text.strip():
            available = self.list_models()
            logger.error(f"Empty response from model. Available models: {available}")
            logger.error(f"Full raw result: {result}")
            raise ValueError(
                f"Empty response from model '{self.config.model}'. "
                f"Available models: {available}. "
                f"Try: ollama pull {self.config.model}"
            )

        # Try to extract JSON from response
        response_text = self._extract_json(response_text)

        try:
            parsed = json.loads(response_text)
            return response_model.model_validate(parsed)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response_text}")
            raise ValueError(f"Invalid JSON response from model: {e}")
        except Exception as e:
            logger.error(f"Failed to validate response: {response_text}")
            raise ValueError(f"Response validation failed: {e}")

    def _strip_thinking_tags(self, text: str) -> str:
        """Remove <think>...</think> blocks from qwen3 responses."""
        # Remove thinking blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        return text.strip()

    def _extract_json(self, text: str) -> str:
        """Extract JSON object from text that might have extra content."""
        text = text.strip()

        # If it already looks like JSON, return it
        if text.startswith('{') and text.endswith('}'):
            return text

        # Try to find JSON object in the text
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if match:
            return match.group(0)

        # Try to find JSON between code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return match.group(1)

        return text

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "OllamaClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
