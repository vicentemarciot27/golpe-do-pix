#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scraper Mercado Livre usando Playwright.
Coleta TODOS os itens das N primeiras páginas (ou menos, se não houver).

Requisitos:
  - playwright instalado: pip install playwright
  - browsers instalados: playwright install chromium
  - (opcional) pyvirtualdisplay para rodar em container com Xvfb

Execute:
  python scraper_playwright.py
"""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

from playwright.sync_api import (
    sync_playwright,
    Page,
    ElementHandle,
    TimeoutError as PlaywrightTimeoutError,
)
from pyvirtualdisplay import Display

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.ml_prices.settings import settings

# =========================
# CONFIGURAÇÕES
# =========================
PAGES_TO_SCRAPE    = settings.pages_to_scrape
PAGE_LOAD_TIMEOUT  = settings.page_load_timeout
EXPLICIT_WAIT      = settings.explicit_wait
HEADLESS           = settings.headless

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ml_scraper_playwright")


# -------------------------
# Modelo de dados
# -------------------------
@dataclass
class Produto:
    titulo: str = "N/A"
    url: str = "N/A"
    preco: str = "N/A"
    moeda: str = "N/A"
    parcelamento: str = "N/A"
    frete: str = "N/A"
    avaliacao: float | None = None
    num_avaliacoes: int | None = None
    variacoes: str = "N/A"
    imagem_url: str = "N/A"


# -------------------------
# Detecção de container / display virtual
# -------------------------
def is_running_in_container() -> bool:
    """Detecta se está rodando dentro de um container Docker."""
    try:
        if os.path.exists("/.dockerenv"):
            return True

        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            return "docker" in content or "container" in content
    except Exception:
        return False


_virtual_display = None


def setup_virtual_display() -> None:
    """Configura display virtual se necessário (apenas para containers)."""
    global _virtual_display

    if not is_running_in_container():
        logger.info("💻 Ambiente local detectado - usando display do sistema")
        return

    logger.info("🐳 Ambiente container detectado - configurando display virtual Xvfb")

    display_var = os.environ.get("DISPLAY", ":99")
    logger.info(f"📺 DISPLAY configurado: {display_var}")

    try:

        _virtual_display = Display(visible=0, size=(1280, 1024))
        _virtual_display.start()
        logger.info(f"✅ pyvirtualdisplay iniciado: {_virtual_display.display}")
    except ImportError:
        logger.info("ℹ️ pyvirtualdisplay não disponível - assumindo Xvfb externo")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao iniciar pyvirtualdisplay: {e}")
        logger.info("ℹ️ Continuando com Xvfb do sistema (se disponível)")


def cleanup_virtual_display() -> None:
    """Desliga display virtual se foi criado."""
    global _virtual_display
    if _virtual_display:
        try:
            _virtual_display.stop()
            logger.info("🧹 Display virtual limpo")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar display virtual: {e}")
        finally:
            _virtual_display = None


# -------------------------
# Helpers de página
# -------------------------
def esperar_carregar(page: Page) -> None:
    """Espera a página terminar de carregar."""
    try:
        page.wait_for_load_state("networkidle", timeout=EXPLICIT_WAIT * 1000)
    except PlaywrightTimeoutError:
        logger.info("⏱️ Timeout em networkidle, seguindo mesmo assim.")


def aceitar_cookies(page: Page) -> None:
    candidates = [
        "button#onetrust-accept-btn-handler",
        "button.cookie-consent-banner-opt-out__action",
        "button:has-text('Aceitar')",
        "button:has-text('Permitir')",
    ]
    for sel in candidates:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                logger.info("Banner de cookies fechado.")
                return
        except Exception:
            continue


def abrir_pagina_busca(page: Page, termo: str) -> str:
    termo_formatado = termo.strip().replace(" ", "-").lower()
    url = f"https://lista.mercadolivre.com.br/{termo_formatado}"
    logger.info(f"Acessando: {url}")
    page.goto(url, wait_until="load", timeout=PAGE_LOAD_TIMEOUT * 1000)
    esperar_carregar(page)
    aceitar_cookies(page)
    logger.info(f"URL atual: {page.url}")
    return page.url


def obter_cards(page: Page) -> List[ElementHandle]:
    """Retorna lista de cards de produto na página."""
    sel_list_item = "li.ui-search-layout__item"
    alt_wrappers = [
        "div.ui-search-result__content-wrapper",
        "div.poly-card__content",
    ]

    # tenta primeiro o layout principal
    try:
        page.wait_for_selector(sel_list_item, timeout=EXPLICIT_WAIT * 1000)
        cards = page.query_selector_all(sel_list_item)
        if cards:
            return cards
    except PlaywrightTimeoutError:
        pass

    # fallbacks
    for css in alt_wrappers:
        try:
            page.wait_for_selector(css, timeout=EXPLICIT_WAIT * 1000)
            cards = page.query_selector_all(css)
            if cards:
                return cards
        except PlaywrightTimeoutError:
            continue

    return []


def extrair_texto_safe(
    el: ElementHandle,
    selector: str,
    attr: Optional[str] = None,
) -> Optional[str]:
    try:
        node = el.query_selector(selector)
        if not node:
            return None
        if attr:
            return node.get_attribute(attr)
        txt = node.inner_text()
        return txt.strip() if txt else None
    except Exception:
        return None


def parse_card(card: ElementHandle) -> Produto:
    p = Produto()

    p.titulo = (
        extrair_texto_safe(card, "h3.poly-component__title-wrapper a.poly-component__title")
        or extrair_texto_safe(card, "h2.ui-search-item__title")
        or extrair_texto_safe(card, "a.ui-search-link__title")
        or "N/A"
    )
    p.url = (
        extrair_texto_safe(card, "h3.poly-component__title-wrapper a.poly-component__title", "href")
        or extrair_texto_safe(card, "a.ui-search-link", "href")
        or "N/A"
    )

    p.preco = (
        extrair_texto_safe(card, "div.poly-price__current span.andes-money-amount__fraction")
        or extrair_texto_safe(card, "span.ui-search-price__part.ui-search-price__part--medium")
        or "N/A"
    )
    p.moeda = (
        extrair_texto_safe(card, "div.poly-price__current span.andes-money-amount__currency-symbol")
        or extrair_texto_safe(card, "span.andes-money-amount__currency-symbol")
        or "N/A"
    )

    p.parcelamento = (
        extrair_texto_safe(card, "span.poly-price__installments")
        or extrair_texto_safe(card, "span.ui-search-installments")
        or "N/A"
    )
    p.frete = (
        extrair_texto_safe(card, "div.poly-component__shipping")
        or extrair_texto_safe(card, "p.ui-search-item__shipping")
        or "N/A"
    )

    rating_txt = (
        extrair_texto_safe(card, "span.poly-reviews__rating")
        or extrair_texto_safe(card, "span.ui-search-reviews__rating-number")
    )
    try:
        p.avaliacao = float(rating_txt.replace(",", ".")) if rating_txt else None
    except Exception:
        p.avaliacao = None

    total_txt = (
        extrair_texto_safe(card, "span.poly-reviews__total")
        or extrair_texto_safe(card, "span.ui-search-reviews__amount")
    )
    try:
        if total_txt:
            p.num_avaliacoes = int(
                total_txt.replace("(", "").replace(")", "").replace(".", "").strip()
            )
        else:
            p.num_avaliacoes = None
    except Exception:
        p.num_avaliacoes = None

    p.variacoes = (
        extrair_texto_safe(card, "span.poly-component__variations-text")
        or "N/A"
    )
    p.imagem_url = (
        extrair_texto_safe(card, "img.poly-component__picture", "src")
        or extrair_texto_safe(card, "img.ui-search-result-image__element", "src")
        or "N/A"
    )

    return p


# -------------------------
# Paginação
# -------------------------
def pagina_atual_num(page: Page) -> Optional[int]:
    """Retorna o número da página atual lendo aria-current."""
    try:
        val = page.evaluate(
            """() => {
                const el = document.querySelector(
                    'li.andes-pagination__button--current a[aria-current="page"]'
                );
                return el ? el.textContent.trim() : null;
            }"""
        )
        return int(val) if val else None
    except Exception:
        return None


def tem_proxima_pagina(page: Page) -> bool:
    """True se existir botão 'Seguinte' habilitado."""
    try:
        return page.evaluate(
            """() => !!document.querySelector(
                'li.andes-pagination__button--next:not(.andes-pagination__button--disabled) a.andes-pagination__link'
            )"""
        )
    except Exception:
        return False


def ir_para_proxima_pagina(page: Page) -> bool:
    """Clica em 'Seguinte' e espera a troca de página."""
    old_url = page.url
    old_page = pagina_atual_num(page) or 0

    for _ in range(3):  # pequenas tentativas contra race condition de DOM
        ok = page.evaluate(
            """() => {
                const sel = 'li.andes-pagination__button--next:not(.andes-pagination__button--disabled) a.andes-pagination__link';
                const a = document.querySelector(sel);
                if (!a) return false;
                a.scrollIntoView({block: 'center'});
                a.click();
                return true;
            }"""
        )
        if not ok:
            return False

        try:
            page.wait_for_load_state("load", timeout=EXPLICIT_WAIT * 1000)
        except PlaywrightTimeoutError:
            pass

        # Pequeno delay adicional
        page.wait_for_timeout(500)

        new_page = pagina_atual_num(page) or 0
        if page.url != old_url or new_page > old_page:
            esperar_carregar(page)
            aceitar_cookies(page)
            return True

    return False


# -------------------------
# Scraper principal
# -------------------------
def scrape_mercadolivre(
    termo_busca: str,
    max_pages: int = 3,
    *,
    headless: bool = False,
) -> List[Produto]:
    logger.info(f"Iniciando scraping via Playwright para: {termo_busca!r}")

    produtos: List[Produto] = []
    vistos: Set[str] = set()  # deduplicação por URL

    setup_virtual_display()

    try:
        with sync_playwright() as p:
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,1024",
                "--disable-blink-features=AutomationControlled",
            ]
            if is_running_in_container():
                launch_args.extend([
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-renderer-backgrounding",
                    "--disable-features=VizDisplayCompositor",
                ])

            browser = p.chromium.launch(headless=headless, args=launch_args)
            context = browser.new_context(
                viewport={"width": 1280, "height": 1024},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            abrir_pagina_busca(page, termo_busca)

            pagina_atual = 1
            while pagina_atual <= max_pages:
                # scroll leve para garantir lazy-load
                page.evaluate("window.scrollTo(0, 800);")
                page.wait_for_timeout(800)
                page.evaluate("window.scrollTo(0, 1600);")
                page.wait_for_timeout(800)

                cards = obter_cards(page)
                logger.info(f"[Página {pagina_atual}] Encontrados {len(cards)} cards.")

                coletados = 0
                for card in cards:
                    try:
                        produto = parse_card(card)
                        if produto.url and produto.url != "N/A":
                            if produto.url in vistos:
                                continue
                            vistos.add(produto.url)
                        produtos.append(produto)
                        coletados += 1
                    except Exception as e:
                        logger.warning(
                            f"Falha ao processar card na página {pagina_atual}: {e}"
                        )

                logger.info(f"[Página {pagina_atual}] Coletados {coletados} itens.")

                if pagina_atual >= max_pages:
                    break
                if not tem_proxima_pagina(page):
                    logger.info("Não há mais páginas. Encerrando.")
                    break
                if not ir_para_proxima_pagina(page):
                    logger.info("Falha ao avançar para a próxima página. Encerrando.")
                    break

                pagina_atual += 1

            browser.close()
            return produtos

    except Exception as e:
        logger.error(f"Erro durante o scraping: {e}", exc_info=True)
        return []
    finally:
        cleanup_virtual_display()


# -------------------------
# Main
# -------------------------
def main(search_term: str = "smartphone xiaomi"):
    """Main entry point for direct execution.
    
    Args:
        search_term: Search term to scrape (defaults to example value).
    """
    produtos = scrape_mercadolivre(
        search_term,
        PAGES_TO_SCRAPE,
        headless=HEADLESS,
    )
    logger.info(f"{len(produtos)} produtos coletados.")
    return produtos


if __name__ == "__main__":
    main()
