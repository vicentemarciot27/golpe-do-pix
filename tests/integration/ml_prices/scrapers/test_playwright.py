#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Integration tests for Mercado Livre Playwright scraper.
Tests the full scraping flow against real Mercado Livre pages.

These tests require:
  - playwright installed with browsers: playwright install chromium
  - Internet connection to access Mercado Livre
  - Reasonable timeout settings for network operations
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.ml_prices.scrapers.playwright import (
    Produto,
    scrape_mercadolivre,
    abrir_pagina_busca,
    obter_cards,
    esperar_carregar,
    aceitar_cookies,
    pagina_atual_num,
    tem_proxima_pagina,
    ir_para_proxima_pagina,
)
from playwright.sync_api import sync_playwright


class TestScrapeMercadoLivre:
    """Integration tests for the main scraping function."""

    def test_scrape_single_page(self, ml_scraper, results):
        """Test scraping a single page of results."""
        produtos = ml_scraper.scrape(
            termo_busca="smartphone",
            max_pages=1,
        )
        
        # Store results for validation
        results.store("test_scrape_single_page", {
            "produtos": produtos,
            "count": len(produtos),
            "search_term": "smartphone",
        })
        
        # Should return at least some products
        assert len(produtos) > 0, "Should find at least one product"
        
        # Check that products have expected structure
        primeiro_produto = produtos[0]
        assert isinstance(primeiro_produto, Produto)
        assert primeiro_produto.titulo != "N/A", "Product should have a title"
        assert primeiro_produto.url != "N/A", "Product should have a URL"
        assert primeiro_produto.preco != "N/A", "Product should have a price"

    def test_scrape_multiple_pages(self, ml_scraper, results):
        """Test scraping multiple pages of results."""
        produtos = ml_scraper.scrape(
            termo_busca="notebook",
            max_pages=2,
        )
        
        # Store results for validation
        results.store("test_scrape_multiple_pages", {
            "produtos": produtos,
            "count": len(produtos),
            "search_term": "notebook",
            "pages": 2,
        })
        
        # Should return products from multiple pages
        assert len(produtos) > 20, "Should find products from multiple pages"
        
        # Check for URL uniqueness (deduplication)
        urls = [p.url for p in produtos if p.url != "N/A"]
        assert len(urls) == len(set(urls)), "All product URLs should be unique"

    def test_scrape_with_special_characters(self, ml_scraper, results):
        """Test scraping with search terms containing special characters."""
        produtos = ml_scraper.scrape(
            termo_busca="smart tv 50\"",
            max_pages=1,
        )
        
        results.store("test_scrape_with_special_characters", {
            "produtos": produtos,
            "count": len(produtos),
        })
        
        assert len(produtos) > 0, "Should handle special characters in search"

    def test_scrape_with_spaces(self, ml_scraper, results):
        """Test scraping with search terms containing spaces."""
        produtos = ml_scraper.scrape(
            termo_busca="fone de ouvido bluetooth",
            max_pages=1,
        )
        
        results.store("test_scrape_with_spaces", {
            "produtos": produtos,
            "count": len(produtos),
        })
        
        assert len(produtos) > 0, "Should handle spaces in search terms"

    def test_product_fields_populated(self, ml_scraper, results):
        """Test that scraped products have their fields properly populated."""
        produtos = ml_scraper.scrape(
            termo_busca="mouse gamer",
            max_pages=1,
        )
        
        # Check that at least some products have various fields populated
        has_moeda = any(p.moeda != "N/A" for p in produtos)
        has_url = any(p.url != "N/A" for p in produtos)
        has_titulo = any(p.titulo != "N/A" for p in produtos)
        
        results.store("test_product_fields_populated", {
            "produtos": produtos,
            "count": len(produtos),
            "has_moeda": has_moeda,
            "has_url": has_url,
            "has_titulo": has_titulo,
        })
        
        assert len(produtos) > 0
        assert has_moeda, "At least some products should have currency"
        assert has_url, "At least some products should have URLs"
        assert has_titulo, "At least some products should have titles"


