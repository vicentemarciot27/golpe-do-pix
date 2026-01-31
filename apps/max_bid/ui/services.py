"""
Shared services and functions for Max Bid Calculator UI
"""

import streamlit as st

from apps.max_bid.services.ncm_calculator import NcmCalculatorFactory
from apps.max_bid.services.simples_nacional_calculator import (
    SimplesNacionalCalculatorFactory,
)
from apps.max_bid.ui.constants import NCM_MODE_LABELS, SIMPLES_NACIONAL_MODE_LABELS
from shared.adapters.outbound.local_auction_storage import (
    LocalNCMStorage,
    LocalRevenueStorage,
)
from shared.domain.auction.value_objects import (
    NcmMode,
    NcmTaxRates,
    SimplesNacionalMode,
    SimplesNacionalTax,
)


def initialize_storages():
    """Initialize storage adapters in session state"""
    if "ncm_storage" not in st.session_state:
        st.session_state.ncm_storage = LocalNCMStorage()

    if "revenue_storage" not in st.session_state:
        st.session_state.revenue_storage = LocalRevenueStorage()


def render_simples_nacional_config():
    """Render Simples Nacional configuration in sidebar"""
    st.sidebar.subheader("Simples Nacional")

    sn_mode = st.sidebar.selectbox(
        "Modo de Cálculo",
        options=[mode.value for mode in SimplesNacionalMode],
        format_func=lambda x: SIMPLES_NACIONAL_MODE_LABELS[x],
        key="sn_mode",
    )

    sn_mode_enum = SimplesNacionalMode(sn_mode)
    default_sn_tax = st.session_state.revenue_storage.get_fixed_simples_nacional_tax()

    # Display Fixed mode values
    if sn_mode_enum == SimplesNacionalMode.FIXED:
        st.sidebar.info(f"""
        📋 **Valores Fixed:**
        - Taxa: {default_sn_tax.rate * 100:.2f}%
        - Dedução: R$ {default_sn_tax.deducao:,.2f}
        """)

    # Custom Simples Nacional inputs
    custom_sn_rate = None
    custom_sn_deducao = None
    if sn_mode_enum == SimplesNacionalMode.CUSTOM_FIXED:
        st.sidebar.markdown("**Taxa Customizada:**")
        custom_sn_rate = (
            st.sidebar.number_input(
                "Taxa (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(default_sn_tax.rate * 100),
                step=0.1,
                format="%.2f",
                help=f"Valor padrão Fixed: {default_sn_tax.rate * 100:.2f}%",
            )
            / 100
        )
        custom_sn_deducao = st.sidebar.number_input(
            "Dedução (R$)",
            min_value=0.0,
            value=float(default_sn_tax.deducao),
            step=100.0,
            format="%.2f",
            help=f"Valor padrão Fixed: R$ {default_sn_tax.deducao:,.2f}",
        )

    return sn_mode_enum, custom_sn_rate, custom_sn_deducao


