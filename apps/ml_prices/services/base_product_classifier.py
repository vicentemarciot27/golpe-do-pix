"""
BaseProductClassifier service.

Extracts product information from freetext descriptions and
searches/creates base products in the database for price analysis.
"""

import logging
from typing import Tuple

from shared.adapters.outbound.ollama_client import OllamaClient, OllamaConfig
from shared.domain.base_product.entities import BaseProduct
from shared.ports.base_product_storage import BaseProductStorage
from apps.ml_prices.services.schemas import ExtractedProductInfo

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a product classification expert. Your task is to extract structured product information from freetext descriptions.

Rules:
1. Extract the most specific product name (e.g., "Smartphone" not "Electronic Device")
2. Identify the brand if mentioned (normalize: "iphone" → brand="Apple", model="iPhone")
3. Extract the exact model if available
4. Color is only relevant if explicitly mentioned
5. Put product-specific attributes in 'other':
   - For phones/tablets: storage (e.g., "128GB"), RAM, connectivity (5G, WiFi)
   - For computers: processor, RAM, storage type (SSD/HDD)
   - For vehicles: year, engine, mileage
6. Set confidence based on how clear the description is
7. Brazilian Portuguese descriptions are common - handle them correctly

Examples:
- "CELULAR SAMSUNG GALAXY S24 ULTRA 256GB PRETO" → name="Smartphone", brand="Samsung", model="Galaxy S24 Ultra", color="Preto", other={"storage": "256GB"}
- "[DI 22/1234567-8] NOTEBOOK DELL INSPIRON 15" → name="Notebook", brand="Dell", model="Inspiron 15"
- "Lote com 5 iPhones 14 Pro Max" → name="Smartphone", brand="Apple", model="iPhone 14 Pro Max"
"""


class BaseProductClassifier:
    """
    Classifies freetext product descriptions into structured BaseProduct entities.

    Uses LLM to extract product information and matches/creates base products
    in the database for cross-platform price comparison.
    """

    def __init__(
        self,
        storage: BaseProductStorage,
        ollama_client: OllamaClient | None = None,
        ollama_config: OllamaConfig | None = None
    ):
        self._storage = storage
        self._ollama = ollama_client or OllamaClient(ollama_config)

    def classify(self, description: str) -> Tuple[BaseProduct, bool]:
        """
        Classify a product description and return the matching BaseProduct.

        Args:
            description: Freetext product description (auction item, etc.)

        Returns:
            Tuple of (BaseProduct, is_new) where is_new indicates if the
            product was newly created vs found in the database.
        """
        logger.info(f"Classifying product: {description[:100]}...")

        extracted = self._extract_product_info(description)
        logger.debug(f"Extracted info: {extracted}")

        existing = self._find_existing_product(extracted)
        if existing:
            logger.info(f"Found existing base product: {existing.id}")
            return existing, False

        new_product = self._create_base_product(extracted)
        logger.info(f"Created new base product: {new_product.id}")
        return new_product, True

    def classify_batch(
        self,
        descriptions: list[str]
    ) -> list[Tuple[BaseProduct, bool]]:
        """
        Classify multiple product descriptions.

        Args:
            descriptions: List of freetext product descriptions

        Returns:
            List of (BaseProduct, is_new) tuples
        """
        results = []
        for desc in descriptions:
            try:
                result = self.classify(desc)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to classify '{desc[:50]}...': {e}")
                raise
        return results

    def _extract_product_info(self, description: str) -> ExtractedProductInfo:
        """Use LLM to extract structured product information."""
        prompt = f"""Extract product information from this description:

"{description}"

Return the extracted information as JSON."""

        return self._ollama.generate_structured(
            prompt=prompt,
            response_model=ExtractedProductInfo,
            system=SYSTEM_PROMPT
        )

    def _find_existing_product(
        self,
        extracted: ExtractedProductInfo
    ) -> BaseProduct | None:
        """Search for an existing base product matching the extracted info."""
        temp_product = BaseProduct(
            name=extracted.name,
            brand=extracted.brand,
            model=extracted.model,
            color=extracted.color,
            other=extracted.other
        )
        signature = temp_product.to_search_signature()

        existing = self._storage.find_by_signature(signature)
        if existing:
            return existing

        candidates = self._storage.search(
            name=extracted.name,
            brand=extracted.brand,
            model=extracted.model,
            limit=5
        )

        for candidate in candidates:
            if temp_product.matches(candidate, strict=False):
                return candidate

        return None

    def _create_base_product(self, extracted: ExtractedProductInfo) -> BaseProduct:
        """Create a new base product from extracted information."""
        product = BaseProduct(
            name=extracted.name,
            brand=extracted.brand,
            model=extracted.model,
            color=extracted.color,
            other=extracted.other
        )
        return self._storage.create(product)

    def close(self) -> None:
        """Clean up resources."""
        self._ollama.close()

    def __enter__(self) -> "BaseProductClassifier":
        return self

    def __exit__(self, *args) -> None:
        self.close()
