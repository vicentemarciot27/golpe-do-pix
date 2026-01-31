"""Lot Max Bid Calculator Page - Multiple Items"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.max_bid.services.max_bid_calculator import MaxBidCalculator
from apps.max_bid.ui import constants, results, services
from shared.domain.auction.value_objects import MaxBidItemCalculationInput

# Page config
st.set_page_config(
    page_title=f"{constants.PAGE_TITLE} - Lote",
    page_icon=constants.PAGE_ICON,
    layout=constants.LAYOUT,
    initial_sidebar_state=constants.SIDEBAR_STATE,
)

st.title("💰 Max Bid Calculator - Lote")
st.markdown(
    "Calcule o lance máximo para um lote com múltiplos itens de leilão da Receita Federal."
)

# Initialize storages
services.initialize_storages()

# Sidebar - Configuration
st.sidebar.header("⚙️ Configurações")

# Simples Nacional and NCM configuration
sn_mode_enum, custom_sn_rate, custom_sn_deducao = (
    services.render_simples_nacional_config()
)
ncm_mode_enum, custom_ncm_rates = services.render_ncm_config()

# Main content - Common parameters
st.header("📝 Parâmetros Comuns")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Venda (Mercado Livre)")
    ml_fee = (
        st.number_input(
            "Taxa ML (%)",
            min_value=constants.MIN_PERCENTAGE,
            max_value=constants.MAX_PERCENTAGE,
            value=constants.DEFAULT_ML_FEE * 100,
            step=0.1,
            format="%.2f",
            help="Taxa de comissionamento do Mercado Livre (aplicada a todos os itens)",
            key="lot_ml_fee",
        )
        / 100
    )

    sales_risk_buffer = (
        st.number_input(
            "Buffer de Risco de Venda (%)",
            min_value=constants.MIN_PERCENTAGE,
            max_value=constants.MAX_PERCENTAGE,
            value=constants.DEFAULT_SALES_RISK_BUFFER * 100,
            step=1.0,
            format="%.2f",
            help="Desconto de segurança para reembolsos e perdas (aplicado a todos os itens)",
            key="lot_sales_buffer",
        )
        / 100
    )

    cost_risk_buffer = (
        st.number_input(
            "Buffer de Risco de Custo (%)",
            min_value=constants.MIN_PERCENTAGE,
            max_value=constants.MAX_PERCENTAGE,
            value=constants.DEFAULT_COST_RISK_BUFFER * 100,
            step=0.5,
            format="%.2f",
            help="Margem de segurança para custos imprevistos (aplicado a todos os itens)",
            key="lot_cost_buffer",
        )
        / 100
    )

with col2:
    st.subheader("Margem e Receita")
    target_net_margin = (
        st.number_input(
            "Margem Líquida Desejada (%)",
            min_value=constants.MIN_PERCENTAGE,
            max_value=constants.MAX_PERCENTAGE,
            value=constants.DEFAULT_TARGET_NET_MARGIN * 100,
            step=1.0,
            format="%.2f",
            help="Margem de lucro líquido desejada (após CMV, despesas operacionais e impostos) - aplicada a todos os itens",
            key="lot_target_net_margin",
        )
        / 100
    )

    revenue_last_12months = st.number_input(
        "Receita 12 meses (R$)",
        min_value=constants.MIN_PRICE,
        value=constants.DEFAULT_REVENUE_12M,
        step=1000.0,
        format="%.2f",
        help="Receita dos últimos 12 meses (para Simples Nacional variable)",
        key="lot_revenue_12m",
    )

# Items configuration
st.markdown("---")
st.header("📦 Itens do Lote")

# Initialize items in session state
if "lot_items" not in st.session_state:
    st.session_state.lot_items = [
        {
            "id": 1,
            "description": "Item 1",
            "ml_price_avg": constants.DEFAULT_ML_PRICE,
            "ncm": constants.DEFAULT_NCM,
            "qty": constants.DEFAULT_QTY,
        }
    ]

# Add/Remove item buttons
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    if st.button("➕ Adicionar Item", use_container_width=True):
        new_id = max(item["id"] for item in st.session_state.lot_items) + 1
        st.session_state.lot_items.append(
            {
                "id": new_id,
                "description": f"Item {new_id}",
                "ml_price_avg": constants.DEFAULT_ML_PRICE,
                "ncm": constants.DEFAULT_NCM,
                "qty": constants.DEFAULT_QTY,
            }
        )
        st.rerun()

with col2:
    if st.button(
        "➖ Remover Último",
        use_container_width=True,
        disabled=len(st.session_state.lot_items) <= 1,
    ):
        st.session_state.lot_items.pop()
        st.rerun()

# Display items table
st.markdown(f"**Total de itens diferentes no lote:** {len(st.session_state.lot_items)}")

# Items input form
for idx, item in enumerate(st.session_state.lot_items):
    with st.expander(f"📦 {item['description']}", expanded=idx < 3):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            item["description"] = st.text_input(
                "Descrição", value=item["description"], key=f"desc_{item['id']}"
            )

        with col2:
            item["ml_price_avg"] = st.number_input(
                "Preço Médio ML (R$)",
                min_value=constants.MIN_PRICE,
                value=float(item["ml_price_avg"]),
                step=10.0,
                format="%.2f",
                help="Preço médio de venda no Mercado Livre",
                key=f"price_{item['id']}",
            )

        with col3:
            item["ncm"] = st.text_input(
                "Código NCM",
                value=item["ncm"],
                help="Código NCM do produto (use 0 para valores default)",
                key=f"ncm_{item['id']}",
            )

        with col4:
            item["qty"] = st.number_input(
                "Quantidade",
                min_value=constants.MIN_QTY,
                value=int(item["qty"]),
                step=1,
                help="Quantidade de itens",
                key=f"qty_{item['id']}",
            )

# Show active configuration summary
st.markdown("---")
services.render_config_summary(
    sn_mode_enum, custom_sn_rate, custom_sn_deducao, ncm_mode_enum, custom_ncm_rates
)

# Calculate button
st.markdown("---")
if st.button(
    "🎯 Calcular Lance Máximo do Lote", type="primary", use_container_width=True
):
    try:
        # Create calculators
        sn_calculator, ncm_calculator = services.create_calculators(
            sn_mode_enum,
            custom_sn_rate,
            custom_sn_deducao,
            ncm_mode_enum,
            custom_ncm_rates,
        )

        # Create max bid calculator
        max_bid_calc = MaxBidCalculator(sn_calculator, ncm_calculator)

        # Calculate for each item
        lot_results = []
        for item in st.session_state.lot_items:
            input_data = MaxBidItemCalculationInput(
                ml_price_avg=item["ml_price_avg"],
                sales_risk_buffer_rate=sales_risk_buffer,
                revenue_last_12months=revenue_last_12months,
                ml_fee=ml_fee,
                target_net_margin=target_net_margin,
                ncm=item["ncm"],
                cost_risk_buffer_rate=cost_risk_buffer,
                qty_item=item["qty"],
            )

            result = max_bid_calc.calculate_max_bid_item(input_data)
            lot_results.append(
                {"description": item["description"], "result": result, "item": item}
            )

        # Calculate totals
        totals = results.calculate_lot_totals(lot_results, ml_fee)

        # Display results - Summary metrics
        results.render_lot_summary_metrics(totals, len(lot_results))

        # Items breakdown table
        results.render_lot_items_table(lot_results, ml_fee)

        # Detailed analysis tabs
        st.markdown("---")
        st.subheader("📊 Análise Detalhada")

        tab1, tab2 = st.tabs(["💼 Resumo Financeiro (DRE)", "📦 Detalhes por Item"])

        with tab1:
            results.render_lot_financial_summary(totals)

        with tab2:
            results.render_lot_items_details(
                lot_results,
                ml_fee,
                target_net_margin,
                revenue_last_12months,
                sn_mode_enum,
                cost_risk_buffer,
            )

    except Exception as e:
        st.error(f"❌ Erro no cálculo: {str(e)}")
        st.exception(e)

# Footer
services.render_footer()
