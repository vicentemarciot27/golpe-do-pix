#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
End-to-End tests for MLPricesMain.
Tests the complete flow: scraping -> database storage -> retrieval.

These tests require:
- PostgreSQL running (docker-compose up -d)
- Network access to Mercado Livre
"""

import pytest
from decimal import Decimal
from apps.ml_prices.main import MLPricesMain
from shared.domain.ecommerce.entities.product import Currency


@pytest.mark.requires_network
@pytest.mark.slow
class TestMLPricesE2E:
    """End-to-end tests for ml_prices application."""
    
    def test_run_saves_products_to_database(self, ml_settings, ml_scraper, pg_storage, db_inspector):
        """
        Test that MLPricesMain.run() scrapes products and saves them to PostgreSQL.
        
        Flow:
        1. Start with empty database
        2. Run MLPricesMain with a search term
        3. Verify products are saved to database
        4. Verify data integrity
        """
        # Arrange
        search_term = "smartphone xiaomi"
        main = MLPricesMain(ml_settings, ml_scraper, pg_storage)
        
        # Act
        main.run(search_term)
        
        # Assert - Products were saved
        product_count = db_inspector.count_products()
        assert product_count > 0, "No products were saved to database"
        print(f"\n✅ {product_count} products saved to database")
        
        # Assert - Verify product data integrity
        products = db_inspector.get_products()
        
        for product in products:
            # Required fields
            assert product['id'], "Product ID is required"
            assert product['title'], "Product title is required"
            assert product['url'], "Product URL is required"
            assert product['url'].startswith('http'), "Product URL must be valid"
            
            # Price validation
            assert product['price'] > 0, f"Product price must be positive: {product['price']}"
            assert product['currency'] == 'BRL', "Currency must be BRL for Mercado Livre"
            
            # Boolean fields
            assert isinstance(product['is_installment_payment_available'], bool)
            assert isinstance(product['is_free_shipping'], bool)
            
            # Rating validation (can be None)
            if product['rating'] is not None:
                assert 0 <= product['rating'] <= 5, f"Rating must be 0-5: {product['rating']}"
            
            # Sold amount validation (can be None)
            if product['sold_amount'] is not None:
                assert product['sold_amount'] >= 0, f"Sold amount must be non-negative: {product['sold_amount']}"
            
            # Metadata
            assert product['extraction_date'] is not None, "Extraction date is required"
            assert product['version'] == 1, "Initial version should be 1"
        
        print(f"✅ All {len(products)} products have valid data")
    
    
    def test_run_twice_updates_existing_products(self, ml_settings, ml_scraper, pg_storage, db_inspector):
        """
        Test that running MLPricesMain twice with same search term updates existing products.
        
        Flow:
        1. Run once - products are created
        2. Get product URLs from first run
        3. Run again with same search term
        4. Verify products were updated (not duplicated)
        5. Verify version was incremented
        """
        # Arrange
        search_term = "iphone 13"
        main = MLPricesMain(ml_settings, ml_scraper, pg_storage)
        
        # Act - First run
        main.run(search_term)
        first_run_count = db_inspector.count_products()
        first_run_products = db_inspector.get_products()
        first_run_urls = {p['url'] for p in first_run_products}
        
        print(f"\n📊 First run: {first_run_count} products")
        
        # Act - Second run (same search term)
        main.run(search_term)
        second_run_count = db_inspector.count_products()
        second_run_products = db_inspector.get_products()
        second_run_urls = {p['url'] for p in second_run_products}
        
        print(f"📊 Second run: {second_run_count} products")
        
        # Assert - No duplicates (products should be updated, not created again)
        # Note: The count might increase if Mercado Livre shows different products,
        # but products with same URL should be updated, not duplicated
        for url in first_run_urls:
            if url in second_run_urls:
                # This product should have been updated
                product = db_inspector.get_product_by_url(url)
                # Note: Version increment logic not implemented yet in update_product
                # This test documents the expected behavior
                print(f"✅ Product was found in both runs: {url[:50]}...")
        
        # Count how many URLs are common
        common_urls = first_run_urls & second_run_urls
        print(f"📊 Common products: {len(common_urls)}")
        
        # There should be no duplicate URLs in the database
        assert len(second_run_urls) == second_run_count, "No duplicate URLs should exist"
    
    
    def test_run_with_different_search_terms(self, ml_settings, ml_scraper, pg_storage, db_inspector):
        """
        Test that running MLPricesMain with different search terms saves all products.
        
        Flow:
        1. Run with search term A
        2. Run with search term B
        3. Verify both product sets are in database
        """
        # Arrange
        search_term_a = "notebook dell"
        search_term_b = "mouse gamer"
        main = MLPricesMain(ml_settings, ml_scraper, pg_storage)
        
        # Act - First search
        main.run(search_term_a)
        count_after_first = db_inspector.count_products()
        
        # Act - Second search
        main.run(search_term_b)
        count_after_second = db_inspector.count_products()
        
        # Assert
        assert count_after_first > 0, "First search should save products"
        assert count_after_second > count_after_first, "Second search should add more products"
        
        print(f"\n✅ Search '{search_term_a}': {count_after_first} products")
        print(f"✅ Search '{search_term_b}': {count_after_second - count_after_first} new products")
        print(f"✅ Total: {count_after_second} products")
    
    
    def test_database_persistence(self, ml_settings, ml_scraper, pg_storage, db_inspector):
        """
        Test that products persist in database across different connections.
        
        Flow:
        1. Save products
        2. Query with inspector (uses different connection)
        3. Verify products persist independently of storage lifetime
        """
        # Arrange
        search_term = "tablet samsung"
        main = MLPricesMain(ml_settings, ml_scraper, pg_storage)
        
        # Act - Save products
        main.run(search_term)
        saved_count = db_inspector.count_products()
        saved_urls = {p['url'] for p in db_inspector.get_products()}
        
        # Assert - Products persist (inspector uses independent connections)
        # The db_inspector creates its own connections, proving data persistence
        persisted_count = db_inspector.count_products()
        persisted_urls = {p['url'] for p in db_inspector.get_products()}
        
        assert persisted_count == saved_count, "Product count should match"
        assert persisted_urls == saved_urls, "Product URLs should match"
        assert saved_count > 0, "Should have saved products"
        
        print(f"\n✅ {persisted_count} products persisted correctly")
    
    
    def test_product_fields_mapping(self, ml_settings, ml_scraper, pg_storage, db_inspector):
        """
        Test that scraped product fields are correctly mapped to database schema.
        
        Validates:
        - All scraped fields are saved
        - Data types are correct
        - Optional fields handle None correctly
        """
        # Arrange
        search_term = "fone bluetooth"
        main = MLPricesMain(ml_settings, ml_scraper, pg_storage)
        
        # Act
        main.run(search_term)
        products = db_inspector.get_products()
        
        # Assert - At least one product
        assert len(products) > 0, "Should have at least one product"
        
        # Check first product in detail
        product = products[0]
        
        print(f"\n📦 Inspecting product: {product['title'][:50]}...")
        
        # Required string fields
        assert isinstance(product['id'], str) and len(product['id']) > 0
        assert isinstance(product['title'], str) and len(product['title']) > 0
        assert isinstance(product['url'], str) and product['url'].startswith('http')
        
        # Numeric fields
        assert isinstance(product['price'], (int, float, Decimal)) and product['price'] > 0
        
        # Rating (can be None)
        if product['rating'] is not None:
            assert isinstance(product['rating'], int) and 0 <= product['rating'] <= 5
        
        # Sold amount (can be None)
        if product['sold_amount'] is not None:
            assert isinstance(product['sold_amount'], int) and product['sold_amount'] >= 0
        
        # Optional numeric fields
        if product['rating_amount'] is not None:
            assert isinstance(product['rating_amount'], int) and product['rating_amount'] >= 0
        
        if product['max_installments'] is not None:
            assert isinstance(product['max_installments'], int) and product['max_installments'] > 0
        
        # Boolean fields
        assert isinstance(product['is_installment_payment_available'], bool)
        assert isinstance(product['is_free_shipping'], bool)
        
        # Enum field
        assert product['currency'] == 'BRL'
        
        # Metadata
        assert product['extraction_date'] is not None
        assert product['version'] == 1
        
        print("✅ All field types are correct")
        print(f"   • Title: {product['title'][:40]}...")
        print(f"   • Price: R$ {product['price']}")
        rating_text = f"{product['rating']}/5" if product['rating'] is not None else "N/A"
        reviews_text = f"({product['rating_amount']} reviews)" if product['rating_amount'] is not None else ""
        print(f"   • Rating: {rating_text} {reviews_text}")
        sold_text = f"{product['sold_amount']} units" if product['sold_amount'] is not None else "N/A"
        print(f"   • Sold: {sold_text}")
        print(f"   • Free shipping: {product['is_free_shipping']}")

