"""ML Prices - Product Classification and Price Analysis Page"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.max_bid.ui import constants
from apps.ml_prices.services import (
    BaseProductClassifier,
    SearchKeyGenerator,
    SearchResultAnalyser,
)
from apps.ml_prices.scrapers.playwright import MercadoLivreScraper, Produto
from config.ml_prices.settings import MLPricesSettings
from shared.adapters.outbound.ollama_client import OllamaClient, OllamaConfig
from shared.adapters.outbound.postgres_base_product_storage import (
    PostgresBaseProductStorage,
)
from shared.adapters.outbound.postgres_ecommerce_storage import PostgresEcommerceStorage
from shared.domain.base_product.entities import BaseProduct
from shared.domain.ecommerce.entities.product import Product, Currency
from datetime import datetime
import uuid

# Page config
st.set_page_config(
    page_title=f"{constants.PAGE_TITLE} - ML Prices",
    page_icon="🔍",
    layout=constants.LAYOUT,
    initial_sidebar_state=constants.SIDEBAR_STATE,
)

st.title("🔍 ML Prices - Análise de Preços")
st.markdown(
    "Classifique produtos, gere chaves de busca e analise resultados do Mercado Livre."
)


def format_currency(value: float) -> str:
    """Format value as Brazilian currency."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date(dt) -> str:
    """Format datetime for display."""
    if dt:
        return dt.strftime("%d/%m/%Y %H:%M")
    return "-"


# Initialize session state
if "ollama_client" not in st.session_state:
    st.session_state.ollama_client = None

if "base_product_storage" not in st.session_state:
    st.session_state.base_product_storage = None

if "product_storage" not in st.session_state:
    st.session_state.product_storage = None

if "current_base_product" not in st.session_state:
    st.session_state.current_base_product = None

if "search_key_result" not in st.session_state:
    st.session_state.search_key_result = None

if "scraped_products" not in st.session_state:
    st.session_state.scraped_products = []

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None


# Sidebar - Ollama Configuration
st.sidebar.header("⚙️ Configurações Ollama")

ollama_url = st.sidebar.text_input(
    "URL do Ollama",
    value="http://localhost:11434",
    help="URL base do servidor Ollama",
)

ollama_model = st.sidebar.text_input(
    "Modelo",
    value="qwen3:4b",
    help="Nome do modelo Ollama a ser usado",
)

ollama_timeout = st.sidebar.number_input(
    "Timeout (segundos)",
    min_value=30,
    max_value=600,
    value=120,
    help="Tempo limite para requisições",
)

st.sidebar.markdown("---")
st.sidebar.header("🌐 Configurações do Scraper")

scraper_pages = st.sidebar.number_input(
    "Páginas a buscar",
    min_value=1,
    max_value=10,
    value=2,
    help="Número de páginas do ML a buscar",
)

scraper_headless = st.sidebar.checkbox(
    "Modo headless",
    value=True,
    help="Executar navegador em modo oculto",
)


def get_ollama_client() -> OllamaClient:
    """Get or create Ollama client."""
    config = OllamaConfig(
        base_url=ollama_url,
        model=ollama_model,
        timeout=float(ollama_timeout),
    )
    return OllamaClient(config)


def get_base_storage() -> PostgresBaseProductStorage:
    """Get or create base product storage."""
    if st.session_state.base_product_storage is None:
        st.session_state.base_product_storage = PostgresBaseProductStorage()
    return st.session_state.base_product_storage


def get_product_storage() -> PostgresEcommerceStorage:
    """Get or create product storage."""
    if st.session_state.product_storage is None:
        st.session_state.product_storage = PostgresEcommerceStorage()
    return st.session_state.product_storage


def get_scraper() -> MercadoLivreScraper:
    """Create scraper with current settings."""
    settings = MLPricesSettings(
        pages_to_scrape=scraper_pages,
        headless=scraper_headless,
    )
    return MercadoLivreScraper(settings)


def produto_to_product(produto: Produto, search_key: str, base_product_id: int | None) -> Product:
    """Convert scraper Produto to domain Product."""
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


# Check Ollama connection
st.sidebar.markdown("---")
if st.sidebar.button("🔗 Testar Conexão Ollama"):
    try:
        client = get_ollama_client()
        models = client.list_models()
        client.close()
        if models:
            st.sidebar.success(f"✅ Conectado! Modelos: {len(models)}")
            with st.sidebar.expander("Modelos disponíveis"):
                for m in models:
                    st.write(f"- {m}")
        else:
            st.sidebar.warning("⚠️ Nenhum modelo encontrado")
    except Exception as e:
        st.sidebar.error(f"❌ Erro: {e}")


# ============================================================
# SECTION 1: Product Classification
# ============================================================
st.header("1. 📦 Classificar Produto")
st.markdown(
    "Extraia informações estruturadas de uma descrição de produto (ex: item de leilão)."
)

