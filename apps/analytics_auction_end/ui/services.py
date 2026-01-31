"""
UI helper services for auction end analytics.

These functions are designed to be used in Streamlit UIs,
particularly in the max_bid UI for comparing lot results with max bid calculations.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, BinaryIO

import streamlit as st

from apps.analytics_auction_end.services.pdf_parser import AuctionEndPDFParser
from apps.analytics_auction_end.services.analyzer import (
    AuctionEndAnalyzer,
    LotAnalysis,
    AuctionAnalysis,
)
from apps.analytics_auction_end.services.manual_entry import (
    ManualAuctionEndEntry,
    create_auction_end_from_data,
)
from apps.analytics_auction_end.ui.constants import (
    COMPETITION_LEVEL_LABELS,
    DEFAULT_MAX_PAGES,
)
from shared.domain.auction_end.entities import (
    AuctionEndResult,
    LotResult,
)
from shared.adapters.outbound.postgres_auction_end_storage import (
    PostgresAuctionEndStorage,
)


def initialize_auction_end_storage() -> None:
    """Initialize auction end storage in session state."""
    if "auction_end_storage" not in st.session_state:
        try:
            st.session_state.auction_end_storage = PostgresAuctionEndStorage()
        except Exception:
            # Storage initialization failed - will work without persistence
            st.session_state.auction_end_storage = None

    if "auction_end_result" not in st.session_state:
        st.session_state.auction_end_result = None

    if "auction_end_analyzer" not in st.session_state:
        st.session_state.auction_end_analyzer = AuctionEndAnalyzer(
            storage=st.session_state.auction_end_storage
        )


def parse_auction_end_pdf(
    file: BinaryIO | str | Path,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> AuctionEndResult:
    """
    Parse an auction end PDF and store result in session state.

    Args:
        file: File object, path string, or Path to the PDF.
        max_pages: Maximum pages to parse.

    Returns:
        Parsed AuctionEndResult.
    """
    parser = AuctionEndPDFParser(max_pages=max_pages)

    if isinstance(file, (str, Path)):
        result = parser.parse_file(file)
    else:
        result = parser.parse_bytes(file)

    st.session_state.auction_end_result = result
    return result


def get_lot_result_for_lot(lot_number: int) -> Optional[LotResult]:
    """
    Get the lot result for a specific lot number from the current auction end result.

    Args:
        lot_number: The lot number to look up.

    Returns:
        LotResult or None if not found.
    """
    result = st.session_state.get("auction_end_result")
    if not result:
        return None

    for lot in result.lot_results:
        if lot.lot_number == lot_number:
            return lot
    return None


def get_winning_bid_for_lot(lot_number: int) -> Optional[float]:
    """
    Get the winning bid value for a specific lot.

    Args:
        lot_number: The lot number to look up.

    Returns:
        Winning value or None if lot has no winner.
    """
    lot = get_lot_result_for_lot(lot_number)
    if lot and lot.has_winner:
        return lot.winning_value
    return None


def get_auction_end_analysis() -> Optional[AuctionAnalysis]:
    """
    Get analysis for current auction end result.

    Returns:
        AuctionAnalysis or None if no result loaded.
    """
    result = st.session_state.get("auction_end_result")
    if not result:
        return None

    analyzer = st.session_state.get("auction_end_analyzer")
    if not analyzer:
        analyzer = AuctionEndAnalyzer()

    return analyzer.analyze_auction(result)


def get_lot_analysis(lot_number: int) -> Optional[LotAnalysis]:
    """
    Get analysis for a specific lot.

    Args:
        lot_number: The lot number to analyze.

    Returns:
        LotAnalysis or None if lot not found.
    """
    lot = get_lot_result_for_lot(lot_number)
    if not lot:
        return None

    analyzer = st.session_state.get("auction_end_analyzer")
    if not analyzer:
        analyzer = AuctionEndAnalyzer()

    return analyzer.analyze_lot(lot)


def render_auction_end_summary() -> None:
    """Render summary of the loaded auction end result."""
    result = st.session_state.get("auction_end_result")
    if not result:
        st.info("Nenhum resultado de leilão carregado. Faça upload de um PDF.")
        return

    analysis = get_auction_end_analysis()
    if not analysis:
        return

    st.markdown("### Resumo do Leilão")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Edital", result.edital)
        st.metric("Total de Lotes", analysis.total_lots)

    with col2:
        st.metric("Lotes Arrematados", analysis.lots_with_winner)
        st.metric("Lotes Sem Vencedor", analysis.lots_without_winner)

    with col3:
        st.metric("Valor Total", format_currency(analysis.total_value))
        st.metric("Valor Médio/Lote", format_currency(analysis.average_lot_value))

    with col4:
        st.metric("Total de Propostas", analysis.total_proposals)
        st.metric("Licitantes Únicos", analysis.unique_bidders)

    # Top winner info
    if analysis.top_winner_cnpj:
        st.markdown("---")
        st.markdown("#### Maior Arrematante")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**CNPJ:** {analysis.top_winner_cnpj}")
        with col2:
            st.write(f"**Lotes:** {analysis.top_winner_lots}")
        with col3:
            st.write(f"**Valor:** {format_currency(analysis.top_winner_value)}")
        if analysis.top_winner_name:
            st.write(f"**Razão Social:** {analysis.top_winner_name}")


def render_lot_result_details(lot_number: int) -> None:
    """
    Render detailed results for a specific lot.

    Args:
        lot_number: The lot number to display.
    """
    lot = get_lot_result_for_lot(lot_number)
    if not lot:
        st.warning(f"Lote {lot_number} não encontrado no resultado do leilão.")
        return

    analysis = get_lot_analysis(lot_number)

    st.markdown(f"### Resultado do Lote {lot_number}")

    # Winner info
    if lot.has_winner:
        st.success(f"Lote arrematado por {format_currency(lot.winning_value)}")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Vencedor:** {lot.winner.cnpj_cpf}")
        with col2:
            st.write(f"**Razão Social:** {lot.winner.name}")
    else:
        st.error("Lote sem vencedor")

    # Analysis metrics
    if analysis:
        st.markdown("#### Análise de Competição")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Propostas Classificadas", analysis.classified_proposals)
            st.metric("Propostas Recusadas", analysis.rejected_proposals)
        with col2:
            st.metric("Total de Lances", analysis.total_bids)
            if analysis.bid_increment_average:
                st.metric(
                    "Incremento Médio",
                    format_currency(analysis.bid_increment_average)
                )
        with col3:
            competition_label = COMPETITION_LEVEL_LABELS.get(
                analysis.competition_level, analysis.competition_level
            )
            st.metric("Nível de Competição", competition_label)

    # Proposals table
    if lot.proposals:
        st.markdown("#### Relação de Propostas")
        proposals_data = [
            {
                "Proponente": p.bidder_id,
                "Status": p.status.value,
                "Valor": format_currency(p.value),
                "Data/Hora": p.timestamp.strftime("%d/%m/%Y %H:%M"),
            }
            for p in lot.proposals
        ]
        st.dataframe(proposals_data, use_container_width=True)

    # Bid history table
    if lot.bid_history:
        st.markdown("#### Histórico de Lances")
        bids_data = [
            {
                "Seq": b.sequence,
                "Data/Hora": b.timestamp.strftime("%d/%m/%Y %H:%M"),
                "Valor": format_currency(b.value),
                "Situação": b.status.value,
                "Licitante": b.bidder_id,
            }
            for b in sorted(lot.bid_history, key=lambda x: x.sequence)
        ]
        st.dataframe(bids_data, use_container_width=True)


def render_winner_comparison(lot_number: int, max_bid_calculated: float) -> None:
    """
    Render comparison between calculated max bid and actual winning bid.

    Args:
        lot_number: The lot number to compare.
        max_bid_calculated: The calculated maximum bid value.
    """
    winning_value = get_winning_bid_for_lot(lot_number)

    if winning_value is None:
        st.info(f"Lote {lot_number} não possui vencedor para comparação.")
        return

    st.markdown("### Comparação: Lance Máximo vs. Lance Vencedor")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Lance Máximo Calculado", format_currency(max_bid_calculated))

    with col2:
        st.metric("Lance Vencedor Real", format_currency(winning_value))

    with col3:
        difference = winning_value - max_bid_calculated
        pct_diff = (difference / max_bid_calculated * 100) if max_bid_calculated > 0 else 0

        if difference > 0:
            st.metric(
                "Diferença",
                format_currency(difference),
                delta=f"+{pct_diff:.1f}%",
                delta_color="inverse",  # Red because you would lose
            )
            st.warning(
                "O lance vencedor foi **maior** que seu lance máximo. "
                "Você não teria arrematado este lote."
            )
        elif difference < 0:
            st.metric(
                "Diferença",
                format_currency(abs(difference)),
                delta=f"{pct_diff:.1f}%",
                delta_color="normal",  # Green because you could win
            )
            st.success(
                "O lance vencedor foi **menor** que seu lance máximo. "
                f"Você poderia ter arrematado com uma margem de {format_currency(abs(difference))}."
            )
        else:
            st.metric("Diferença", "R$ 0,00")
            st.info("O lance vencedor é exatamente igual ao seu lance máximo calculado.")


def render_lot_selector() -> Optional[int]:
    """
    Render a lot selector based on loaded auction end result.

    Returns:
        Selected lot number or None.
    """
    result = st.session_state.get("auction_end_result")
    if not result or not result.lot_results:
        return None

    lot_options = {
        f"Lote {lot.lot_number} - {'Arrematado' if lot.has_winner else 'Sem vencedor'}": lot.lot_number
        for lot in sorted(result.lot_results, key=lambda x: x.lot_number)
    }

    selected = st.selectbox(
        "Selecione o Lote",
        options=list(lot_options.keys()),
        key="lot_selector",
    )

    return lot_options.get(selected)


def format_currency(value: float) -> str:
    """
    Format value as Brazilian currency.

    Args:
        value: The value to format.

    Returns:
        Formatted string like "R$ 1.234,56".
    """
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def save_auction_end_result() -> Optional[int]:
    """
    Save current auction end result to database.

    Returns:
        The ID of saved result or None if failed.
    """
    result = st.session_state.get("auction_end_result")
    analyzer = st.session_state.get("auction_end_analyzer")

    if not result:
        st.error("Nenhum resultado carregado para salvar.")
        return None

    if not analyzer or not analyzer.storage:
        st.error("Storage não configurado. Verifique a conexão com o banco de dados.")
        return None

    try:
        result_id = analyzer.save_result(result)
        st.success(f"Resultado salvo com ID: {result_id}")
        return result_id
    except Exception as e:
        st.error(f"Erro ao salvar resultado: {e}")
        return None


def load_auction_end_from_dict(data: dict) -> AuctionEndResult:
    """
    Load auction end result from dictionary data.

    Args:
        data: Dictionary with auction end data.

    Returns:
        Parsed AuctionEndResult.
    """
    result = create_auction_end_from_data(data)
    st.session_state.auction_end_result = result
    return result


def load_auction_end_from_csv(csv_content: str) -> AuctionEndResult:
    """
    Load auction end result from CSV string.

    Args:
        csv_content: CSV string content.

    Returns:
        Parsed AuctionEndResult.
    """
    result = ManualAuctionEndEntry.create_from_csv_string(csv_content)
    st.session_state.auction_end_result = result
    return result


def render_manual_entry_form() -> Optional[AuctionEndResult]:
    """
    Render a form for manual auction end data entry.

    Returns:
        AuctionEndResult if submitted, None otherwise.
    """
    st.markdown("### Entrada Manual de Dados")

    with st.form("manual_entry_form"):
        edital = st.text_input(
            "Número do Edital",
            placeholder="0800100/000008/2025"
        )

        auction_date = st.date_input("Data do Leilão")

        st.markdown("**Resultados dos Lotes:**")
        st.caption("Adicione os lotes no formato: Número | CNPJ Vencedor | Nome | Valor")

        lot_text = st.text_area(
            "Lotes (um por linha)",
            placeholder="3|60.530.186/0001-12|XP MONEY INFORMATICA|112000.00\n4|60.530.186/0001-12|XP MONEY INFORMATICA|113000.00",
            height=200,
        )

        submitted = st.form_submit_button("Carregar Dados")

        if submitted and edital and lot_text:
            lots = []
            for line in lot_text.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|")
                if len(parts) >= 1:
                    lot_number = int(parts[0].strip())
                    cnpj = parts[1].strip() if len(parts) > 1 else None
                    name = parts[2].strip() if len(parts) > 2 else None
                    value_str = parts[3].strip() if len(parts) > 3 else "0"

                    # Parse value
                    try:
                        value = float(value_str.replace(".", "").replace(",", "."))
                    except ValueError:
                        value = None

                    lots.append((lot_number, cnpj, name, value))

            result = ManualAuctionEndEntry.create_simple_result(
                edital=edital,
                auction_date=datetime.combine(auction_date, datetime.min.time()),
                lots=lots,
            )
            st.session_state.auction_end_result = result
            st.success(f"Carregados {len(lots)} lotes.")
            return result

    return None


def render_csv_upload() -> Optional[AuctionEndResult]:
    """
    Render CSV file upload for auction end data.

    Returns:
        AuctionEndResult if uploaded and parsed, None otherwise.
    """
    st.markdown("### Upload de CSV")

    uploaded_file = st.file_uploader(
        "Selecione o arquivo CSV",
        type=["csv"],
        key="csv_upload",
    )

    if uploaded_file is not None:
        try:
            content = uploaded_file.read().decode("utf-8")
            result = load_auction_end_from_csv(content)
            st.success(f"Carregados {len(result.lot_results)} lotes do CSV.")
            return result
        except Exception as e:
            st.error(f"Erro ao processar CSV: {e}")

    return None
