"""
Example usage of ML Prices services.

This script demonstrates how to use the three main services:
1. BaseProductClassifier - Classify product descriptions
2. SearchKeyGenerator - Generate optimized search keys
3. SearchResultAnalyser - Analyze search results for relevance

Prerequisites:
- Ollama running with qwen3:4b model
- PostgreSQL database with schema applied
"""

import logging

from apps.ml_prices.services import (
    BaseProductClassifier,
    SearchKeyGenerator,
    SearchResultAnalyser,
)
from shared.adapters.outbound.ollama_client import OllamaConfig
from shared.adapters.outbound.postgres_base_product_storage import (
    PostgresBaseProductStorage,
)
from shared.domain.base_product.entities import BaseProduct

logging.basicConfig(level=logging.INFO)


def example_classify_product():
    """Example: Classify a product description from an auction."""
    print("\n=== Example 1: Product Classification ===\n")

    config = OllamaConfig(model="qwen3:4b")
    storage = PostgresBaseProductStorage()

    try:
        with BaseProductClassifier(storage, ollama_config=config) as classifier:
            descriptions = [
                "[DI 22/1234567-8] CELULAR SAMSUNG GALAXY S24 ULTRA 256GB PRETO",
                "NOTEBOOK DELL INSPIRON 15 3520 I5 8GB RAM 256GB SSD",
                "IPHONE 15 PRO MAX 256GB TITANIO NATURAL",
            ]

            for desc in descriptions:
                print(f"Input: {desc}")
                base_product, is_new = classifier.classify(desc)
                print(f"Result: {base_product.brand} {base_product.model}")
                print(f"  Name: {base_product.name}")
                print(f"  Color: {base_product.color}")
                print(f"  Other: {base_product.other}")
                print(f"  Is New: {is_new}")
                print()
    finally:
        storage.closeall()


def example_generate_search_key():
    """Example: Generate search keys for Mercado Livre."""
    print("\n=== Example 2: Search Key Generation ===\n")

    config = OllamaConfig(model="qwen3:4b")

    with SearchKeyGenerator(ollama_config=config) as generator:
        base_product = BaseProduct(
            name="Smartphone",
            brand="Samsung",
            model="Galaxy S24 Ultra",
            color="Preto",
            other={"storage": "256GB"},
        )

        result = generator.generate_from_base_product(base_product)
        print(f"BaseProduct: {base_product.brand} {base_product.model}")
        print(f"Primary Key: {result.primary_key}")
        print(f"Alternatives: {result.alternatives}")
        print(f"Reasoning: {result.reasoning}")
        print()

        freetext = "Lote com 3 iPhones 14 Pro Max 256GB"
        result = generator.generate_from_freetext(freetext)
        print(f"Freetext: {freetext}")
        print(f"Primary Key: {result.primary_key}")
        print(f"Alternatives: {result.alternatives}")
        print()


def example_analyse_mock_results():
    """Example: Analyze search results (with mock data)."""
    print("\n=== Example 3: Search Result Analysis ===\n")

    from datetime import datetime
    from shared.domain.ecommerce.entities.product import Currency, Product

    config = OllamaConfig(model="qwen3:4b")

    with SearchResultAnalyser(ollama_config=config) as analyser:
        base_product = BaseProduct(
            name="Smartphone",
            brand="Samsung",
            model="Galaxy S24 Ultra",
            color="Preto"
        )

        mock_products = [
            Product(
                id="1",
                title="Samsung Galaxy S24 Ultra 256GB Preto",
                url="https://ml.com/1",
                price=6499.00,
                currency=Currency.BRL,
                is_installment_payment_available=True,
                max_installments=12,
                is_free_shipping=True,
                rating=5,
                rating_amount=100,
                sold_amount=50,
                extraction_date=datetime.now(),
            ),
            Product(
                id="2",
                title="Capa Samsung Galaxy S24 Ultra Silicone",
                url="https://ml.com/2",
                price=49.90,
                currency=Currency.BRL,
                is_installment_payment_available=False,
                max_installments=None,
                is_free_shipping=False,
                rating=4,
                rating_amount=20,
                sold_amount=200,
                extraction_date=datetime.now(),
            ),
            Product(
                id="3",
                title="Samsung Galaxy S24 Ultra 512GB Titanium",
                url="https://ml.com/3",
                price=7299.00,
                currency=Currency.BRL,
                is_installment_payment_available=True,
                max_installments=12,
                is_free_shipping=True,
                rating=5,
                rating_amount=80,
                sold_amount=30,
                extraction_date=datetime.now(),
            ),
        ]

        result = analyser.analyse_batch(
            base_product, mock_products, "Samsung Galaxy S24 Ultra"
        )

        print(f"Target: {base_product.brand} {base_product.model}")
        print(f"Relevant Products: {len(result.relevant_products)}")
        print(f"Irrelevant Products: {len(result.irrelevant_products)}")
        print(f"Summary: {result.summary}")

        if result.suggested_new_key:
            print(f"Suggested New Key: {result.suggested_new_key}")

        print("\nRelevant:")
        for p in result.relevant_products:
            print(f"  - {p.product.title}: R${p.product.price}")

        print("\nIrrelevant:")
        for p in result.irrelevant_products:
            print(f"  - {p.product.title}: R${p.product.price}")

        stats = analyser.get_price_statistics(result.relevant_products)
        print(f"\nPrice Statistics: {stats}")


if __name__ == "__main__":
    print("ML Prices - Usage Examples")
    print("=" * 50)

    # Uncomment the examples you want to run:
    example_classify_product()  # Requires DB
    example_generate_search_key()  # Ollama only
    example_analyse_mock_results()  # Ollama only
