"""
SearchResultAnalyser service.

Analyzes Mercado Livre search results to filter relevant products
for price comparison against a base product.
"""

import logging
from dataclasses import dataclass

from shared.adapters.outbound.ollama_client import OllamaClient, OllamaConfig
from shared.domain.base_product.entities import BaseProduct
from shared.domain.ecommerce.entities.product import Product
from apps.ml_prices.services.schemas import (
    ProductRelevanceResult,
    BatchRelevanceResult,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a product matching expert for price comparison. Your task is to determine if products from Mercado Livre search results match a target product for price analysis.

Rules for matching:
1. Brand and model MUST match (or be equivalent - e.g., "Galaxy S24" = "SM-S921")
2. Color differences are usually ACCEPTABLE - they don't significantly affect price
3. Storage/capacity differences should be FLAGGED but may still be relevant
4. Condition matters: new vs used vs refurbished affect price significantly
5. Watch for:
   - Accessories being sold as the main product (cases, chargers, etc.)
   - Parts instead of complete products
   - Bundles vs single items
   - Generic/unbranded copies
6. Price category assessment:
   - "normal": Within expected market range
   - "premium": Significantly above average (special edition, new release)
   - "budget": Significantly below average (used, refurbished, older stock)
   - "suspicious": Too good to be true or potential scam

For batch analysis:
- Return indices of ALL relevant products (be inclusive when uncertain)
- Suggest new search key only if less than 30% of results are relevant
- Common reasons for suggesting new key:
  - Results are for wrong product variant
  - Results are mostly accessories
  - Brand is being confused with another
"""


@dataclass
class AnalysedProduct:
    """A product with its relevance analysis."""
    product: Product
    is_relevant: bool
    confidence: float
    reasoning: str
    price_category: str


@dataclass
class AnalysisResult:
    """Complete analysis result for a search."""
    relevant_products: list[AnalysedProduct]
    irrelevant_products: list[AnalysedProduct]
    suggested_new_key: str | None
    summary: str


class SearchResultAnalyser:
    """
    Analyzes search results to identify relevant products for price comparison.

    Uses LLM to intelligently filter products, handling variations like
    color differences, storage variants, and identifying non-relevant
    items like accessories or different products.
    """

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        ollama_config: OllamaConfig | None = None,
        min_relevant_ratio: float = 0.3
    ):
        self._ollama = ollama_client or OllamaClient(ollama_config)
        self._min_relevant_ratio = min_relevant_ratio

    def analyse_batch(
        self,
        base_product: BaseProduct,
        products: list[Product],
        search_key: str
    ) -> AnalysisResult:
        """
        Analyze a batch of products for relevance to a base product.

        Args:
            base_product: The target product we're looking for
            products: List of products from Mercado Livre search
            search_key: The search key used (for context)

        Returns:
            AnalysisResult with categorized products and suggestions
        """
        if not products:
            return AnalysisResult(
                relevant_products=[],
                irrelevant_products=[],
                suggested_new_key=None,
                summary="No products to analyze"
            )

        logger.info(f"Analyzing {len(products)} products for '{base_product.name}'")

        product_summaries = self._format_products_for_analysis(products)
        base_description = self._format_base_product(base_product)

        prompt = f"""Analyze these search results and identify which products match the target.

Target Product:
{base_description}

Search Key Used: "{search_key}"

Products Found (index: title - price):
{product_summaries}

Determine which products are relevant for price comparison.
Return the analysis as JSON with relevant_indices (0-based), suggested_new_key (if needed), and summary."""

        result = self._ollama.generate_structured(
            prompt=prompt,
            response_model=BatchRelevanceResult,
            system=SYSTEM_PROMPT
        )

        relevant_indices = set(result.relevant_indices)
        relevant = []
        irrelevant = []

        for i, product in enumerate(products):
            is_rel = i in relevant_indices
            analysed = AnalysedProduct(
                product=product,
                is_relevant=is_rel,
                confidence=0.8 if is_rel else 0.7,
                reasoning="Batch analysis",
                price_category="normal"
            )
            if is_rel:
                relevant.append(analysed)
            else:
                irrelevant.append(analysed)

        relevance_ratio = len(relevant) / len(products) if products else 0
        suggested_key = None

        if relevance_ratio < self._min_relevant_ratio and result.suggested_new_key:
            suggested_key = result.suggested_new_key
            logger.info(
                f"Low relevance ratio ({relevance_ratio:.1%}), "
                f"suggesting new key: {suggested_key}"
            )

        return AnalysisResult(
            relevant_products=relevant,
            irrelevant_products=irrelevant,
            suggested_new_key=suggested_key,
            summary=result.summary
        )

    def analyse_single(
        self,
        base_product: BaseProduct,
        product: Product
    ) -> AnalysedProduct:
        """
        Analyze a single product for relevance.

        Use analyse_batch for multiple products - it's more efficient.

        Args:
            base_product: The target product
            product: The product to analyze

        Returns:
            AnalysedProduct with relevance information
        """
        base_description = self._format_base_product(base_product)

        prompt = f"""Determine if this product matches the target for price comparison.

Target Product:
{base_description}

Product to Analyze:
Title: {product.title}
Price: {product.price} {product.currency.value}
URL: {product.url}

Return the analysis as JSON."""

        result = self._ollama.generate_structured(
            prompt=prompt,
            response_model=ProductRelevanceResult,
            system=SYSTEM_PROMPT
        )

        return AnalysedProduct(
            product=product,
            is_relevant=result.is_relevant,
            confidence=result.confidence,
            reasoning=result.reasoning,
            price_category=result.price_category
        )

    def get_price_statistics(
        self,
        relevant_products: list[AnalysedProduct]
    ) -> dict:
        """
        Calculate price statistics from relevant products.

        Args:
            relevant_products: List of analysed products marked as relevant

        Returns:
            Dictionary with min, max, avg, median prices
        """
        if not relevant_products:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "median": None
            }

        prices = sorted(p.product.price for p in relevant_products)
        count = len(prices)

        return {
            "count": count,
            "min": prices[0],
            "max": prices[-1],
            "avg": sum(prices) / count,
            "median": prices[count // 2] if count % 2 else
                     (prices[count // 2 - 1] + prices[count // 2]) / 2
        }

    def _format_products_for_analysis(self, products: list[Product]) -> str:
        """Format products into a summary for batch analysis."""
        lines = []
        for i, p in enumerate(products):
            lines.append(f"{i}: {p.title[:80]} - R${p.price:.2f}")
        return "\n".join(lines)

    def _format_base_product(self, bp: BaseProduct) -> str:
        """Format BaseProduct into a description for the LLM."""
        parts = [f"Name: {bp.name}"]

        if bp.brand:
            parts.append(f"Brand: {bp.brand}")
        if bp.model:
            parts.append(f"Model: {bp.model}")
        if bp.color:
            parts.append(f"Color: {bp.color} (color variations acceptable)")
        if bp.other:
            other_str = ", ".join(f"{k}: {v}" for k, v in bp.other.items())
            parts.append(f"Attributes: {other_str}")

        return "\n".join(parts)

    def close(self) -> None:
        """Clean up resources."""
        self._ollama.close()

    def __enter__(self) -> "SearchResultAnalyser":
        return self

    def __exit__(self, *args) -> None:
        self.close()