def render_ncm_config():
    """Render NCM configuration in sidebar"""
    st.sidebar.subheader("NCM (Impostos)")

    ncm_mode = st.sidebar.selectbox(
        "Modo de Cálculo",
        options=[mode.value for mode in NcmMode],
        format_func=lambda x: NCM_MODE_LABELS[x],
        key="ncm_mode",
    )

    ncm_mode_enum = NcmMode(ncm_mode)
    default_ncm_rates = st.session_state.ncm_storage.get_default_tax_rates()

    # Display Fixed mode values
    if ncm_mode_enum == NcmMode.FIXED:
        st.sidebar.info(f"""
        📋 **Valores Fixed:**
        - IPI: {default_ncm_rates.ipi * 100:.2f}%
        - II: {default_ncm_rates.ii * 100:.2f}%
        - ICMS: {default_ncm_rates.icms * 100:.2f}%
        - CBS: {default_ncm_rates.cbs * 100:.2f}%
        - IBS: {default_ncm_rates.ibs * 100:.2f}%
        """)

    # Custom NCM inputs
    custom_ncm_rates = None
    if ncm_mode_enum == NcmMode.CUSTOM_FIXED:
        st.sidebar.markdown("**Taxas Customizadas (%):**")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            custom_ipi = (
                st.number_input(
                    "IPI",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_ncm_rates.ipi * 100),
                    step=0.1,
                    help=f"Valor padrão Fixed: {default_ncm_rates.ipi * 100:.2f}%",
                )
                / 100
            )
            custom_ii = (
                st.number_input(
                    "II",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_ncm_rates.ii * 100),
                    step=0.1,
                    help=f"Valor padrão Fixed: {default_ncm_rates.ii * 100:.2f}%",
                )
                / 100
            )
            custom_icms = (
                st.number_input(
                    "ICMS",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_ncm_rates.icms * 100),
                    step=0.1,
                    help=f"Valor padrão Fixed: {default_ncm_rates.icms * 100:.2f}%",
                )
                / 100
            )
        with col2:
            custom_cbs = (
                st.number_input(
                    "CBS",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_ncm_rates.cbs * 100),
                    step=0.1,
                    help=f"Valor padrão Fixed: {default_ncm_rates.cbs * 100:.2f}%",
                )
                / 100
            )
            custom_ibs = (
                st.number_input(
                    "IBS",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_ncm_rates.ibs * 100),
                    step=0.1,
                    help=f"Valor padrão Fixed: {default_ncm_rates.ibs * 100:.2f}%",
                )
                / 100
            )

        custom_ncm_rates = NcmTaxRates(
            ipi=custom_ipi,
            ii=custom_ii,
            icms=custom_icms,
            cbs=custom_cbs,
            ibs=custom_ibs,
        )

    return ncm_mode_enum, custom_ncm_rates


def create_calculators(
    sn_mode_enum, custom_sn_rate, custom_sn_deducao, ncm_mode_enum, custom_ncm_rates
):
    """Create calculator instances based on selected modes"""
    sn_factory = SimplesNacionalCalculatorFactory(st.session_state.revenue_storage)

    # Create Simples Nacional calculator
    if sn_mode_enum == SimplesNacionalMode.CUSTOM_FIXED:
        custom_sn_tax = SimplesNacionalTax(
            rate=custom_sn_rate, deducao=custom_sn_deducao
        )
        sn_calculator = sn_factory.create(sn_mode_enum, custom_sn_tax)
    else:
        sn_calculator = sn_factory.create(sn_mode_enum)

    # Create NCM calculator
    ncm_factory = NcmCalculatorFactory(st.session_state.ncm_storage)
    if ncm_mode_enum == NcmMode.CUSTOM_FIXED:
        ncm_calculator = ncm_factory.create(ncm_mode_enum, custom_ncm_rates)
    else:
        ncm_calculator = ncm_factory.create(ncm_mode_enum)

    return sn_calculator, ncm_calculator


