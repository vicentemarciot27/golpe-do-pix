"""
ML Prices - LLM-enhanced price analysis.

This module provides the main orchestration for:
1. Classifying product descriptions into base products
2. Generating optimized search keys for Mercado Livre
3. Scraping products from Mercado Livre
4. Analyzing search results for relevance
5. Calculating price statistics
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime

from config.ml_prices.settings import MLPricesSettings
from shared.adapters.outbound.ollama_client import OllamaClient, OllamaConfig
from shared.adapters.outbound.postgres_base_product_storage import PostgresBaseProductStorage
from shared.adapters.outbound.postgres_ecommerce_storage import PostgresEcommerceStorage
from shared.domain.base_product.entities import BaseProduct
from shared.domain.ecommerce.entities.product import Product, Currency
from shared.ports.base_product_storage import BaseProductStorage
from shared.ports.ecommerce_storage import EcommerceStorage
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper, Produto
from apps.ml_prices.services import (
    BaseProductClassifier,
    SearchKeyGenerator,
    SearchResultAnalyser,
    AnalysisResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PriceAnalysisResult:
    """Complete result of a price analysis run."""
    base_product: BaseProduct
    search_key: str
    search_attempts: int
    total_products_found: int
    relevant_products_count: int
    price_stats: dict
    analysis: AnalysisResult


class MLPricesMain:
    """
    Main orchestrator for ML Prices.

    Combines LLM-powered classification, search optimization, and
    relevance analysis for accurate price comparison.
    """

    def __init__(
        self,
        settings: MLPricesSettings,
        scraper: MercadoLivreScraper,
        product_storage: EcommerceStorage,
        base_product_storage: BaseProductStorage | None = None,
        ollama_client: OllamaClient | None = None
    ):
        self.settings = settings
        self.scraper = scraper
        self.product_storage = product_storage
        self.base_product_storage = base_product_storage

        # Initialize Ollama if base_product_storage is provided (LLM mode)
        if base_product_storage:
            ollama_config = OllamaConfig(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout=settings.ollama_timeout,
                temperature=settings.ollama_temperature
            )
            self._ollama = ollama_client or OllamaClient(ollama_config)

            self.classifier = BaseProductClassifier(
                storage=base_product_storage,
                ollama_client=self._ollama
            )
            self.key_generator = SearchKeyGenerator(ollama_client=self._ollama)
            self.analyser = SearchResultAnalyser(
                ollama_client=self._ollama,
                min_relevant_ratio=settings.min_relevant_ratio
            )
        else:
            self._ollama = None
            self.classifier = None
            self.key_generator = None
            self.analyser = None

    def run(self, search_term: str) -> None:
        """
        Simple scrape and save mode (backwards compatible).

        Args:
            search_term: Search term for Mercado Livre
        """
        products = self.scraper.scrape(search_term)
        for product in products:
            if self.product_storage.get_product_by_url(product.url) is not None:
                product_for_storage = self._format_product_for_storage(product)
                self.product_storage.update_product(product_for_storage)
                continue
            product_for_storage = self._format_product_for_storage(product)
            self.product_storage.create_product(product_for_storage)

    def analyse_product(self, description: str) -> PriceAnalysisResult:
        """
        Run complete price analysis for a product description.

        Args:
            description: Freetext product description (e.g., from auction)

        Returns:
            PriceAnalysisResult with base product, relevant prices, and statistics
        """
        if not self.classifier:
            raise RuntimeError("LLM mode not enabled. Provide base_product_storage to enable.")

        base_product, is_new = self.classifier.classify(description)
        logger.info(
            f"{'Created' if is_new else 'Found'} base product: "
            f"{base_product.brand} {base_product.name} {base_product.model}"
        )

        return self.analyse_from_base_product(base_product)

    def analyse_from_base_product(self, base_product: BaseProduct) -> PriceAnalysisResult:
        """
        Run price analysis for an existing base product.

        Args:
            base_product: Existing BaseProduct entity

        Returns:
            PriceAnalysisResult with relevant prices and statistics
        """
        if not self.key_generator or not self.analyser:
            raise RuntimeError("LLM mode not enabled. Provide base_product_storage to enable.")

        search_key_output = self.key_generator.generate_from_base_product(base_product)
        current_key = search_key_output.primary_key
        alternative_keys = search_key_output.alternatives

        analysis = None
        search_attempts = 0

        for attempt in range(self.settings.max_search_retries):
            search_attempts += 1
            logger.info(f"Search attempt {search_attempts}: '{current_key}'")

            raw_products = self.scraper.scrape(current_key)
            products = [
                self._format_product(p, current_key, base_product.id)
                for p in raw_products
            ]

            if not products:
                logger.warning(f"No products found for '{current_key}'")
                if alternative_keys:
                    current_key = alternative_keys.pop(0)
                    continue
                break

            for product in products:
                self._save_product(product)

            analysis = self.analyser.analyse_batch(base_product, products, current_key)

            if analysis.suggested_new_key and attempt < self.settings.max_search_retries - 1:
                logger.info(f"Refining search: '{current_key}' -> '{analysis.suggested_new_key}'")
                current_key = analysis.suggested_new_key
                continue

            break

        if analysis is None:
            analysis = AnalysisResult(
                relevant_products=[],
                irrelevant_products=[],
                suggested_new_key=None,
                summary="No products found"
            )

        # Update relevance in database
        for analysed in analysis.relevant_products:
            self._update_product_relevance(analysed.product, True)
        for analysed in analysis.irrelevant_products:
            self._update_product_relevance(analysed.product, False)

        price_stats = self.analyser.get_price_statistics(analysis.relevant_products)

        return PriceAnalysisResult(
            base_product=base_product,
            search_key=current_key,
            search_attempts=search_attempts,
            total_products_found=len(analysis.relevant_products) + len(analysis.irrelevant_products),
            relevant_products_count=len(analysis.relevant_products),
            price_stats=price_stats,
            analysis=analysis
        )

    def scrape_for_base_product(
        self,
        base_product: BaseProduct,
        search_key: str
    ) -> list[Product]:
        """
        Scrape products for a base product with a given search key.

        Args:
            base_product: The base product
            search_key: Search key to use

        Returns:
            List of scraped products
        """
        raw_products = self.scraper.scrape(search_key)
        products = [
            self._format_product(p, search_key, base_product.id)
            for p in raw_products
        ]

        for product in products:
            self._save_product(product)

        return products

    def _format_product_for_storage(self, product: Produto) -> Product:
        """Convert scraper Produto to domain Product (simple mode)."""
        def int_or_none(val):
            return int(val) if val is not None else None

        return Product(
            id=str(uuid.uuid4()),
            title=product.titulo,
            url=product.url,
            price=float(product.preco),
            currency=Currency.BRL,
            is_installment_payment_available=bool(product.parcelamento),
            max_installments=None,
            is_free_shipping="grátis" in (product.frete or "").lower(),
            rating=int_or_none(product.avaliacao),
            rating_amount=product.num_avaliacoes if product.num_avaliacoes is not None else None,
            sold_amount=int_or_none(product.num_vendidos),
            extraction_date=datetime.now()
        )

    def _format_product(
        self,
        produto: Produto,
        search_key: str,
        base_product_id: int | None
    ) -> Product:
        """Convert scraper Produto to domain Product (LLM mode)."""
        def int_or_none(val):
            return int(val) if val is not None else None

        return Product(
            id=str(uuid.uuid4()),
            title=produto.titulo,
            url=produto.url,
            price=float(produto.preco),
            currency=Currency.BRL,
            is_installment_payment_available=bool(produto.parcelamento),
            max_installments=None,
            is_free_shipping="grátis" in (produto.frete or "").lower(),
            rating=int_or_none(produto.avaliacao),
            rating_amount=produto.num_avaliacoes,
            sold_amount=int_or_none(produto.num_vendidos),
            extraction_date=datetime.now(),
            base_product_id=base_product_id,
            search_key=search_key,
            is_relevant=None
        )

    def _save_product(self, product: Product) -> None:
        """Save or update product in storage."""
        existing = self.product_storage.get_product_by_url(product.url)
        if existing:
            self.product_storage.update_product(product)
        else:
            self.product_storage.create_product(product)

    def _update_product_relevance(self, product: Product, is_relevant: bool) -> None:
        """Update product relevance flag in storage."""
        if hasattr(self.product_storage, 'update_relevance'):
            self.product_storage.update_relevance(product.id, is_relevant)

    def close(self) -> None:
        """Clean up resources."""
        if self._ollama:
            self._ollama.close()

    def __enter__(self) -> "MLPricesMain":
        return self

    def __exit__(self, *args) -> None:
        self.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    from config.ml_prices.settings import get_settings

    settings = get_settings()
    scraper = MercadoLivreScraper(settings)
    product_storage = PostgresEcommerceStorage()
    base_product_storage = PostgresBaseProductStorage()

    try:
        main = MLPricesMain(
            settings=settings,
            scraper=scraper,
            product_storage=product_storage,
            base_product_storage=base_product_storage
        )

        result = main.analyse_product(
            "[DI 22/1234567-8] CELULAR SMARTPHONE SAMSUNG GALAXY S24 ULTRA 256GB PRETO"
        )

        print(f"\n{'='*60}")
        print(f"Base Product: {result.base_product.brand} {result.base_product.model}")
        print(f"Search Key: {result.search_key}")
        print(f"Search Attempts: {result.search_attempts}")
        print(f"Products Found: {result.total_products_found}")
        print(f"Relevant Products: {result.relevant_products_count}")
        print(f"Price Stats: {result.price_stats}")
        print(f"Analysis Summary: {result.analysis.summary}")
        print(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        product_storage.closeall()
        base_product_storage.closeall()