col1, col2 = st.columns([3, 1])

with col1:
    product_description = st.text_area(
        "Descrição do Produto",
        placeholder="[DI 22/1234567-8] CELULAR SAMSUNG GALAXY S24 ULTRA 256GB PRETO",
        height=100,
        help="Cole a descrição do produto para classificação",
    )

with col2:
    st.write("")
    st.write("")
    classify_button = st.button(
        "🔍 Classificar",
        type="primary",
        use_container_width=True,
        disabled=not product_description,
    )

if classify_button and product_description:
    with st.spinner("Classificando produto..."):
        try:
            storage = get_base_storage()
            client = get_ollama_client()

            classifier = BaseProductClassifier(
                storage=storage, ollama_client=client
            )

            base_product, is_new = classifier.classify(product_description)
            st.session_state.current_base_product = base_product
            st.session_state.scraped_products = []
            st.session_state.analysis_result = None

            if is_new:
                st.success(f"✅ Novo produto criado (ID: {base_product.id})")
            else:
                st.info(f"📋 Produto existente encontrado (ID: {base_product.id})")

        except Exception as e:
            st.error(f"Erro na classificação: {e}")
            import traceback
            st.code(traceback.format_exc())

# Display current base product
if st.session_state.current_base_product:
    bp = st.session_state.current_base_product

    st.markdown("### Produto Classificado")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Nome", bp.name)
    with col2:
        st.metric("Marca", bp.brand or "-")
    with col3:
        st.metric("Modelo", bp.model or "-")
    with col4:
        st.metric("Cor", bp.color or "-")

    if bp.other:
        st.markdown("**Atributos Adicionais:**")
        cols = st.columns(min(len(bp.other), 4))
        for i, (key, value) in enumerate(bp.other.items()):
            with cols[i % len(cols)]:
                st.metric(key.title(), str(value))

    st.caption(f"ID: {bp.id} | Signature: {bp.to_search_signature()}")


# ============================================================
# SECTION 2: Search Key Generation
# ============================================================
st.markdown("---")
st.header("2. 🔑 Gerar Chave de Busca")
st.markdown("Gere chaves de busca otimizadas para o Mercado Livre.")

tab_from_product, tab_from_text = st.tabs(
    ["📦 Do Produto Classificado", "✏️ De Texto Livre"]
)

with tab_from_product:
    if st.session_state.current_base_product:
        bp = st.session_state.current_base_product
        # Build full product description
        product_parts = []
        if bp.brand:
            product_parts.append(bp.brand)
        product_parts.append(bp.name)
        if bp.model:
            product_parts.append(bp.model)
        if bp.color:
            product_parts.append(bp.color)
        if bp.other:
            for key in sorted(bp.other.keys()):
                if bp.other[key]:
                    product_parts.append(str(bp.other[key]))
        product_desc = " ".join(product_parts)
        st.info(f"Produto: **{product_desc}**")

        if st.button("🔑 Gerar Chave", key="gen_from_product"):
            with st.spinner("Gerando chave de busca..."):
                try:
                    client = get_ollama_client()
                    generator = SearchKeyGenerator(ollama_client=client)
                    result = generator.generate_from_base_product(bp)
                    st.session_state.search_key_result = result
                    generator.close()
                except Exception as e:
                    st.error(f"Erro: {e}")
    else:
        st.warning("👆 Classifique um produto primeiro.")

with tab_from_text:
    freetext = st.text_input(
        "Texto para gerar chave",
        placeholder="iPhone 15 Pro Max 256GB",
    )

    if st.button("🔑 Gerar Chave", key="gen_from_text", disabled=not freetext):
        with st.spinner("Gerando chave de busca..."):
            try:
                client = get_ollama_client()
                generator = SearchKeyGenerator(ollama_client=client)
                result = generator.generate_from_freetext(freetext)
                st.session_state.search_key_result = result
                generator.close()
            except Exception as e:
                st.error(f"Erro: {e}")

