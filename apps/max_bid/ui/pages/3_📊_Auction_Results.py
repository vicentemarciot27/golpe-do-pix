"""Auction Results Analysis Page - Compare with actual winning bids"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from apps.analytics_auction_end import AuctionEndHelper
from apps.analytics_auction_end.ui.constants import COMPETITION_LEVEL_LABELS
from apps.max_bid.ui import constants, services
from shared.domain.auction_end.entities import AuctionEndResult

# Page config
st.set_page_config(
    page_title=f"{constants.PAGE_TITLE} - Resultados",
    page_icon=constants.PAGE_ICON,
    layout=constants.LAYOUT,
    initial_sidebar_state=constants.SIDEBAR_STATE,
)

st.title("📊 Análise de Resultados do Leilão")
st.markdown("Compare seus lances máximos calculados com os resultados reais do leilão.")


def format_currency(value: float) -> str:
    """Format value as Brazilian currency."""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_date(dt) -> str:
    """Format datetime for display."""
    if dt:
        return dt.strftime("%d/%m/%Y %H:%M")
    return "-"


# Initialize helper in session state
if "auction_end_helper" not in st.session_state:
    st.session_state.auction_end_helper = AuctionEndHelper()

if "auction_end_result" not in st.session_state:
    st.session_state.auction_end_result = None

helper = st.session_state.auction_end_helper

# Sidebar - Configuration
st.sidebar.header("⚙️ Configurações")

limit_pages = st.sidebar.checkbox(
    "Limitar páginas",
    value=False,
    help="Marque para limitar o número de páginas processadas",
)

max_pages = None
if limit_pages:
    max_pages = st.sidebar.number_input(
        "Máximo de páginas",
        min_value=1,
        max_value=10000,
        value=100,
        help="Limite o número de páginas a processar",
    )

# ============================================================
# SECTION: Load from saved analyses (TOP)
# ============================================================
st.header("📂 Carregar Análise Salva")

try:
    saved_analyses = helper.list_saved_analyses()
    if saved_analyses:
        # Create options for selectbox
        options = ["-- Selecione uma análise salva --"] + [
            f"{a['edital']} ({format_date(a['created_at'])}) - {a['lots_with_winner']}/{a['total_lots']} lotes"
            for a in saved_analyses
        ]

        selected_idx = st.selectbox(
            "Análises salvas no banco de dados",
            options=list(range(len(options))),
            format_func=lambda x: options[x],
            key="saved_analysis_select",
        )

        if selected_idx > 0:
            selected_analysis = saved_analyses[selected_idx - 1]
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(
                    f"**Edital:** {selected_analysis['edital']} | "
                    f"**Data:** {format_date(selected_analysis['auction_date'])} | "
                    f"**Lotes:** {selected_analysis['lots_with_winner']}/{selected_analysis['total_lots']} | "
                    f"**Valor:** {format_currency(selected_analysis['total_value'])}"
                )
            with col2:
                if st.button("📥 Carregar", type="primary", use_container_width=True):
                    with st.spinner("Carregando análise..."):
                        result = helper.load_full_result(selected_analysis["edital"])
                        if result:
                            st.session_state.auction_end_result = result
                            st.success(f"Análise carregada: {result.edital}")
                            st.rerun()
                        else:
                            st.error("Erro ao carregar análise.")
    else:
        st.info("Nenhuma análise salva no banco de dados.")
except Exception as e:
    st.warning(f"Não foi possível carregar análises salvas: {e}")

st.markdown("---")

# ============================================================
# SECTION: Load new data
# ============================================================
st.header("1. Carregar Novo Resultado")

tab_upload, tab_manual = st.tabs(["📄 Upload PDF", "✏️ Entrada Manual"])

with tab_upload:
    # File path option (more reliable)
    st.markdown("### Carregar do Sistema de Arquivos")
    file_path = st.text_input(
        "Caminho do PDF",
        placeholder=r"C:\Projetos\golpe-do-pix\data\relacao_vencedores_leiloes\arquivo.pdf",
        help="Caminho completo do arquivo PDF no sistema (recomendado)",
    )
    st.markdown("### Ou faça upload")
    st.caption("⚠️ Se o upload falhar, use o caminho do arquivo acima.")
    uploaded_file = st.file_uploader(
        "Selecione o PDF 'Relação de Vencedores'",
        type=["pdf"],
        help="PDF do relatório de vencedores da RFB",
    )

    if file_path or uploaded_file is not None:
        if st.button("🔍 Processar PDF", type="primary"):
            with st.spinner("Processando PDF..."):
                try:
                    result = None

                    # Prefer file path if provided
                    if file_path:
                        file_path_obj = Path(file_path.strip())
                        if file_path_obj.exists():
                            result = helper.parse_pdf(
                                str(file_path_obj), max_pages=max_pages
                            )
                        else:
                            st.error(f"Arquivo não encontrado: {file_path}")
                    elif uploaded_file is not None:
                        # Load from uploaded file
                        import io

                        pdf_bytes = io.BytesIO(uploaded_file.read())
                        result = helper.parse_pdf(pdf_bytes, max_pages=max_pages)

                    if result:
                        st.session_state.auction_end_result = result
                        st.success(
                            f"PDF processado! {result.total_lots} lotes encontrados."
                        )
                except Exception as e:
                    st.error(f"Erro ao processar PDF: {e}")
                    import traceback

                    st.code(traceback.format_exc())

with tab_manual:
    st.markdown("**Entrada manual de resultados:**")

    with st.form("manual_entry"):
        edital = st.text_input(
            "Número do Edital",
            placeholder="0800100/000008/2025",
        )

        st.markdown("**Lotes (um por linha):** `número|cnpj|valor`")
        lots_text = st.text_area(
            "Dados dos Lotes",
            placeholder="3|60.530.186/0001-12|112000\n4|60.530.186/0001-12|113000",
            height=150,
        )

        if st.form_submit_button("Carregar Dados"):
            if edital and lots_text:
                try:
                    lots_data = []
                    for line in lots_text.strip().split("\n"):
                        if not line.strip():
                            continue
                        parts = line.split("|")
                        lot_num = int(parts[0].strip())
                        cnpj = parts[1].strip() if len(parts) > 1 else None
                        value_str = parts[2].strip() if len(parts) > 2 else "0"
                        value = float(value_str.replace(".", "").replace(",", "."))
                        lots_data.append(
                            {
                                "lot_number": lot_num,
                                "winner_cnpj": cnpj if cnpj else None,
                                "winner_name": "",
                                "winning_value": value if value > 0 else None,
                            }
                        )

                    data = {
                        "edital": edital,
                        "auction_date": "",
                        "report_date": "",
                        "lots": lots_data,
                    }
                    result = helper.parse_from_dict(data)
                    st.session_state.auction_end_result = result
                    st.success(f"Dados carregados! {len(lots_data)} lotes.")
                except Exception as e:
                    st.error(f"Erro ao processar dados: {e}")

# Display loaded result
result: AuctionEndResult = st.session_state.auction_end_result

if result:
    st.markdown("---")
    st.header("2. Resumo do Leilão")

    # Analysis
    analysis = helper.analyze_auction(result)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Edital", result.edital)
        st.metric("Total de Lotes", analysis.total_lots)

    with col2:
        st.metric("Lotes Arrematados", analysis.lots_with_winner)
        st.metric("Lotes Sem Vencedor", analysis.lots_without_winner)

    with col3:
        st.metric("Valor Total", format_currency(analysis.total_value))
        st.metric(
            "Valor Médio/Lote",
            format_currency(analysis.average_lot_value)
            if analysis.average_lot_value
            else "-",
        )

    with col4:
        st.metric("Total Propostas", analysis.total_proposals)
        st.metric("Licitantes Únicos", analysis.unique_bidders)

    # Top winner
    if analysis.top_winner_cnpj:
        st.markdown("---")
        st.subheader("🏆 Maior Arrematante")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**CNPJ:** {analysis.top_winner_cnpj}")
        with col2:
            st.write(f"**Lotes:** {analysis.top_winner_lots}")
        with col3:
            st.write(f"**Valor:** {format_currency(analysis.top_winner_value)}")
        if analysis.top_winner_name:
            st.write(f"**Razão Social:** {analysis.top_winner_name}")

    # Lots table
    st.markdown("---")
    st.header("3. Resultados por Lote")

    lots_data = []
    for lot in sorted(result.lot_results, key=lambda x: x.lot_number):
        summary = helper.get_lot_summary(lot)
        lots_data.append(
            {
                "Lote": summary.lot_number,
                "Vencedor": summary.winner_cnpj if summary.has_winner else "-",
                "Valor": format_currency(summary.winning_value)
                if summary.winning_value
                else "-",
                "Propostas": summary.total_proposals,
                "Lances": summary.total_bids,
            }
        )

    st.dataframe(lots_data, use_container_width=True, hide_index=True)

    # Comparison section
    st.markdown("---")
    st.header("4. Comparar com Lance Máximo Calculado")

    st.markdown(
        "Insira seus lances máximos calculados para comparar com os resultados reais."
    )

    # Initialize max bids in session state
    if "comparison_max_bids" not in st.session_state:
        st.session_state.comparison_max_bids = {}

    # Input for max bids
    with st.expander("➕ Adicionar Lances Máximos", expanded=True):
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            lot_options = [
                lot.lot_number for lot in result.lot_results if lot.has_winner
            ]
            selected_lot = st.selectbox(
                "Lote",
                options=lot_options,
                key="compare_lot_select",
            )

        with col2:
            max_bid_value = st.number_input(
                "Lance Máximo Calculado (R$)",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%.2f",
                key="compare_max_bid_input",
            )

        with col3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("Adicionar", use_container_width=True):
                if selected_lot and max_bid_value > 0:
                    st.session_state.comparison_max_bids[selected_lot] = max_bid_value
                    st.rerun()

    # Show current max bids
    if st.session_state.comparison_max_bids:
        st.markdown("**Lances Máximos Cadastrados:**")

        bids_to_remove = []
        for lot_num, max_bid in sorted(st.session_state.comparison_max_bids.items()):
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                st.write(f"Lote {lot_num}")
            with col2:
                st.write(format_currency(max_bid))
            with col3:
                if st.button("🗑️", key=f"remove_{lot_num}"):
                    bids_to_remove.append(lot_num)

        for lot_num in bids_to_remove:
            del st.session_state.comparison_max_bids[lot_num]
            st.rerun()

        # Run comparison
        st.markdown("---")
        if st.button(
            "📊 Analisar Comparação", type="primary", use_container_width=True
        ):
            comparisons = helper.compare_all_lots(
                result, st.session_state.comparison_max_bids
            )

            if comparisons:
                st.subheader("Resultado da Análise")

                # Summary metrics
                would_win = sum(1 for c in comparisons if c.would_have_won)
                would_lose = len(comparisons) - would_win

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Lotes Analisados", len(comparisons))
                with col2:
                    st.metric("Teria Arrematado", would_win, delta_color="normal")
                with col3:
                    st.metric("Não Arremataria", would_lose, delta_color="inverse")

                # Detailed comparison
                st.markdown("---")

                for comp in comparisons:
                    lot = helper.get_lot_by_number(result, comp.lot_number)

                    with st.expander(
                        f"Lote {comp.lot_number} - {'✅ Arremataria' if comp.would_have_won else '❌ Não Arremataria'}",
                        expanded=True,
                    ):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.metric(
                                "Lance Máximo Calculado",
                                format_currency(comp.calculated_max_bid),
                            )

                        with col2:
                            st.metric(
                                "Lance Vencedor Real",
                                format_currency(comp.actual_winning_bid)
                                if comp.actual_winning_bid
                                else "-",
                            )

                        with col3:
                            if comp.difference is not None:
                                delta_str = f"{comp.difference_percent:+.1f}%"
                                st.metric(
                                    "Diferença",
                                    format_currency(abs(comp.difference)),
                                    delta=delta_str,
                                    delta_color="inverse"
                                    if comp.difference > 0
                                    else "normal",
                                )

                        # Analysis message
                        if comp.would_have_won:
                            margin = abs(comp.difference) if comp.difference else 0
                            st.success(
                                f"✅ Você **teria arrematado** este lote com uma margem de "
                                f"{format_currency(margin)}."
                            )
                        else:
                            deficit = comp.difference if comp.difference else 0
                            st.warning(
                                f"❌ O lance vencedor foi **maior** que seu limite. "
                                f"Você precisaria de mais {format_currency(deficit)} para vencer."
                            )

                        # Winner info
                        if comp.winner_cnpj:
                            st.caption(
                                f"Vencedor: {comp.winner_cnpj} - {comp.winner_name}"
                            )

                        # Lot analysis
                        if lot:
                            lot_analysis = helper.analyze_lot(lot)
                            competition_label = COMPETITION_LEVEL_LABELS.get(
                                lot_analysis.competition_level,
                                lot_analysis.competition_level,
                            )
                            st.caption(
                                f"Competição: {competition_label} | "
                                f"Propostas: {lot_analysis.total_proposals} | "
                                f"Lances: {lot_analysis.total_bids}"
                            )

    # Save to database
    st.markdown("---")
    st.header("5. Salvar no Banco de Dados")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Salvar Resultado", use_container_width=True):
            try:
                result_id = helper.save_to_database(result)
                st.success(f"Resultado salvo com ID: {result_id}")
                st.rerun()  # Refresh to show in saved analyses
            except ValueError as e:
                st.error(f"Erro: {e}")
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    with col2:
        if st.button("🗑️ Limpar Dados", use_container_width=True):
            st.session_state.auction_end_result = None
            st.session_state.comparison_max_bids = {}
            st.rerun()

else:
    st.info(
        "👆 Selecione uma análise salva acima ou carregue um novo PDF/dados manualmente."
    )

# ============================================================
# SECTION: Saved analyses table (BOTTOM)
# ============================================================
st.markdown("---")
st.header("📋 Histórico de Análises Salvas")

try:
    saved_analyses = helper.list_saved_analyses()
    if saved_analyses:
        table_data = [
            {
                "Edital": a["edital"],
                "Data Leilão": format_date(a["auction_date"]),
                "Data Análise": format_date(a["created_at"]),
                "Lotes": f"{a['lots_with_winner']}/{a['total_lots']}",
                "Valor Total": format_currency(a["total_value"]),
            }
            for a in saved_analyses
        ]
        st.dataframe(table_data, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma análise salva ainda.")
except Exception as e:
    st.warning(f"Não foi possível carregar histórico: {e}")

# Footer
services.render_footer()
