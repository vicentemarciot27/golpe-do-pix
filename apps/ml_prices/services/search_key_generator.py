"""
SearchKeyGenerator service.

Generates optimized Mercado Livre search keys from BaseProduct
information or freetext descriptions.
"""

import logging
from dataclasses import dataclass

from shared.adapters.outbound.ollama_client import OllamaClient, OllamaConfig
from shared.domain.base_product.entities import BaseProduct
from apps.ml_prices.services.schemas import SearchKeyResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Mercado Livre search optimization expert. Your task is to generate effective search queries that will find relevant product listings.

Rules for Mercado Livre searches:
1. Keep queries concise but include price-affecting attributes
2. Include brand and model when known - these are critical for matching
3. **ALWAYS include attributes that significantly affect price:**
   - Storage/capacity (128GB, 256GB, 512GB, 1TB) - CRITICAL for electronics
   - RAM (4GB, 8GB, 16GB) - Important for computers/phones
   - Processor/chipset - Important for performance-based pricing
   - Year/model year - Critical for vehicles and older electronics
   - Screen size - Important for TVs and monitors
4. **SKIP attributes that don't affect price:**
   - Color (preto, branco, azul, etc.) - cosmetic only
   - Connectivity type (WiFi, 5G, Bluetooth) - usually standard
   - Minor cosmetic features
5. Use common Brazilian Portuguese terms when appropriate
6. For electronics: brand + model + storage (e.g., "iPhone 15 Pro Max 256GB", "Galaxy S24 512GB")
7. For computers: brand + model + RAM + storage (e.g., "Dell Inspiron 15 16GB 512GB SSD")
8. For vehicles: brand + model + year (e.g., "Honda Civic 2020")
9. Avoid special characters and excessive punctuation
10. Don't include words like "novo", "usado", "original" - let the user filter these

Examples:
- BaseProduct(name="Smartphone", brand="Apple", model="iPhone 15 Pro", other={"storage": "256GB"}) → "iPhone 15 Pro 256GB"
- BaseProduct(name="Smartphone", brand="Apple", model="iPhone 15 Pro", color="Preto", other={"storage": "512GB"}) → "iPhone 15 Pro 512GB"
- BaseProduct(name="Notebook", brand="Dell", model="Inspiron 15 3520", other={"ram": "16GB", "storage": "512GB SSD"}) → "Dell Inspiron 15 3520 16GB 512GB"
- BaseProduct(name="TV", brand="Samsung", model="55TU7000") → "Samsung TV 55 TU7000"
- BaseProduct(name="Smartphone", brand="Xiaomi", model="Redmi Note 13", color="Azul", other={"storage": "128GB", "ram": "6GB"}) → "Xiaomi Redmi Note 13 128GB 6GB"

Alternative keys should try different approaches:
- More generic (just brand + model, no storage)
- Different storage variants (if original has 256GB, try 128GB or 512GB)
- Different word order
"""


@dataclass
class SearchKeyOutput:
    """Output from search key generation."""
    primary_key: str
    alternatives: list[str]
    reasoning: str


class SearchKeyGenerator:
    """
    Generates optimized search keys for Mercado Livre searches.

    Takes BaseProduct information or freetext and produces search
    queries optimized for Mercado Livre's search engine.
    """

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        ollama_config: OllamaConfig | None = None
    ):
        self._ollama = ollama_client or OllamaClient(ollama_config)

    def generate_from_base_product(
        self,
        base_product: BaseProduct
    ) -> SearchKeyOutput:
        """
        Generate search key from a BaseProduct entity.

        Args:
            base_product: The base product to generate a search key for

        Returns:
            SearchKeyOutput with primary key and alternatives
        """
        product_desc = self._format_base_product(base_product)
        return self._generate_key(product_desc)

    def generate_from_freetext(self, freetext: str) -> SearchKeyOutput:
        """
        Generate search key directly from freetext description.

        Useful when you don't have a structured BaseProduct yet.

        Args:
            freetext: Raw product description

        Returns:
            SearchKeyOutput with primary key and alternatives
        """
        return self._generate_key(freetext)

    def refine_key(
        self,
        original_key: str,
        problem: str,
        context: str | None = None
    ) -> SearchKeyOutput:
        """
        Refine a search key that didn't produce good results.

        Args:
            original_key: The search key that was used
            problem: Description of the problem (e.g., "too few results",
                     "results are for wrong product")
            context: Optional additional context about what we're looking for

        Returns:
            SearchKeyOutput with refined key and alternatives
        """
        prompt = f"""The search key "{original_key}" didn't work well.

Problem: {problem}
{f"Context: {context}" if context else ""}

Generate a better search key that addresses this problem.
Return the search key as JSON."""

        result = self._ollama.generate_structured(
            prompt=prompt,
            response_model=SearchKeyResult,
            system=SYSTEM_PROMPT
        )

        return SearchKeyOutput(
            primary_key=result.search_key,
            alternatives=result.alternative_keys,
            reasoning=result.reasoning
        )

    def _generate_key(self, product_description: str) -> SearchKeyOutput:
        """Internal method to generate search key from description."""
        prompt = f"""Generate a Mercado Livre search key for this product:

{product_description}

Return the search key as JSON."""

        result = self._ollama.generate_structured(
            prompt=prompt,
            response_model=SearchKeyResult,
            system=SYSTEM_PROMPT
        )

        logger.info(f"Generated search key: '{result.search_key}' - {result.reasoning}")

        return SearchKeyOutput(
            primary_key=result.search_key,
            alternatives=result.alternative_keys,
            reasoning=result.reasoning
        )

    def _format_base_product(self, bp: BaseProduct) -> str:
        """Format BaseProduct into a description for the LLM."""
        parts = [f"Product: {bp.name}"]

        if bp.brand:
            parts.append(f"Brand: {bp.brand}")
        if bp.model:
            parts.append(f"Model: {bp.model}")
        if bp.color:
            parts.append(f"Color: {bp.color}")
        if bp.other:
            other_str = ", ".join(f"{k}: {v}" for k, v in bp.other.items())
            parts.append(f"Attributes: {other_str}")

        return "\n".join(parts)

    def close(self) -> None:
        """Clean up resources."""
        self._ollama.close()

    def __enter__(self) -> "SearchKeyGenerator":
        return self

    def __exit__(self, *args) -> None:
        self.close()
