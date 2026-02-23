#!/usr/bin/env python3
"""
Database schema update script.

Applies the main schema.sql file to the PostgreSQL database.
Safe to run multiple times (idempotent).

Usage:
    python scripts/update_db.py
    python scripts/update_db.py --dry-run
    python scripts/update_db.py --env config/.env.test
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from shared.infrastructure.postgres import PostgresConnectionPool, run_schema_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SCHEMA_FILE = ROOT_DIR / "shared" / "infrastructure" / "schema.sql"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Apply database schema updates"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print SQL without executing"
    )
    parser.add_argument(
        "--env",
        type=str,
        default="config/.env",
        help="Path to .env file (default: config/.env)"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Path to schema file (default: shared/infrastructure/schema.sql)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load environment
    env_path = ROOT_DIR / args.env
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded environment from {env_path}")
    else:
        logger.warning(f"Environment file not found: {env_path}")

    # Determine schema file
    schema_file = Path(args.schema) if args.schema else SCHEMA_FILE
    if not schema_file.exists():
        logger.error(f"Schema file not found: {schema_file}")
        sys.exit(1)

    logger.info(f"Schema file: {schema_file}")

    # Read schema
    sql_content = schema_file.read_text(encoding="utf-8")
    statement_count = sql_content.count(";")
    logger.info(f"Schema contains approximately {statement_count} statements")

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - SQL to be executed:")
        print("=" * 60)
        print(sql_content[:2000])
        if len(sql_content) > 2000:
            print(f"\n... ({len(sql_content) - 2000} more characters)")
        print("=" * 60)
        return

    # Apply schema
    pool = None
    try:
        pool = PostgresConnectionPool()
        logger.info("Connected to database")

        run_schema_file(pool, schema_file)
        logger.info("Schema applied successfully")

    except Exception as e:
        logger.error(f"Failed to apply schema: {e}")
        sys.exit(1)
    finally:
        if pool:
            pool.closeall()
            logger.info("Database connections closed")


if __name__ == "__main__":
    main()
