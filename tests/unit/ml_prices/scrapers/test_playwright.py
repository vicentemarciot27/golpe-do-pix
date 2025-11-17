#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for Mercado Livre Playwright scraper helper functions.
Tests individual functions in isolation without requiring browser automation.
"""

import os
import platform
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

ROOT_DIR = Path(__file__).resolve().parents[4]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.ml_prices.scrapers.playwright import (
    Produto,
    is_running_in_container,
    extrair_texto_safe,
    parse_card,
    MercadoLivreScraper,
)
from config.ml_prices.settings import MLPricesSettings


class TestProdutoDataclass:
    """Test the Produto dataclass structure."""

    def test_produto_default_values(self):
        """Test that Produto initializes with correct default values."""
        produto = Produto()
        
        assert produto.titulo == "N/A"
        assert produto.url == "N/A"
        assert produto.preco == "N/A"
        assert produto.moeda == "N/A"
        assert produto.parcelamento == "N/A"
        assert produto.frete == "N/A"
        assert produto.avaliacao is None
        assert produto.num_avaliacoes is None
        assert produto.num_vendidos is None
        assert produto.variacoes == "N/A"
        assert produto.imagem_url == "N/A"

    def test_produto_custom_values(self):
        """Test that Produto accepts custom values."""
        produto = Produto(
            titulo="Smartphone Xiaomi",
            url="https://produto.mercadolivre.com.br/MLB-123",
            preco="1.299",
            moeda="R$",
            parcelamento="12x R$ 108,25",
            frete="Frete grátis",
            avaliacao=4.5,
            num_avaliacoes=1234,
            num_vendidos=50,
            variacoes="3 cores",
            imagem_url="https://http2.mlstatic.com/D_NQ_NP_123.jpg"
        )
        
        assert produto.titulo == "Smartphone Xiaomi"
        assert produto.url == "https://produto.mercadolivre.com.br/MLB-123"
        assert produto.preco == "1.299"
        assert produto.moeda == "R$"
        assert produto.avaliacao == 4.5
        assert produto.num_avaliacoes == 1234
        assert produto.num_vendidos == 50


class TestIsRunningInContainer:
    """Test container detection logic."""

    def test_detects_dockerenv_file(self):
        """Test detection when /.dockerenv exists."""
        with patch("apps.ml_prices.scrapers.playwright.platform.system", return_value="Linux"):
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = True
                assert is_running_in_container() is True

    def test_detects_docker_in_cgroup(self):
        """Test detection via /proc/1/cgroup content."""
        with patch("apps.ml_prices.scrapers.playwright.platform.system", return_value="Linux"):
            with patch("os.path.exists", return_value=False):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = (
                        "12:cpuset:/docker/abc123"
                    )
                    assert is_running_in_container() is True

    def test_detects_container_in_cgroup(self):
        """Test detection via /proc/1/cgroup with 'container' keyword."""
        with patch("apps.ml_prices.scrapers.playwright.platform.system", return_value="Linux"):
            with patch("os.path.exists", return_value=False):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = (
                        "12:cpuset:/container/abc123"
                    )
                    assert is_running_in_container() is True

    def test_not_in_container(self):
        """Test detection when not in container."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "12:cpuset:/user.slice"
                )
                assert is_running_in_container() is False

    def test_handles_exceptions_gracefully(self):
        """Test that exceptions return False."""
        with patch("os.path.exists", side_effect=Exception("Test error")):
            assert is_running_in_container() is False


class TestExtrairTextoSafe:
    """Test the safe text extraction function."""

    def test_extracts_text_successfully(self):
        """Test successful text extraction from element."""
        mock_element = Mock()
        mock_node = Mock()
        mock_node.inner_text.return_value = "  Test Text  "
        mock_element.query_selector.return_value = mock_node
        
        result = extrair_texto_safe(mock_element, "div.test")
        
        assert result == "Test Text"
        mock_element.query_selector.assert_called_once_with("div.test")

    def test_extracts_attribute_successfully(self):
        """Test successful attribute extraction from element."""
        mock_element = Mock()
        mock_node = Mock()
        mock_node.get_attribute.return_value = "https://example.com"
        mock_element.query_selector.return_value = mock_node
        
        result = extrair_texto_safe(mock_element, "a.link", attr="href")
        
        assert result == "https://example.com"
        mock_node.get_attribute.assert_called_once_with("href")

    def test_returns_none_when_node_not_found(self):
        """Test that None is returned when selector finds nothing."""
        mock_element = Mock()
        mock_element.query_selector.return_value = None
        
        result = extrair_texto_safe(mock_element, "div.nonexistent")
        
        assert result is None

    def test_returns_none_when_text_is_empty(self):
        """Test that None is returned when text is empty."""
        mock_element = Mock()
        mock_node = Mock()
        mock_node.inner_text.return_value = ""
        mock_element.query_selector.return_value = mock_node
        
        result = extrair_texto_safe(mock_element, "div.empty")
        
        assert result is None

    def test_handles_exceptions_gracefully(self):
        """Test that exceptions return None."""
        mock_element = Mock()
        mock_element.query_selector.side_effect = Exception("Test error")
        
        result = extrair_texto_safe(mock_element, "div.error")
        
        assert result is None