class TestPageHelpers:
    """Integration tests for page helper functions using real browser."""

    def test_abrir_pagina_busca(self, browser_page):
        """Test opening a search page."""
        url_final = abrir_pagina_busca(browser_page, "notebook")
        
        assert "mercadolivre.com.br" in url_final
        assert "notebook" in url_final.lower()

    def test_abrir_pagina_busca_formats_term(self, browser_page):
        """Test that search term is properly formatted in URL."""
        url_final = abrir_pagina_busca(browser_page, "Smart TV 4K")
        
        # Should convert to lowercase and replace spaces with hyphens
        assert "smart-tv-4k" in url_final.lower()

    def test_obter_cards(self, browser_page, results):
        """Test obtaining product cards from a page."""
        abrir_pagina_busca(browser_page, "teclado")
        cards = obter_cards(browser_page)
        
        results.store("test_obter_cards", {
            "cards_count": len(cards),
            "search_term": "teclado",
        })
        
        assert len(cards) > 0, "Should find product cards on the page"
        # Mercado Livre typically shows 48-50 items per page
        assert len(cards) >= 30, "Should find reasonable number of cards"

    def test_esperar_carregar(self, browser_page):
        """Test waiting for page to load."""
        browser_page.goto("https://www.mercadolivre.com.br")
        
        # Should not raise any exceptions
        esperar_carregar(browser_page)
        
        # Page should be in a loaded state
        assert browser_page.url is not None

    def test_aceitar_cookies(self, browser_page):
        """Test accepting cookies banner."""
        browser_page.goto("https://www.mercadolivre.com.br")
        
        # Should not raise any exceptions even if banner doesn't exist
        aceitar_cookies(browser_page)

    def test_pagina_atual_num(self, browser_page):
        """Test getting current page number."""
        abrir_pagina_busca(browser_page, "smartphone")
        
        pagina = pagina_atual_num(browser_page)
        
        # First page should be 1 or None (if pagination not visible)
        assert pagina is None or pagina == 1

    def test_tem_proxima_pagina(self, browser_page):
        """Test checking if next page exists."""
        abrir_pagina_busca(browser_page, "celular")
        
        has_next = tem_proxima_pagina(browser_page)
        
        # First page should typically have a next page
        assert isinstance(has_next, bool)

    def test_ir_para_proxima_pagina(self, browser_page):
        """Test navigating to next page."""
        abrir_pagina_busca(browser_page, "tablet")
        
        url_inicial = browser_page.url
        
        if tem_proxima_pagina(browser_page):
            sucesso = ir_para_proxima_pagina(browser_page)
            
            if sucesso:
                url_final = browser_page.url
                assert url_final != url_inicial, "URL should change after navigation"
                
                # Page number should increase
                pagina = pagina_atual_num(browser_page)
                if pagina is not None:
                    assert pagina > 1, "Page number should be greater than 1"


class TestPaginationFlow:
    """Integration tests for pagination workflow."""

    def test_pagination_workflow(self, ml_scraper, results):
        """Test complete pagination workflow across multiple pages."""
        import asyncio
        
        # Skip if running inside asyncio loop (pytest-asyncio conflict)
        try:
            asyncio.get_running_loop()
            pytest.skip("Skipping due to asyncio loop conflict with sync Playwright")
        except RuntimeError:
            pass
        
        produtos_pagina_1 = ml_scraper.scrape(
            termo_busca="headset",
            max_pages=1,
        )
        
        produtos_pagina_2 = ml_scraper.scrape(
            termo_busca="headset",
            max_pages=2,
        )
        
        results.store("test_pagination_workflow", {
            "produtos_pagina_1": produtos_pagina_1,
            "produtos_pagina_2": produtos_pagina_2,
            "count_page_1": len(produtos_pagina_1),
            "count_page_2": len(produtos_pagina_2),
        })
        
        # Second run should have more products than first
        assert len(produtos_pagina_2) > len(produtos_pagina_1), \
            "Scraping 2 pages should return more products than 1 page"

    def test_deduplication_across_pages(self, ml_scraper, results):
        """Test that products are deduplicated across pages."""
        produtos = ml_scraper.scrape(
            termo_busca="monitor",
            max_pages=2,
        )
        
        # Extract URLs
        urls = [p.url for p in produtos if p.url != "N/A"]
        unique_urls = set(urls)
        
        results.store("test_deduplication_across_pages", {
            "produtos": produtos,
            "total_urls": len(urls),
            "unique_urls": len(unique_urls),
            "duplicates": len(urls) - len(unique_urls),
        })
        
        # All URLs should be unique
        assert len(urls) == len(unique_urls), \
            "Product URLs should be unique (no duplicates)"


class TestEdgeCases:
    """Integration tests for edge cases and error handling."""

    def test_handles_no_results(self, ml_scraper):
        """Test handling when search returns no results."""
        # Use a very specific/unlikely search term
        produtos = ml_scraper.scrape(
            termo_busca="xyzabc123nonexistentproduct999",
            max_pages=1,
        )
        
        # Should return empty list or very few results
        assert isinstance(produtos, list)

    def test_handles_max_pages_greater_than_available(self, ml_scraper):
        """Test when requesting more pages than available."""
        # Use a very specific search that likely has few results
        produtos = ml_scraper.scrape(
            termo_busca="produto muito específico raro",
            max_pages=10,  # Request many pages
        )
        
        # Should stop when no more pages available
        assert isinstance(produtos, list)

    def test_handles_single_result_page(self, ml_scraper):
        """Test scraping when only one page of results exists."""
        produtos = ml_scraper.scrape(
            termo_busca="produto ultra específico único",
            max_pages=3,
        )
        
        # Should handle gracefully even if only 1 page exists
        assert isinstance(produtos, list)


