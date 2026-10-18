"""Datenbankverbindung und Migrationen (PRD Anhang C, migrations/)."""

from pathlib import Path

import psycopg

MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""


def connect(database_url: str, *, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(database_url, autocommit=autocommit)


def migration_files(migrations_dir: Path) -> list[Path]:
    """Migrationen in Nummernfolge: 0001_init.sql, 0002_….sql, …"""
    return sorted(p for p in migrations_dir.glob("*.sql") if p.name[:4].isdigit())


def migrate(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    """Wendet noch nicht angewendete Migrationen an, jede in einer eigenen Transaktion.

    Gibt die Versionen zurück, die in diesem Aufruf angewendet wurden.
    """
    with conn.transaction():
        conn.execute(MIGRATIONS_TABLE)
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    done: list[str] = []
    for path in migration_files(migrations_dir):
        version = path.stem
        if version in applied:
            continue
        with conn.transaction():
            # Ohne Parameter nutzt psycopg das einfache Protokoll, mehrere Anweisungen sind erlaubt.
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        done.append(version)
    return done
