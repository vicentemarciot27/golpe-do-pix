import logging
import time
import requests
from dataclasses import asdict
from datetime import datetime
from typing import Any
from shared.domain.auction.entities.auction import Auction
from shared.domain.auction.entities.item import Item
from shared.domain.auction.entities.lot import Lot
from shared.domain.auction.value_objects import AvisoErrata, LotImage
from config.rfb_auction_tools.settings import RFBAuctionSettings


logger = logging.getLogger(__name__)


class LotUnavailableError(Exception):
    """Raised when a lot is in a state that cannot be queried via API (HTTP 422)."""

    pass


class RFBAuctionCollector:
    """Collector for RFB auction data via HTTP requests."""

    def __init__(self, settings: RFBAuctionSettings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; RFBAuctionCollector/1.0)",
            "Accept": "application/json",
        })

    def _request(self, endpoint: str) -> dict[str, Any]:
        """Make a GET request to the RFB API with retry on server errors."""
        url = f"{self.settings.base_url}/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries):
            try:
                response = self.session.get(url, timeout=self.settings.request_timeout)
                response.raise_for_status()

                if self.settings.request_delay > 0:
                    time.sleep(self.settings.request_delay)

                return response.json()

            except requests.exceptions.HTTPError as e:
                last_error = e
                if e.response is not None and e.response.status_code < 500:
                    raise
                wait_time = self.settings.retry_backoff_base ** attempt
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.settings.max_retries}): "
                    f"{e}. Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)

            except requests.exceptions.RequestException as e:
                last_error = e
                wait_time = self.settings.retry_backoff_base ** attempt
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.settings.max_retries}): "
                    f"{e}. Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)

        raise last_error

    def _parse_datetime(self, date_str: str | None) -> datetime | None:
        """Parse datetime string from RFB API format."""
        if not date_str:
            return None
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")

    def _parse_aviso_errata(self, data: dict[str, Any]) -> AvisoErrata:
        """Parse AvisoErrata from JSON data."""
        return AvisoErrata(
            data=self._parse_datetime(data["data"]),
            codigo_tipo=data["codigoTipo"],
            tipo=data["tipo"],
            texto=data["texto"],
            id=None,
            auction_id=None,
            lot_id=None,
        )

    def _parse_lot_image(self, data: dict[str, Any]) -> LotImage:
        """Parse LotImage from JSON data."""
        return LotImage(
            rfb_id=data["imllNrSq"],
            url=data["src"],
            thumbnail_url=data["min"],
            width=data["w"],
            height=data["h"],
            is_featured=data.get("destaque", False),
            id=None,
            lot_id=None,
        )

    def _parse_item(self, data: dict[str, Any]) -> Item:
        """Parse Item from JSON data."""
        return Item(
            recinto_armazenador=data["recintoArmazenador"],
            quantidade=data["quantidade"],
            unidade_medida=data["unMedida"],
            descricao=data["descricao"],
            nr_referencia=data.get("nrReferencia"),
            id=None,
            lot_id=None,
        )

    def _parse_lot_from_list(self, data: dict[str, Any], edle: str, edital: str) -> Lot:
        """Parse Lot from listaLotes data (without items)."""
        imagens = [self._parse_lot_image(img) for img in data.get("imagens", [])]

        return Lot(
            rfb_id=data["loleNrSq"],
            numero=data["nrAtribuido"],
            edle=edle,
            edital=edital,
            tipo=data["tipo"],
            orgao="Receita Federal do Brasil",
            cidade="",  # Not available in list view
            valor_minimo=data["valorMinimo"],
            situacao_lote=data["situacaoLote"],
            situacao_edital=data.get("situacaoEdital", 0),
            tipo_edital=data.get("tipoEdital", 0),
            permite_pf=data["permitePF"],
            possui_imagens=data["possuiImagens"],
            destaque=data["destaque"],
            nr_avisos=data["nrAvisos"],
            nr_erratas=data["nrErratas"],
            itens=[],
            imagens=imagens,
            avisos_erratas=[],
            id=None,
            auction_id=None,
        )

    def _parse_lot_details(self, data: dict[str, Any]) -> Lot:
        """Parse Lot from lot details endpoint (with items)."""
        itens = [self._parse_item(item) for item in data.get("itensDetalhesLote", [])]
        imagens = [self._parse_lot_image(img) for img in data.get("imagens", [])]
        avisos = [self._parse_aviso_errata(av) for av in data.get("avisosErratas", [])]

        return Lot(
            rfb_id=data["loleNrSq"],
            numero=data["nrAtribuido"],
            edle=data["edle"],
            edital=data["edital"],
            tipo=data["tipo"],
            orgao=data["orgao"],
            cidade=data["cidade"],
            valor_minimo=data["valorMinimo"],
            situacao_lote=data["situacaoLote"],
            situacao_edital=data["situacaoEdital"],
            tipo_edital=data["tipoEdital"],
            permite_pf=data["permitePF"],
            possui_imagens=data["possuiImagens"],
            destaque=data["destaque"],
            nr_avisos=data["nrAvisos"],
            nr_erratas=data["nrErratas"],
            itens=itens,
            imagens=imagens,
            avisos_erratas=avisos,
            id=None,
            auction_id=None,
        )

    def _parse_auction_from_list(self, data: dict[str, Any]) -> Auction:
        """Parse Auction from editais-disponiveis list."""
        return Auction(
            edital=data["edital"],
            edle=data["edle"],
            tipo=str(data["tipo"]),
            orgao=data["orgao"],
            cidade=data["cidade"],
            unidade_nome=data["uaNm"],
            codigo_situacao=data["codigoSituacao"],
            permite_pf=data["permitePF"],
            data_inicio_propostas=self._parse_datetime(data["dataInicioPropostas"]),
            data_fim_propostas=self._parse_datetime(data["dataFimPropostas"]),
            data_abertura_lances=self._parse_datetime(data["dataAberturaLances"]),
            total_lotes=data["lotes"],
            mercadorias_apreendidas=data.get("mercadoriasApreendidas"),
            data_classificacao=None,
            forma_contato=None,
            dados_publicacao=None,
            numero_recursos=0,
            numero_avisos=0,
            numero_erratas=0,
            lotes=[],
            avisos_erratas=[],
            id=None,
        )

    def _parse_auction_details(self, data: dict[str, Any]) -> Auction:
        """Parse Auction from edital details endpoint."""
        lotes = [
            self._parse_lot_from_list(lot, data["edle"], data["edital"])
            for lot in data.get("listaLotes", [])
        ]
        avisos = [self._parse_aviso_errata(av) for av in data.get("avisosErratas", [])]

        return Auction(
            edital=data["edital"],
            edle=data["edle"],
            tipo=str(data["tipo"]),
            orgao=data["orgao"],
            cidade=data["cidade"],
            unidade_nome=data.get("cidade", ""),  # In details, cidade is the full name
            codigo_situacao=data["situacao"],
            permite_pf=data["permitePF"],
            data_inicio_propostas=self._parse_datetime(data["dataInicioPropostas"]),
            data_fim_propostas=self._parse_datetime(data["dataFimPropostas"]),
            data_abertura_lances=self._parse_datetime(data["dataAberturaLances"]),
            total_lotes=len(lotes),
            mercadorias_apreendidas=data.get("mercadoriasApreendidas"),
            data_classificacao=self._parse_datetime(data.get("dataClassificacao")),
            forma_contato=data.get("formaContato"),
            dados_publicacao=data.get("dadosPublicacao"),
            numero_recursos=data.get("numeroRecursos", 0),
            numero_avisos=data.get("numeroAvisos", 0),
            numero_erratas=data.get("numeroErratas", 0),
            lotes=lotes,
            avisos_erratas=avisos,
            id=None,
        )

    def fetch_available_auctions(self) -> list[Auction]:
        """Fetch all available auctions from RFB API."""
        data = self._request("editais-disponiveis")
        auctions = []

        for situacao in data.get("situacoes", []):
            for auction_data in situacao.get("lista", []):
                auction = self._parse_auction_from_list(auction_data)
                auctions.append(auction)

        return auctions

    def fetch_auction_details(self, edle: str) -> Auction:
        """Fetch detailed auction data including lots."""
        data = self._request(f"edital/{edle}")
        return self._parse_auction_details(data)

    def fetch_lot_details(self, edle: str, lot_id: int) -> Lot:
        """Fetch detailed lot data including items.

        Raises:
            LotUnavailableError: If lot is in a non-queryable state (HTTP 422)
            requests.exceptions.RequestException: For other request errors
        """
        try:
            data = self._request(f"lote/{edle}/{lot_id}")
            return self._parse_lot_details(data)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:
                raise LotUnavailableError(f"Lot {lot_id} unavailable: {e}") from e
            raise

    def collect_test_sample(self) -> dict[str, list[Any]]:
        """
        Collect a test sample following the rules:
        1. One auction per distinct codigo_situacao
        2. One lot per auction collected
        3. All items for each lot collected

        Returns data grouped by entity type.
        """
        result: dict[str, list[Any]] = {
            "auctions": [],
            "lots": [],
            "items": [],
            "lot_images": [],
            "avisos_erratas": [],
        }

        # Fetch available auctions
        available = self._request("editais-disponiveis")
        seen_situacoes: set[int] = set()
        selected_auctions: list[dict[str, Any]] = []

        # Select one auction per codigo_situacao
        for situacao in available.get("situacoes", []):
            situacao_code = situacao["situacao"]
            if situacao_code not in seen_situacoes and situacao.get("lista"):
                seen_situacoes.add(situacao_code)
                selected_auctions.append(situacao["lista"][0])

        # Process each selected auction
        for auction_data in selected_auctions:
            edle = auction_data["edle"]

            # Fetch auction details
            auction_details = self._request(f"edital/{edle}")
            auction = self._parse_auction_details(auction_details)

            # Add auction to result (convert to dict)
            auction_dict = asdict(auction)
            auction_dict["lotes"] = []  # Remove nested lotes
            auction_dict["avisos_erratas"] = []  # Will add separately
            result["auctions"].append(auction_dict)

            # Add auction-level avisos_erratas
            for aviso in auction.avisos_erratas:
                aviso_dict = asdict(aviso)
                aviso_dict["_auction_edle"] = edle  # Reference
                result["avisos_erratas"].append(aviso_dict)

            # Get first lot details if available
            if auction_details.get("listaLotes"):
                first_lot_data = auction_details["listaLotes"][0]
                lot_id = first_lot_data["loleNrSq"]

                # Fetch lot details with items
                lot = self.fetch_lot_details(edle, lot_id)

                # Add lot to result
                lot_dict = asdict(lot)
                lot_dict["itens"] = []  # Remove nested items
                lot_dict["imagens"] = []  # Will add separately
                lot_dict["avisos_erratas"] = []  # Will add separately
                lot_dict["_auction_edle"] = edle  # Reference
                result["lots"].append(lot_dict)

                # Add all items
                for item in lot.itens:
                    item_dict = asdict(item)
                    item_dict["_lot_rfb_id"] = lot.rfb_id  # Reference
                    item_dict["_auction_edle"] = edle  # Reference
                    result["items"].append(item_dict)

                # Add all images
                for image in lot.imagens:
                    image_dict = asdict(image)
                    image_dict["_lot_rfb_id"] = lot.rfb_id  # Reference
                    image_dict["_auction_edle"] = edle  # Reference
                    result["lot_images"].append(image_dict)

                # Add lot-level avisos_erratas
                for aviso in lot.avisos_erratas:
                    aviso_dict = asdict(aviso)
                    aviso_dict["_lot_rfb_id"] = lot.rfb_id  # Reference
                    aviso_dict["_auction_edle"] = edle  # Reference
                    result["avisos_erratas"].append(aviso_dict)

        return result