class TestProductDataQuality:
    """Integration tests for data quality of scraped products."""

    def test_url_format(self, ml_scraper, results):
        """Test that product URLs have correct format."""
        produtos = ml_scraper.scrape(
            termo_busca="livro",
            max_pages=1,
        )
        
        invalid_urls = []
        for produto in produtos:
            if produto.url != "N/A":
                if not produto.url.startswith("http"):
                    invalid_urls.append(produto.url)
                elif "mercadolivre.com.br" not in produto.url and "mercadolibre.com" not in produto.url:
                    invalid_urls.append(produto.url)
        
        results.store("test_url_format", {
            "produtos": produtos,
            "invalid_urls": invalid_urls,
            "valid_count": len(produtos) - len(invalid_urls),
        })
        
        for produto in produtos:
            if produto.url != "N/A":
                assert produto.url.startswith("http"), \
                    f"URL should start with http: {produto.url}"
                assert "mercadolivre.com.br" in produto.url or "mercadolibre.com" in produto.url, \
                    f"URL should be from Mercado Livre: {produto.url}"

    def test_price_format(self, ml_scraper, results):
        """Test that prices have reasonable format."""
        produtos = ml_scraper.scrape(
            termo_busca="caneta",
            max_pages=1,
        )
        
        prices_with_digits = sum(
            1 for p in produtos 
            if p.preco != "N/A" and any(c.isdigit() for c in p.preco)
        )
        
        results.store("test_price_format", {
            "produtos": produtos,
            "prices_with_digits": prices_with_digits,
            "total_prices": sum(1 for p in produtos if p.preco != "N/A"),
        })
        
        for produto in produtos:
            if produto.preco != "N/A":
                # Price should contain digits
                assert any(c.isdigit() for c in produto.preco), \
                    f"Price should contain digits: {produto.preco}"

    def test_rating_range(self, ml_scraper, results):
        """Test that ratings are within valid range."""
        produtos = ml_scraper.scrape(
            termo_busca="caderno",
            max_pages=1,
        )
        
        ratings = [p.avaliacao for p in produtos if p.avaliacao is not None]
        
        results.store("test_rating_range", {
            "produtos": produtos,
            "ratings": ratings,
            "avg_rating": sum(ratings) / len(ratings) if ratings else None,
            "min_rating": min(ratings) if ratings else None,
            "max_rating": max(ratings) if ratings else None,
        })
        
        for produto in produtos:
            if produto.avaliacao is not None:
                assert 0 <= produto.avaliacao <= 5, \
                    f"Rating should be between 0 and 5: {produto.avaliacao}"

    def test_num_avaliacoes_positive(self, ml_scraper, results):
        """Test that number of reviews is positive."""
        produtos = ml_scraper.scrape(
            termo_busca="mochila",
            max_pages=1,
        )
        
        num_avaliacoes = [p.num_avaliacoes for p in produtos if p.num_avaliacoes is not None]
        
        results.store("test_num_avaliacoes_positive", {
            "produtos": produtos,
            "num_avaliacoes": num_avaliacoes,
            "total_reviews": sum(num_avaliacoes) if num_avaliacoes else 0,
            "avg_reviews": sum(num_avaliacoes) / len(num_avaliacoes) if num_avaliacoes else None,
        })
        
        for produto in produtos:
            if produto.num_avaliacoes is not None:
                assert produto.num_avaliacoes >= 0, \
                    f"Number of reviews should be non-negative: {produto.num_avaliacoes}"

    def test_num_vendidos_positive(self, ml_scraper, results):
        """Test that number of sold items is positive."""
        produtos = ml_scraper.scrape(
            termo_busca="mochila",
            max_pages=1,
        )
        
        num_vendidos = [p.num_vendidos for p in produtos if p.num_vendidos is not None]
        
        results.store("test_num_vendidos_positive", {
            "produtos": produtos,
            "num_vendidos": num_vendidos,
            "total_sold": sum(num_vendidos) if num_vendidos else 0,
            "avg_sold": sum(num_vendidos) / len(num_vendidos) if num_vendidos else None,
        })
        
        for produto in produtos:
            if produto.num_vendidos is not None:
                assert produto.num_vendidos >= 0, \
                    f"Number of sold items should be non-negative: {produto.num_vendidos}"

    def test_image_url_format(self, ml_scraper, results):
        """Test that image URLs have correct format."""
        produtos = ml_scraper.scrape(
            termo_busca="camiseta",
            max_pages=1,
        )
        
        valid_images = sum(
            1 for p in produtos 
            if p.imagem_url != "N/A" and p.imagem_url.startswith("http")
        )
        
        results.store("test_image_url_format", {
            "produtos": produtos,
            "valid_images": valid_images,
            "total_images": sum(1 for p in produtos if p.imagem_url != "N/A"),
        })
        
        for produto in produtos:
            if produto.imagem_url != "N/A":
                assert produto.imagem_url.startswith("http"), \
                    f"Image URL should start with http: {produto.imagem_url}"