def render_config_summary(
    sn_mode_enum, custom_sn_rate, custom_sn_deducao, ncm_mode_enum, custom_ncm_rates
):
    """Render configuration summary in expander"""
    default_ncm_rates = st.session_state.ncm_storage.get_default_tax_rates()
    default_sn_tax = st.session_state.revenue_storage.get_fixed_simples_nacional_tax()

    with st.expander("🔍 Ver Configurações Ativas", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**💼 Simples Nacional**")
            st.write(f"**Modo:** {sn_mode_enum.value}")
            if sn_mode_enum == SimplesNacionalMode.FIXED:
                st.write(f"- Taxa: {default_sn_tax.rate * 100:.2f}%")
                st.write(f"- Dedução: R$ {default_sn_tax.deducao:,.2f}")
            elif sn_mode_enum == SimplesNacionalMode.CUSTOM_FIXED:
                st.write(f"- Taxa: {custom_sn_rate * 100:.2f}%")
                st.write(f"- Dedução: R$ {custom_sn_deducao:,.2f}")
            else:
                st.write("- Variável por faixa de receita")

        with col2:
            st.markdown("**🏛️ NCM (Impostos)**")
            st.write(f"**Modo:** {ncm_mode_enum.value}")
            if ncm_mode_enum == NcmMode.FIXED:
                st.write(
                    f"- IPI: {default_ncm_rates.ipi * 100:.1f}%, II: {default_ncm_rates.ii * 100:.1f}%, ICMS: {default_ncm_rates.icms * 100:.1f}%"
                )
                st.write(
                    f"- CBS: {default_ncm_rates.cbs * 100:.1f}%, IBS: {default_ncm_rates.ibs * 100:.1f}%"
                )
            elif ncm_mode_enum == NcmMode.CUSTOM_FIXED and custom_ncm_rates:
                st.write(
                    f"- IPI: {custom_ncm_rates.ipi * 100:.1f}%, II: {custom_ncm_rates.ii * 100:.1f}%, ICMS: {custom_ncm_rates.icms * 100:.1f}%"
                )
                st.write(
                    f"- CBS: {custom_ncm_rates.cbs * 100:.1f}%, IBS: {custom_ncm_rates.ibs * 100:.1f}%"
                )
            else:
                st.write("- Variável por código NCM")


def render_result_details(
    result,
    ml_fee,
    target_net_margin,
    revenue_last_12months,
    sn_mode_enum,
    cost_risk_buffer,
):
    """Render detailed calculation results in tabs"""
    tab1, tab2, tab3 = st.tabs(
        ["💼 Impostos NCM", "🏦 Simples Nacional", "📊 Breakdown Completo"]
    )

    with tab1:
        st.markdown("**Alíquotas NCM:**")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"- **IPI:** {result.ncm_tax_rates.ipi * 100:.2f}%")
            st.write(f"- **II:** {result.ncm_tax_rates.ii * 100:.2f}%")
            st.write(f"- **ICMS:** {result.ncm_tax_rates.icms * 100:.2f}%")
        with col2:
            st.write(f"- **CBS:** {result.ncm_tax_rates.cbs * 100:.2f}%")
            st.write(f"- **IBS:** {result.ncm_tax_rates.ibs * 100:.2f}%")

        st.markdown(f"**Total de Impostos NCM:** R$ {result.ncm_taxes_total:,.2f}")

        # Individual tax amounts
        ipi_amount = result.max_bid_item * result.ncm_tax_rates.ipi
        ii_amount = result.max_bid_item * result.ncm_tax_rates.ii
        icms_amount = result.max_bid_item * result.ncm_tax_rates.icms
        cbs_amount = result.max_bid_item * result.ncm_tax_rates.cbs
        ibs_amount = result.max_bid_item * result.ncm_tax_rates.ibs

        st.markdown("**Valores em Reais:**")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"- IPI: R$ {ipi_amount:,.2f}")
            st.write(f"- II: R$ {ii_amount:,.2f}")
            st.write(f"- ICMS: R$ {icms_amount:,.2f}")
        with col2:
            st.write(f"- CBS: R$ {cbs_amount:,.2f}")
            st.write(f"- IBS: R$ {ibs_amount:,.2f}")

    with tab2:
        st.markdown("**Simples Nacional:**")
        st.write(f"- **Taxa Nominal:** {result.simples_nacional_tax_rate * 100:.2f}%")
        st.write(f"- **Dedução:** R$ {result.simples_nacional_tax_deducao:,.2f}")
        st.write(
            f"- **Taxa Efetiva:** {result.simples_nacional_tax_effective_rate * 100:.2f}%"
        )
        st.write(
            f"- **Valor a Pagar:** R$ {result.expected_rev * result.simples_nacional_tax_effective_rate:,.2f}"
        )

        if sn_mode_enum == SimplesNacionalMode.VARIABLE:
            st.info(
                f"📊 Baseado em receita de 12 meses: R$ {revenue_last_12months:,.2f}"
            )
        elif sn_mode_enum == SimplesNacionalMode.FIXED:
            st.info("🔒 Usando valores padrão da primeira faixa do Simples Nacional")
        elif sn_mode_enum == SimplesNacionalMode.CUSTOM_FIXED:
            st.info("✏️ Usando valores personalizados definidos pelo usuário")

    with tab3:
        st.markdown("**Fórmula do Cálculo:**")
        st.code(
            f"""
Numerador = Expected Rev × (1 - Target Net Margin - Simples Nacional - ML Fee)
Numerador = {result.expected_rev:,.2f} × (1 - {target_net_margin:.3f} - {result.simples_nacional_tax_effective_rate:.3f} - {ml_fee:.3f})
Numerador = {result.numerator:,.2f}

Denominador = (1 + IPI + II + ICMS + CBS + IBS) × (1 + Cost Risk Buffer)
Denominador = (1 + {result.ncm_tax_rates.ipi:.3f} + {result.ncm_tax_rates.ii:.3f} + {result.ncm_tax_rates.icms:.3f} + {result.ncm_tax_rates.cbs:.3f} + {result.ncm_tax_rates.ibs:.3f}) × (1 + {cost_risk_buffer:.3f})
Denominador = {result.denominator:.4f}

Max Bid = Numerador / Denominador
Max Bid = {result.numerator:,.2f} / {result.denominator:.4f}
Max Bid = R$ {result.max_bid_item:,.2f}
        """,
            language="text",
        )

        st.markdown("**Resumo de Custos e Lucros:**")

        # Cálculos contábeis corretos
        cmv = result.max_bid_item + result.ncm_taxes_total
        lucro_bruto = result.expected_rev - cmv
        lucro_bruto_pct = (
            (lucro_bruto / result.expected_rev * 100) if result.expected_rev > 0 else 0
        )

        ml_fee_amount = result.expected_rev * ml_fee
        lucro_operacional = lucro_bruto - ml_fee_amount
        lucro_operacional_pct = (
            (lucro_operacional / result.expected_rev * 100)
            if result.expected_rev > 0
            else 0
        )

        sn_amount = result.expected_rev * result.simples_nacional_tax_effective_rate
        lucro_liquido = lucro_operacional - sn_amount
        lucro_liquido_pct = (
            (lucro_liquido / result.expected_rev * 100)
            if result.expected_rev > 0
            else 0
        )

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"- **Receita Esperada:** R$ {result.expected_rev:,.2f}")
            st.write(f"- **CMV** (Lance + Impostos NCM): R$ {cmv:,.2f}")
            st.write(
                f"- **= Lucro Bruto:** R$ {lucro_bruto:,.2f} ({lucro_bruto_pct:.1f}%)"
            )
            st.write(f"- **(-) Taxa ML:** R$ {ml_fee_amount:,.2f}")
            st.write(
                f"- **= Lucro Operacional:** R$ {lucro_operacional:,.2f} ({lucro_operacional_pct:.1f}%)"
            )
        with col2:
            st.write(f"- **(-) Simples Nacional:** R$ {sn_amount:,.2f}")
            st.write(
                f"- **= Lucro Líquido:** R$ {lucro_liquido:,.2f} ({lucro_liquido_pct:.1f}%)"
            )
            st.write("")
            st.write(
                f"- **Total de Custos:** R$ {cmv + ml_fee_amount + sn_amount:,.2f}"
            )
            st.write(
                f"- **ROI:** {(lucro_liquido / result.max_bid_item * 100) if result.max_bid_item > 0 else 0:.1f}%"
            )

        st.markdown("---")
        st.markdown("**💡 Análise de Margem Líquida:**")
        margin_diff = lucro_liquido_pct - (target_net_margin * 100)
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"- **Margem Líquida Desejada:** {target_net_margin * 100:.2f}%")
            st.write(f"- **Margem Líquida Real:** {lucro_liquido_pct:.2f}%")
        with col2:
            if margin_diff > 0:
                st.success(f"✅ **Diferença:** +{margin_diff:.2f}%")
                st.caption("Margem real maior devido aos buffers de segurança")
            elif margin_diff < 0:
                st.error(f"⚠️ **Diferença:** {margin_diff:.2f}%")
                st.caption("Atenção: margem real menor que a desejada")
            else:
                st.info(f"✓ **Diferença:** {margin_diff:.2f}%")
                st.caption("Margem real igual à desejada")


def render_footer():
    """Render page footer"""
    st.markdown("---")
    st.markdown(
        """
    <div style='text-align: center; color: gray; font-size: 0.9em;'>
        <p>Max Bid Calculator - Golpe do Pix</p>
        <p>Calcule lances inteligentes considerando todas as variáveis tributárias e de mercado</p>
    </div>
    """,
        unsafe_allow_html=True,
    )
