"""
Script principal para sincronização de dados de leilões RFB.

Este script coleta dados de todos os leilões disponíveis na API da RFB
e sincroniza com o banco de dados PostgreSQL.
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config.rfb_auction_tools.settings import get_settings
from shared.infrastructure.postgres import get_pool, PostgresConnectionPool
from shared.adapters.outbound.postgres_auction_storage import PostgresAuctionStorage
from apps.rfb_auction_tools.collectors import RFBAuctionCollector
from apps.rfb_auction_tools.sync import RFBAuctionSync


def setup_logging(verbose: bool = False) -> None:
    """Configura o sistema de logging."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Formato do log
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Configuração básica
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Silencia logs verbosos de bibliotecas externas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description='Sincroniza dados de leilões RFB com o banco de dados'
    )

    parser.add_argument(
        '--no-lot-details',
        action='store_true',
        help='Não busca detalhes individuais de cada lote (mais rápido, mas sem items)'
    )

    parser.add_argument(
        '--env-file',
        type=str,
        default=None,
        help='Caminho para arquivo .env com configurações (padrão: config/.env)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Ativa logging detalhado (DEBUG)'
    )

    parser.add_argument(
        '--db-host',
        type=str,
        default=None,
        help='Host do banco PostgreSQL (sobrescreve variável de ambiente)'
    )

    parser.add_argument(
        '--db-port',
        type=int,
        default=None,
        help='Porta do banco PostgreSQL (sobrescreve variável de ambiente)'
    )

    parser.add_argument(
        '--db-name',
        type=str,
        default=None,
        help='Nome do banco PostgreSQL (sobrescreve variável de ambiente)'
    )

    parser.add_argument(
        '--db-user',
        type=str,
        default=None,
        help='Usuário do banco PostgreSQL (sobrescreve variável de ambiente)'
    )

    parser.add_argument(
        '--db-password',
        type=str,
        default=None,
        help='Senha do banco PostgreSQL (sobrescreve variável de ambiente)'
    )

    return parser.parse_args()


def build_db_config(args: argparse.Namespace) -> dict | None:
    """Constrói configuração do banco a partir dos argumentos CLI."""
    # Se nenhum argumento de DB foi fornecido, usa variáveis de ambiente
    if not any([args.db_host, args.db_port, args.db_name, args.db_user, args.db_password]):
        return None

    import os
    config = {
        "host": args.db_host or os.getenv("POSTGRES_HOST", "localhost"),
        "port": args.db_port or int(os.getenv("POSTGRES_PORT", 5435)),
        "database": args.db_name or os.getenv("POSTGRES_DB", "golpe_do_pix"),
        "user": args.db_user or os.getenv("POSTGRES_USER", "postgres"),
        "password": args.db_password or os.getenv("POSTGRES_PASSWORD", "postgres"),
    }
    return config


def main() -> int:
    """Função principal."""
    args = parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("RFB Auction Tools - Sincronização de Leilões")
    logger.info("=" * 80)

    start_time = datetime.now()

    try:
        # 1. Carrega configurações
        logger.info("Carregando configurações...")
        settings = get_settings(args.env_file)
        logger.info(f"  Base URL: {settings.base_url}")
        logger.info(f"  Timeout: {settings.request_timeout}s")
        logger.info(f"  Max retries: {settings.max_retries}")
        logger.info(f"  Request delay: {settings.request_delay}s")

        # 2. Configura conexão com banco
        logger.info("Configurando conexão com banco de dados...")
        db_config = build_db_config(args)
        pool = get_pool(db_config=db_config, minconn=2, maxconn=10)
        logger.info("  Pool de conexões criado")

        # 3. Cria storage
        logger.info("Inicializando storage...")
        storage = PostgresAuctionStorage(pool)

        # 4. Cria collector
        logger.info("Inicializando collector...")
        collector = RFBAuctionCollector(settings)

        # 5. Cria sync
        logger.info("Inicializando sincronizador...")
        sync = RFBAuctionSync(collector, storage)

        # 6. Roda sincronização
        fetch_lot_details = not args.no_lot_details
        logger.info("")
        logger.info("Iniciando sincronização...")
        logger.info(f"  Buscar detalhes de lotes: {'SIM' if fetch_lot_details else 'NÃO'}")
        logger.info("")

        result = sync.sync_all(fetch_lot_details=fetch_lot_details)

        # 7. Exibe resultados
        logger.info("")
        logger.info("=" * 80)
        logger.info("RESULTADOS DA SINCRONIZAÇÃO")
        logger.info("=" * 80)
        logger.info(f"Batch ID: {result.batch_id}")
        logger.info("")
        logger.info("Auctions:")
        logger.info(f"  Criados:     {result.auctions['created']}")
        logger.info(f"  Atualizados: {result.auctions['updated']}")
        logger.info(f"  Deletados:   {result.auctions['deleted']}")
        logger.info(f"  Erros:       {result.auctions['errors']}")
        logger.info("")
        logger.info("Lotes:")
        logger.info(f"  Criados:     {result.lots['created']}")
        logger.info(f"  Atualizados: {result.lots['updated']}")
        logger.info(f"  Deletados:   {result.lots['deleted']}")
        logger.info(f"  Erros:       {result.lots['errors']}")
        logger.info("")
        logger.info("Items:")
        logger.info(f"  Sincronizados: {result.items['synced']}")
        logger.info("")

        # 8. Tempo de execução
        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"Tempo de execução: {duration}")
        logger.info("=" * 80)

        # 9. Fecha conexões
        logger.info("Fechando conexões...")
        storage.closeall()

        logger.info("")
        logger.info("Sincronização concluída com sucesso!")
        return 0

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("Sincronização interrompida pelo usuário")
        return 130

    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("ERRO DURANTE SINCRONIZAÇÃO")
        logger.error("=" * 80)
        logger.error(f"Tipo: {type(e).__name__}")
        logger.error(f"Mensagem: {e}")
        logger.exception("Stack trace completo:")
        logger.error("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