class TestParseCard:
    """Test the card parsing function."""

    def test_parses_complete_card(self):
        """Test parsing a card with all fields present."""
        mock_card = Mock()
        
        # Create mock nodes with proper return values
        title_node = Mock()
        title_node.inner_text.return_value = "Smartphone Xiaomi Redmi Note 12"
        title_node.get_attribute.return_value = "https://produto.mercadolivre.com.br/MLB-123"
        
        price_node = Mock()
        price_node.inner_text.return_value = "1.299"
        
        currency_node = Mock()
        currency_node.inner_text.return_value = "R$"
        
        installments_node = Mock()
        installments_node.inner_text.return_value = "12x R$ 108,25"
        
        shipping_node = Mock()
        shipping_node.inner_text.return_value = "Frete grátis"
        
        rating_node = Mock()
        rating_node.inner_text.return_value = "4,5"
        
        reviews_node = Mock()
        reviews_node.inner_text.return_value = "(1.234)"
        
        variations_node = Mock()
        variations_node.inner_text.return_value = "3 cores"
        
        image_node = Mock()
        image_node.get_attribute.return_value = "https://http2.mlstatic.com/D_NQ_NP_123.jpg"
        
        def mock_query_selector(selector):
            """Mock different selectors returning different nodes."""
            if "poly-component__title" in selector:
                return title_node
            elif "ui-search-item__title" in selector:
                return title_node
            elif "fraction" in selector:
                return price_node
            elif "currency" in selector:
                return currency_node
            elif "installments" in selector:
                return installments_node
            elif "shipping" in selector:
                return shipping_node
            elif "rating" in selector:
                return rating_node
            elif "total" in selector or "amount" in selector:
                return reviews_node
            elif "variations" in selector:
                return variations_node
            elif "picture" in selector or "image" in selector:
                return image_node
            else:
                return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.titulo == "Smartphone Xiaomi Redmi Note 12"
        assert produto.url == "https://produto.mercadolivre.com.br/MLB-123"
        assert produto.preco == "1.299"
        assert produto.moeda == "R$"
        assert produto.parcelamento == "12x R$ 108,25"
        assert produto.frete == "Frete grátis"
        assert produto.avaliacao == 4.5
        assert produto.num_avaliacoes == 1234
        assert produto.num_vendidos is None  # Not provided in this test
        assert produto.variacoes == "3 cores"
        assert produto.imagem_url == "https://http2.mlstatic.com/D_NQ_NP_123.jpg"

    def test_parses_card_with_missing_fields(self):
        """Test parsing a card with some fields missing."""
        mock_card = Mock()
        mock_card.query_selector.return_value = None
        
        produto = parse_card(mock_card)
        
        assert produto.titulo == "N/A"
        assert produto.url == "N/A"
        assert produto.preco == "N/A"
        assert produto.moeda == "N/A"
        assert produto.parcelamento == "N/A"
        assert produto.frete == "N/A"
        assert produto.avaliacao is None
        assert produto.num_avaliacoes is None
        assert produto.num_vendidos is None
        assert produto.variacoes == "N/A"
        assert produto.imagem_url == "N/A"

    def test_handles_invalid_rating_format(self):
        """Test that invalid rating format results in None."""
        mock_card = Mock()
        
        def mock_query_selector(selector):
            if "rating" in selector.lower():
                node = Mock()
                node.inner_text.return_value = "invalid"
                return node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.avaliacao is None

    def test_handles_invalid_num_avaliacoes_format(self):
        """Test that invalid num_avaliacoes format results in None."""
        mock_card = Mock()
        
        def mock_query_selector(selector):
            if "total" in selector.lower() or "amount" in selector.lower():
                node = Mock()
                node.inner_text.return_value = "invalid"
                return node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.num_avaliacoes is None

    def test_parses_rating_with_comma_decimal(self):
        """Test that rating with comma is converted to float."""
        mock_card = Mock()
        
        def mock_query_selector(selector):
            if "rating" in selector.lower():
                node = Mock()
                node.inner_text.return_value = "4,7"
                return node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.avaliacao == 4.7

    def test_parses_num_avaliacoes_with_formatting(self):
        """Test that num_avaliacoes handles parentheses and dots."""
        mock_card = Mock()
        
        def mock_query_selector(selector):
            if "total" in selector.lower() or "amount" in selector.lower():
                node = Mock()
                node.inner_text.return_value = "(12.345)"
                return node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.num_avaliacoes == 12345

    def test_parses_num_vendidos_from_review_container(self):
        """Test that num_vendidos is extracted from review container."""
        mock_card = Mock()
        
        review_container_node = Mock()
        review_container_node.inner_text.return_value = "5.0 | +5 vendidos"
        
        def mock_query_selector(selector):
            if "review-compacted" in selector:
                return review_container_node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.avaliacao == 5.0
        assert produto.num_vendidos == 5

    def test_parses_num_vendidos_without_plus_sign(self):
        """Test that num_vendidos works without plus sign."""
        mock_card = Mock()
        
        review_container_node = Mock()
        review_container_node.inner_text.return_value = "4.5 | 100 vendidos"
        
        def mock_query_selector(selector):
            if "review-compacted" in selector:
                return review_container_node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.avaliacao == 4.5
        assert produto.num_vendidos == 100

    def test_handles_missing_num_vendidos(self):
        """Test that missing num_vendidos results in None."""
        mock_card = Mock()
        
        review_container_node = Mock()
        review_container_node.inner_text.return_value = "5.0"
        
        def mock_query_selector(selector):
            if "review-compacted" in selector:
                return review_container_node
            return None
        
        mock_card.query_selector.side_effect = mock_query_selector
        
        produto = parse_card(mock_card)
        
        assert produto.avaliacao == 5.0
        assert produto.num_vendidos is None


