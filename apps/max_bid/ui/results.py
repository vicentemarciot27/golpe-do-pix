"""
Results rendering services for Max Bid Calculator UI
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from apps.max_bid.ui import services


def render_single_item_result(
    result,
    ml_fee,
    target_net_margin,
    revenue_last_12months,
    sn_mode_enum,
    cost_risk_buffer,
):
    """Render calculation results for a single item"""
    st.success("✅ Cálculo realizado com sucesso!")

    # Calculate metrics
    cmv = result.max_bid_item + result.ncm_taxes_total
    lucro_bruto = result.expected_rev - cmv
    lucro_bruto_pct = (
        (lucro_bruto / result.expected_rev * 100) if result.expected_rev > 0 else 0
    )

    ml_fee_amount = result.expected_rev * ml_fee
    lucro_operacional = lucro_bruto - ml_fee_amount

    sn_amount = result.expected_rev * result.simples_nacional_tax_effective_rate
    lucro_liquido = lucro_operacional - sn_amount
    lucro_liquido_pct = (
        (lucro_liquido / result.expected_rev * 100) if result.expected_rev > 0 else 0
    )

    roi = (lucro_liquido / result.max_bid_item * 100) if result.max_bid_item > 0 else 0

    # Main result metrics
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "💲 Preço de Venda",
            f"R$ {result.expected_rev:,.2f}",
            help="Receita esperada (preço ML ajustado pelo buffer de risco)\nCálculo: Preço ML × Quantidade × (1 - Buffer de Risco de Venda)",
        )
    with col2:
        st.metric(
            "💰 Lance Máximo",
            f"R$ {result.max_bid_item:,.2f}",
            help="Valor máximo que você deve ofertar\nCálculo: Numerador / Denominador\nOnde Numerador = Receita × (1 - Margem Líquida - SN - Taxa ML)\nDenominador = (1 + Impostos NCM) × (1 + Buffer de Custo)",
        )
    with col3:
        st.metric(
            "💚 Lucro Bruto",
            f"R$ {lucro_bruto:,.2f}",
            delta=f"{lucro_bruto_pct:.1f}%",
            help="Lucro Bruto = Receita - CMV\nOnde CMV = Lance + Impostos NCM\nMargem % = (Lucro Bruto / Receita) × 100",
        )
    with col4:
        st.metric(
            "💵 Lucro Líquido",
            f"R$ {lucro_liquido:,.2f}",
            delta=f"{lucro_liquido_pct:.1f}%",
            help="Lucro Líquido = Lucro Bruto - Taxa ML - Simples Nacional\nMargem % = (Lucro Líquido / Receita) × 100",
        )
    with col5:
        st.metric(
            "📈 ROI",
            f"{roi:.1f}%",
            help="Retorno sobre Investimento\nCálculo: (Lucro Líquido / Lance Máximo) × 100",
        )

    # Detailed breakdown
    st.markdown("---")
    st.subheader("📋 Detalhamento do Cálculo")
    services.render_result_details(
        result,
        ml_fee,
        target_net_margin,
        revenue_last_12months,
        sn_mode_enum,
        cost_risk_buffer,
    )


def render_lot_summary_metrics(totals, num_items):
    """Render summary metrics for lot calculation"""
    st.success("✅ Cálculo realizado com sucesso!")

    st.markdown("---")
    st.subheader("🎯 Resultado Total do Lote")

    # Calculate average selling price per item type
    avg_selling_price = (
        totals["total_expected_rev"] / totals["total_items_qty"]
        if totals["total_items_qty"] > 0
        else 0
    )
    roi_total = (
        (totals["lucro_liquido"] / totals["total_max_bid"] * 100)
        if totals["total_max_bid"] > 0
        else 0
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "💲 Receita Total Esperada",
            f"R$ {totals['total_expected_rev']:,.2f}",
            help="Receita total esperada do lote\nCálculo: Soma de (Preço ML × Qtd × (1 - Buffer Venda)) de cada item",
        )
    with col2:
        st.metric(
            "💰 Lance Máximo Total",
            f"R$ {totals['total_max_bid']:,.2f}",
            help="Valor máximo total a ofertar pelo lote\nCálculo: Soma dos lances máximos de cada item",
        )
    with col3:
        st.metric(
            "💚 Lucro Bruto Total",
            f"R$ {totals['lucro_bruto']:,.2f}",
            delta=f"{totals['lucro_bruto_pct']:.1f}%",
            help="Lucro Bruto Total = Receita Total - CMV Total\nOnde CMV = Lance + Impostos NCM\nMargem % = (Lucro Bruto / Receita) × 100",
        )
    with col4:
        st.metric(
            "💵 Lucro Líquido Total",
            f"R$ {totals['lucro_liquido']:,.2f}",
            delta=f"{totals['lucro_liquido_pct']:.1f}%",
            help="Lucro Líquido Total = Lucro Bruto - Taxa ML - Simples Nacional\nMargem % = (Lucro Líquido / Receita) × 100",
        )
    with col5:
        st.metric(
            "📈 ROI Total",
            f"{roi_total:.1f}%",
            help="Retorno sobre Investimento Total\nCálculo: (Lucro Líquido Total / Lance Máximo Total) × 100",
        )

    # Second row with additional info
    st.markdown("")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "📦 Tipos de Itens",
            num_items,
            help="Número de tipos diferentes de itens no lote\n(cada tipo pode ter quantidade > 1)",
        )
    with col2:
        st.metric(
            "💲 Preço de Venda Médio",
            f"R$ {avg_selling_price:,.2f}",
            help="Receita esperada média por tipo de item\nCálculo: Receita Total / Número de Tipos",
        )
    with col3:
        avg_max_bid = totals["total_max_bid"] / num_items if num_items > 0 else 0
        st.metric(
            "💰 Lance Médio",
            f"R$ {avg_max_bid:,.2f}",
            help="Lance máximo médio por tipo de item\nCálculo: Lance Total / Número de Tipos",
        )


def render_lot_items_table(results, ml_fee):
    """Render table with all lot items details"""
    st.markdown("---")
    st.subheader("📋 Detalhamento por Item")

    df_data = []
    for r in results:
        result = r["result"]
        item = r["item"]

        # Cálculos corretos
        cmv = result.max_bid_item + result.ncm_taxes_total
        lucro_bruto = result.expected_rev - cmv
        ml_fee_amount = result.expected_rev * ml_fee
        lucro_operacional = lucro_bruto - ml_fee_amount
        sn_amount = result.expected_rev * result.simples_nacional_tax_effective_rate
        lucro_liquido = lucro_operacional - sn_amount
        lucro_liquido_pct = (
            (lucro_liquido / result.expected_rev * 100)
            if result.expected_rev > 0
            else 0
        )

        df_data.append(
            {
                "Item": r["description"],
                "Qtd": item["qty"],
                "Preço ML": f"R$ {item['ml_price_avg']:,.2f}",
                "Preço Venda": f"R$ {(result.expected_rev / item['qty']):,.2f}",
                "NCM": item["ncm"],
                "Lance Máx": f"R$ {result.max_bid_item:,.2f}",
                "Lucro Líquido": f"R$ {lucro_liquido:,.2f}",
                "Margem Líq. %": f"{lucro_liquido_pct:.1f}%",
            }
        )

    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_lot_financial_summary(totals):
    """Render financial summary for lot"""
    st.markdown("**Demonstrativo de Resultado (DRE) do Lote:**")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📊 Receitas e Custos:**")
        st.write(f"- **Receita Bruta:** R$ {totals['total_expected_rev']:,.2f}")
        st.write("- **(-) CMV:**")
        st.write(f"  - Lance: R$ {totals['total_max_bid']:,.2f}")
        st.write(f"  - Impostos NCM: R$ {totals['total_ncm_taxes']:,.2f}")
        st.write(
            f"- **= Lucro Bruto:** R$ {totals['lucro_bruto']:,.2f} ({totals['lucro_bruto_pct']:.1f}%)"
        )
        st.write("- **(-) Despesas Operacionais:**")
        st.write(f"  - Taxa ML: R$ {totals['total_ml_fee']:,.2f}")
        st.write(f"- **= Lucro Operacional:** R$ {totals['lucro_operacional']:,.2f}")

    with col2:
        st.markdown("**💰 Resultado Final:**")
        st.write("- **(-) Impostos sobre Receita:**")
        st.write(f"  - Simples Nacional: R$ {totals['total_sn']:,.2f}")
        st.write(
            f"- **= Lucro Líquido:** R$ {totals['lucro_liquido']:,.2f} ({totals['lucro_liquido_pct']:.1f}%)"
        )
        st.write("")
        st.write(f"- **Total Investido:** R$ {totals['total_max_bid']:,.2f}")
        st.write(
            f"- **ROI:** {(totals['lucro_liquido'] / totals['total_max_bid'] * 100) if totals['total_max_bid'] > 0 else 0:.1f}%"
        )

    # Summary chart data
    st.markdown("---")
    st.markdown("**Composição da Receita:**")

    labels = ["Lucro Líquido", "Simples Nacional", "Taxa ML", "Impostos NCM", "Lance"]
    values = [
        totals["lucro_liquido"],
        totals["total_sn"],
        totals["total_ml_fee"],
        totals["total_ncm_taxes"],
        totals["total_max_bid"],
    ]
    colors = ["#28a745", "#dc3545", "#fd7e14", "#ffc107", "#007bff"]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textposition="auto",
                hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
            )
        ]
    )

    fig.update_layout(showlegend=True, height=500, margin=dict(t=40, b=40, l=40, r=40))

    st.plotly_chart(fig, use_container_width=True)


def render_lot_items_details(
    results,
    ml_fee,
    target_net_margin,
    revenue_last_12months,
    sn_mode_enum,
    cost_risk_buffer,
):
    """Render detailed breakdown for each item in lot"""
    for r in results:
        result = r["result"]
        item = r["item"]

        with st.expander(f"📦 {r['description']}", expanded=False):
            # Cálculos corretos
            cmv = result.max_bid_item + result.ncm_taxes_total
            lucro_bruto = result.expected_rev - cmv
            lucro_bruto_pct = (
                (lucro_bruto / result.expected_rev * 100)
                if result.expected_rev > 0
                else 0
            )

            ml_fee_amount = result.expected_rev * ml_fee
            lucro_operacional = lucro_bruto - ml_fee_amount

            sn_amount = result.expected_rev * result.simples_nacional_tax_effective_rate
            lucro_liquido = lucro_operacional - sn_amount
            lucro_liquido_pct = (
                (lucro_liquido / result.expected_rev * 100)
                if result.expected_rev > 0
                else 0
            )

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "💲 Preço de Venda",
                    f"R$ {result.expected_rev / item['qty']:,.2f}",
                    help="Receita esperada deste item\nCálculo: Preço ML × Qtd × (1 - Buffer de Risco de Venda)",
                )
            with col2:
                st.metric(
                    "💰 Lance Máximo",
                    f"R$ {result.max_bid_item:,.2f}",
                    help="Valor máximo a ofertar por este item\nCálculo: [Receita × (1 - Margem - SN - ML Fee)] / [(1 + Impostos NCM) × (1 + Buffer Custo)]",
                )
            with col3:
                st.metric(
                    "💚 Lucro Bruto",
                    f"R$ {lucro_bruto:,.2f}",
                    delta=f"{lucro_bruto_pct:.1f}%",
                    help="Lucro Bruto = Receita - CMV\nCMV = Lance + Impostos NCM\nMargem % = (Lucro Bruto / Receita) × 100",
                )
            with col4:
                st.metric(
                    "💵 Lucro Líquido",
                    f"R$ {lucro_liquido:,.2f}",
                    delta=f"{lucro_liquido_pct:.1f}%",
                    help="Lucro Líquido = Lucro Bruto - Taxa ML - Simples Nacional\nMargem % = (Lucro Líquido / Receita) × 100",
                )
            with col5:
                roi = (
                    (lucro_liquido / result.max_bid_item * 100)
                    if result.max_bid_item > 0
                    else 0
                )
                st.metric(
                    "📈 ROI",
                    f"{roi:.1f}%",
                    help="Retorno sobre Investimento\nCálculo: (Lucro Líquido / Lance Máximo) × 100",
                )

            st.markdown("**Detalhes:**")
            services.render_result_details(
                result,
                ml_fee,
                target_net_margin,
                revenue_last_12months,
                sn_mode_enum,
                cost_risk_buffer,
            )


def calculate_lot_totals(results, ml_fee):
    """Calculate totals for lot results"""
    total_max_bid = sum(r["result"].max_bid_item for r in results)
    total_expected_rev = sum(r["result"].expected_rev for r in results)
    total_ncm_taxes = sum(r["result"].ncm_taxes_total for r in results)
    total_ml_fee = sum(r["result"].expected_rev * ml_fee for r in results)
    total_sn = sum(
        r["result"].expected_rev * r["result"].simples_nacional_tax_effective_rate
        for r in results
    )
    total_items_qty = sum(r["item"]["qty"] for r in results)

    # Cálculos contábeis corretos
    total_cmv = total_max_bid + total_ncm_taxes
    lucro_bruto = total_expected_rev - total_cmv
    lucro_bruto_pct = (
        (lucro_bruto / total_expected_rev * 100) if total_expected_rev > 0 else 0
    )

    lucro_operacional = lucro_bruto - total_ml_fee

    lucro_liquido = lucro_operacional - total_sn
    lucro_liquido_pct = (
        (lucro_liquido / total_expected_rev * 100) if total_expected_rev > 0 else 0
    )

    return {
        "total_max_bid": total_max_bid,
        "total_expected_rev": total_expected_rev,
        "total_ncm_taxes": total_ncm_taxes,
        "total_ml_fee": total_ml_fee,
        "total_sn": total_sn,
        "total_cmv": total_cmv,
        "lucro_bruto": lucro_bruto,
        "lucro_bruto_pct": lucro_bruto_pct,
        "lucro_operacional": lucro_operacional,
        "lucro_liquido": lucro_liquido,
        "lucro_liquido_pct": lucro_liquido_pct,
        "total_items_qty": total_items_qty,
    }
