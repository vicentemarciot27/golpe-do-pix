"""Single Item Max Bid Calculator Page"""

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
    page_title=f"{constants.PAGE_TITLE} - Item Único",
    page_icon=constants.PAGE_ICON,
    layout=constants.LAYOUT,
    initial_sidebar_state=constants.SIDEBAR_STATE,
)

st.title("💰 Max Bid Calculator - Item Único")
st.markdown(
    "Calcule o lance máximo para um item individual de leilão da Receita Federal."
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

# Main content - Input parameters
st.header("📝 Parâmetros do Item")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Venda (Mercado Livre)")
    ml_price_avg = st.number_input(
        "Preço Médio ML (R$)",
        min_value=constants.MIN_PRICE,
        value=constants.DEFAULT_ML_PRICE,
        step=10.0,
        format="%.2f",
        help="Preço médio de venda no Mercado Livre",
    )

    ml_fee = (
        st.number_input(
            "Taxa ML (%)",
            min_value=constants.MIN_PERCENTAGE,
            max_value=constants.MAX_PERCENTAGE,
            value=constants.DEFAULT_ML_FEE * 100,
            step=0.1,
            format="%.2f",
            help="Taxa de comissionamento do Mercado Livre",
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
            help="Desconto de segurança para reembolsos e perdas",
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
            help="Margem de lucro líquido desejada (após CMV, despesas operacionais e impostos)",
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
    )

with col3:
    st.subheader("Produto")
    ncm = st.text_input(
        "Código NCM",
        value=constants.DEFAULT_NCM,
        help="Código NCM do produto (use 0 para valores default)",
    )

    qty_item = st.number_input(
        "Quantidade",
        min_value=constants.MIN_QTY,
        value=constants.DEFAULT_QTY,
        step=1,
        help="Quantidade de itens",
    )

    cost_risk_buffer = (
        st.number_input(
            "Buffer de Risco de Custo (%)",
            min_value=constants.MIN_PERCENTAGE,
            max_value=constants.MAX_PERCENTAGE,
            value=constants.DEFAULT_COST_RISK_BUFFER * 100,
            step=0.5,
            format="%.2f",
            help="Margem de segurança para custos imprevistos",
        )
        / 100
    )

# Show active configuration summary
st.markdown("---")
services.render_config_summary(
    sn_mode_enum, custom_sn_rate, custom_sn_deducao, ncm_mode_enum, custom_ncm_rates
)

# Calculate button
st.markdown("---")
if st.button("🎯 Calcular Lance Máximo", type="primary", use_container_width=True):
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

        # Create input
        input_data = MaxBidItemCalculationInput(
            ml_price_avg=ml_price_avg,
            sales_risk_buffer_rate=sales_risk_buffer,
            revenue_last_12months=revenue_last_12months,
            ml_fee=ml_fee,
            target_net_margin=target_net_margin,
            ncm=ncm,
            cost_risk_buffer_rate=cost_risk_buffer,
            qty_item=qty_item,
        )

        # Calculate
        result = max_bid_calc.calculate_max_bid_item(input_data)

        # Display results
        results.render_single_item_result(
            result,
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