class TestVirtualDisplayFunctions:
    """Test virtual display setup and cleanup functions."""

    @patch("apps.ml_prices.scrapers.playwright.is_running_in_container")
    @patch("apps.ml_prices.scrapers.playwright.logger")
    def test_setup_virtual_display_local_environment(self, mock_logger, mock_is_container):
        """Test that virtual display is not set up in local environment."""
        from apps.ml_prices.scrapers.playwright import setup_virtual_display
        
        mock_is_container.return_value = False
        
        setup_virtual_display()
        
        mock_logger.info.assert_called_with(
            "💻 Ambiente local detectado - usando display do sistema"
        )

    @patch("apps.ml_prices.scrapers.playwright.is_running_in_container")
    @patch("apps.ml_prices.scrapers.playwright.logger")
    def test_setup_virtual_display_container_environment(
        self, mock_logger, mock_is_container
    ):
        """Test that virtual display setup is attempted in container environment."""
        from apps.ml_prices.scrapers.playwright import setup_virtual_display
        
        mock_is_container.return_value = True
        
        # The function will try to import pyvirtualdisplay inside, which may fail
        # We just verify it logs the container detection message
        setup_virtual_display()
        
        # Verify that container environment was detected
        mock_logger.info.assert_any_call(
            "🐳 Ambiente container detectado - configurando display virtual Xvfb"
        )

    @patch("apps.ml_prices.scrapers.playwright._virtual_display")
    @patch("apps.ml_prices.scrapers.playwright.logger")
    def test_cleanup_virtual_display_when_display_exists(self, mock_logger, mock_display):
        """Test cleanup when virtual display exists."""
        from apps.ml_prices.scrapers.playwright import cleanup_virtual_display
        
        # Create a mock display that's truthy
        mock_display_instance = Mock()
        
        with patch("apps.ml_prices.scrapers.playwright._virtual_display", mock_display_instance):
            cleanup_virtual_display()
            
            mock_display_instance.stop.assert_called_once()

    def test_cleanup_virtual_display_when_no_display(self):
        """Test cleanup when no virtual display exists."""
        from apps.ml_prices.scrapers.playwright import cleanup_virtual_display
        
        with patch("apps.ml_prices.scrapers.playwright._virtual_display", None):
            # Should not raise any exceptions
            cleanup_virtual_display()