# Display search key result
if st.session_state.search_key_result:
    result = st.session_state.search_key_result

    st.markdown("### Resultado da Geração")

    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("**Chave Principal:**")
        st.code(result.primary_key, language=None)

        st.markdown(
            f'<a href="https://lista.mercadolivre.com.br/{result.primary_key.replace(" ", "-")}" '
            f'target="_blank">🔗 Buscar no ML</a>',
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**Raciocínio:**")
        st.write(result.reasoning)

        if result.alternatives:
            st.markdown("**Alternativas:**")
            for alt in result.alternatives:
                st.write(f"- `{alt}`")


# ============================================================
# SECTION 3: Scrape and Analyze
# ============================================================
st.markdown("---")
st.header("3. 📊 Buscar e Analisar Resultados")
st.markdown("Busque produtos no Mercado Livre e analise a relevância para comparação de preço.")

if st.session_state.current_base_product and st.session_state.search_key_result:
    bp = st.session_state.current_base_product
    search_key = st.session_state.search_key_result.primary_key

    # Custom search key input
    custom_key = st.text_input(
        "Chave de busca (editar se necessário)",
        value=search_key,
        key="custom_search_key"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔍 Buscar no Mercado Livre", type="primary", use_container_width=True):
            with st.spinner(f"Buscando '{custom_key}' no Mercado Livre..."):
                try:
                    scraper = get_scraper()
                    raw_products = scraper.scrape(custom_key, max_pages=scraper_pages)

                    products = [
                        produto_to_product(p, custom_key, bp.id)
                        for p in raw_products
                    ]

                    # Save to database
                    storage = get_product_storage()
                    for product in products:
                        existing = storage.get_product_by_url(product.url)
                        if existing:
                            storage.update_product(product)
                        else:
                            storage.create_product(product)

                    st.session_state.scraped_products = products
                    st.session_state.analysis_result = None
                    st.success(f"✅ Encontrados {len(products)} produtos")

                except RuntimeError as e:
                    if "Playwright" in str(e):
                        st.error("⚠️ Erro do Playwright no Windows")
                        st.warning(
                            "**Soluções:**\n\n"
                            "1. Reinicie o Streamlit (Ctrl+C e rode novamente)\n"
                            "2. Use WSL2 (Windows Subsystem for Linux)\n"
                            "3. Execute o scraper em um script Python separado\n\n"
                            "Este erro ocorre porque o Playwright não funciona bem "
                            "no Windows quando executado dentro do Streamlit."
                        )
                    else:
                        st.error(f"Erro: {e}")
                except Exception as e:
                    st.error(f"Erro no scraping: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    with col2:
        if st.session_state.scraped_products:
            if st.button("📊 Analisar Relevância", type="secondary", use_container_width=True):
                with st.spinner("Analisando produtos..."):
                    try:
                        client = get_ollama_client()
                        analyser = SearchResultAnalyser(ollama_client=client)

                        result = analyser.analyse_batch(
                            bp,
                            st.session_state.scraped_products,
                            custom_key
                        )
                        st.session_state.analysis_result = result

                        # Update relevance in database
                        storage = get_product_storage()
                        for ap in result.relevant_products:
                            if hasattr(storage, 'update_relevance'):
                                storage.update_relevance(ap.product.id, True)
                        for ap in result.irrelevant_products:
                            if hasattr(storage, 'update_relevance'):
                                storage.update_relevance(ap.product.id, False)

                        analyser.close()
                    except Exception as e:
                        st.error(f"Erro: {e}")
                        import traceback
                        st.code(traceback.format_exc())

    # Display scraped products
    if st.session_state.scraped_products:
        products = st.session_state.scraped_products

        st.markdown(f"### Produtos Encontrados ({len(products)})")

        products_data = []
        for p in products:
            products_data.append({
                "Título": p.title[:60] + "..." if len(p.title) > 60 else p.title,
                "Preço": format_currency(p.price),
                "Frete Grátis": "✅" if p.is_free_shipping else "❌",
                "Avaliação": f"⭐ {p.rating}" if p.rating else "-",
                "Vendidos": p.sold_amount or "-",
            })

        st.dataframe(products_data, use_container_width=True, hide_index=True)

    # Display analysis result
    if st.session_state.analysis_result:
        result = st.session_state.analysis_result

        st.markdown("### Resultado da Análise")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Produtos Relevantes", len(result.relevant_products))
        with col2:
            st.metric("Produtos Irrelevantes", len(result.irrelevant_products))
        with col3:
            client = get_ollama_client()
            analyser = SearchResultAnalyser(ollama_client=client)
            stats = analyser.get_price_statistics(result.relevant_products)
            analyser.close()
            if stats["avg"]:
                st.metric("Preço Médio (Relevantes)", format_currency(stats["avg"]))
            else:
                st.metric("Preço Médio", "-")

        st.markdown(f"**Resumo:** {result.summary}")

        if result.suggested_new_key:
            st.warning(f"💡 **Sugestão de nova chave:** `{result.suggested_new_key}`")

        # Relevant products
        if result.relevant_products:
            with st.expander("✅ Produtos Relevantes", expanded=True):
                for ap in result.relevant_products:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        title = ap.product.title[:50] + "..." if len(ap.product.title) > 50 else ap.product.title
                        st.markdown(f"[{title}]({ap.product.url})")
                    with col2:
                        st.write(format_currency(ap.product.price))
                    with col3:
                        st.write(f"Confiança: {ap.confidence:.0%}")

        # Irrelevant products
        if result.irrelevant_products:
            with st.expander("❌ Produtos Irrelevantes"):
                for ap in result.irrelevant_products:
                    col1, col2 = st.columns([3, 2])
                    with col1:
                        title = ap.product.title[:50] + "..." if len(ap.product.title) > 50 else ap.product.title
                        st.write(f"~~{title}~~")
                    with col2:
                        st.write(format_currency(ap.product.price))

        # Price statistics
        if stats["count"] > 0:
            st.markdown("### Estatísticas de Preço (Relevantes)")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Mínimo", format_currency(stats["min"]))
            with col2:
                st.metric("Máximo", format_currency(stats["max"]))
            with col3:
                st.metric("Média", format_currency(stats["avg"]))
            with col4:
                st.metric("Mediana", format_currency(stats["median"]))

else:
    st.info("👆 Classifique um produto e gere uma chave de busca primeiro.")


# ============================================================
# SECTION 4: Saved Base Products
# ============================================================
st.markdown("---")
st.header("4. 📂 Produtos Base Salvos")

try:
    storage = get_base_storage()

    # Search form
    with st.expander("🔍 Buscar Produtos", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            search_name = st.text_input("Nome", placeholder="Smartphone")
        with col2:
            search_brand = st.text_input("Marca", placeholder="Samsung")
        with col3:
            search_model = st.text_input("Modelo", placeholder="Galaxy")

        if st.button("🔍 Buscar"):
            results = storage.search(
                name=search_name or None,
                brand=search_brand or None,
                model=search_model or None,
                limit=20,
            )

            if results:
                st.success(f"Encontrados {len(results)} produtos")

                table_data = []
                for bp in results:
                    table_data.append({
                        "ID": bp.id,
                        "Nome": bp.name,
                        "Marca": bp.brand or "-",
                        "Modelo": bp.model or "-",
                        "Cor": bp.color or "-",
                        "Atributos": ", ".join(
                            f"{k}:{v}" for k, v in (bp.other or {}).items()
                        )[:30],
                        "Criado": format_date(bp.created_at),
                    })

                st.dataframe(table_data, use_container_width=True, hide_index=True)

                # Select to load
                selected_id = st.selectbox(
                    "Carregar produto",
                    options=[None] + [bp.id for bp in results],
                    format_func=lambda x: (
                        "-- Selecione --"
                        if x is None
                        else f"ID {x}: {next(bp.name for bp in results if bp.id == x)}"
                    ),
                )

                if selected_id and st.button("📥 Carregar"):
                    loaded = storage.get_by_id(selected_id)
                    if loaded:
                        st.session_state.current_base_product = loaded
                        st.session_state.scraped_products = []
                        st.session_state.analysis_result = None
                        st.session_state.search_key_result = None
                        st.success(f"Produto carregado: {loaded.brand} {loaded.model}")
                        st.rerun()
            else:
                st.info("Nenhum produto encontrado.")

    # Manual creation
    with st.expander("➕ Criar Produto Manualmente", expanded=False):
        with st.form("create_product"):
            col1, col2 = st.columns(2)

            with col1:
                new_name = st.text_input("Nome *", placeholder="Smartphone")
                new_brand = st.text_input("Marca", placeholder="Apple")
                new_model = st.text_input("Modelo", placeholder="iPhone 15 Pro")

            with col2:
                new_color = st.text_input("Cor", placeholder="Titanium")
                new_storage = st.text_input("Armazenamento", placeholder="256GB")
                new_ram = st.text_input("RAM", placeholder="8GB")

            if st.form_submit_button("💾 Criar Produto"):
                if new_name:
                    other = {}
                    if new_storage:
                        other["storage"] = new_storage
                    if new_ram:
                        other["ram"] = new_ram

                    new_bp = BaseProduct(
                        name=new_name,
                        brand=new_brand or None,
                        model=new_model or None,
                        color=new_color or None,
                        other=other,
                    )

                    created = storage.create(new_bp)
                    st.session_state.current_base_product = created
                    st.session_state.scraped_products = []
                    st.session_state.analysis_result = None
                    st.session_state.search_key_result = None
                    st.success(f"Produto criado com ID: {created.id}")
                    st.rerun()
                else:
                    st.error("Nome é obrigatório.")

except Exception as e:
    st.error(f"Erro ao acessar banco de dados: {e}")
    st.info("Verifique se o PostgreSQL está rodando e o schema foi aplicado.")


# Footer
st.markdown("---")
st.markdown(
    """
<div style='text-align: center; color: gray; font-size: 0.9em;'>
    <p>ML Prices - Powered by Ollama + qwen3</p>
    <p>Classifique produtos, gere chaves de busca otimizadas e analise preços do Mercado Livre</p>
</div>
""",
    unsafe_allow_html=True,
)