class TestMercadoLivreScraperClass:
    """Test the MercadoLivreScraper class with dependency injection."""
    
    def test_scraper_initialization(self):
        """Test that scraper can be initialized with settings."""
        settings = MLPricesSettings(
            pages_to_scrape=5,
            headless=True,
            page_load_timeout=30,
            explicit_wait=15,
        )
        
        scraper = MercadoLivreScraper(settings)
        
        assert scraper.settings.pages_to_scrape == 5
        assert scraper.settings.headless is True
        assert scraper.settings.page_load_timeout == 30
        assert scraper.settings.explicit_wait == 15
        assert scraper._virtual_display is None
    
    def test_scraper_with_different_settings(self):
        """Test that different scrapers can have different settings."""
        settings_prod = MLPricesSettings(
            pages_to_scrape=3,
            headless=True,
            page_load_timeout=40,
            explicit_wait=20,
        )
        
        settings_test = MLPricesSettings(
            pages_to_scrape=1,
            headless=True,
            page_load_timeout=10,
            explicit_wait=5,
        )
        
        scraper_prod = MercadoLivreScraper(settings_prod)
        scraper_test = MercadoLivreScraper(settings_test)
        
        assert scraper_prod.settings.pages_to_scrape == 3
        assert scraper_test.settings.pages_to_scrape == 1
        assert scraper_prod.settings.page_load_timeout == 40
        assert scraper_test.settings.page_load_timeout == 10
    
    def test_esperar_carregar_uses_settings(self):
        """Test that esperar_carregar uses settings timeout."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        
        settings = MLPricesSettings(explicit_wait=15)
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        # Use PlaywrightTimeoutError instead of generic Exception
        mock_page.wait_for_load_state.side_effect = PlaywrightTimeoutError("timeout")
        
        # Should not raise exception (it catches PlaywrightTimeoutError)
        scraper.esperar_carregar(mock_page)
        
        # Verify timeout was calculated from settings
        mock_page.wait_for_load_state.assert_called_once_with(
            "networkidle", timeout=15000  # 15 seconds * 1000
        )
    
    def test_aceitar_cookies_method(self):
        """Test that aceitar_cookies works as a method."""
        settings = MLPricesSettings()
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        mock_button = Mock()
        mock_page.query_selector.return_value = mock_button
        
        scraper.aceitar_cookies(mock_page)
        
        mock_button.click.assert_called_once()
    
    def test_abrir_pagina_busca_uses_settings(self):
        """Test that abrir_pagina_busca uses settings timeout."""
        settings = MLPricesSettings(page_load_timeout=25, explicit_wait=10)
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        mock_page.url = "https://lista.mercadolivre.com.br/smartphone"
        mock_page.wait_for_load_state.return_value = None
        
        scraper.abrir_pagina_busca(mock_page, "smartphone")
        
        # Verify timeout was calculated from settings
        mock_page.goto.assert_called_once()
        call_args = mock_page.goto.call_args
        assert call_args[1]["timeout"] == 25000  # 25 seconds * 1000
    
    def test_obter_cards_uses_settings(self):
        """Test that obter_cards uses settings timeout."""
        settings = MLPricesSettings(explicit_wait=12)
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        mock_cards = [Mock(), Mock(), Mock()]
        mock_page.query_selector_all.return_value = mock_cards
        
        cards = scraper.obter_cards(mock_page)
        
        assert len(cards) == 3
        # Verify timeout was calculated from settings
        mock_page.wait_for_selector.assert_called_once()
        call_args = mock_page.wait_for_selector.call_args
        assert call_args[1]["timeout"] == 12000  # 12 seconds * 1000
    
    def test_pagina_atual_num_method(self):
        """Test pagina_atual_num as a method."""
        settings = MLPricesSettings()
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        mock_page.evaluate.return_value = "2"
        
        pagina = scraper.pagina_atual_num(mock_page)
        
        assert pagina == 2
    
    def test_tem_proxima_pagina_method(self):
        """Test tem_proxima_pagina as a method."""
        settings = MLPricesSettings()
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        mock_page.evaluate.return_value = True
        
        has_next = scraper.tem_proxima_pagina(mock_page)
        
        assert has_next is True
    
    def test_ir_para_proxima_pagina_uses_settings(self):
        """Test that ir_para_proxima_pagina uses settings timeout."""
        settings = MLPricesSettings(explicit_wait=18)
        scraper = MercadoLivreScraper(settings)
        
        mock_page = Mock()
        mock_page.url = "https://lista.mercadolivre.com.br/smartphone"
        mock_page.evaluate.side_effect = [True, "2"]  # First call clicks, second gets page num
        
        with patch.object(scraper, 'esperar_carregar'):
            with patch.object(scraper, 'aceitar_cookies'):
                with patch.object(scraper, 'pagina_atual_num', side_effect=[1, 2]):
                    result = scraper.ir_para_proxima_pagina(mock_page)
        
        # Verify timeout was calculated from settings
        mock_page.wait_for_load_state.assert_called()
        call_args = mock_page.wait_for_load_state.call_args
        assert call_args[1]["timeout"] == 18000  # 18 seconds * 1000

