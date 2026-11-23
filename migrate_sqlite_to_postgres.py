import os
import sqlite3
from datetime import datetime

from sqlalchemy import Boolean, DateTime, create_engine, text
from database import db
import models

SOURCE_DB = "instance/incidents.db"

EXPECTED_COUNTS = {
    "user": 4,
    "incident": 8,
    "incident_activity": 18,
}

TABLE_NAMES = ["user", "incident", "incident_activity"]

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is not configured.")

if not os.path.exists(SOURCE_DB):
    raise SystemExit(f"SQLite database not found: {SOURCE_DB}")

# Read the original SQLite database.
source = sqlite3.connect(SOURCE_DB)
source.row_factory = sqlite3.Row

if source.execute("PRAGMA foreign_key_check").fetchall():
    raise SystemExit("SQLite foreign-key violations found. Migration aborted.")

source_data = {}

for name in TABLE_NAMES:
    source_data[name] = [
        dict(row) for row in source.execute(f'SELECT * FROM "{name}"')
    ]

source.close()

# Confirm we are migrating the expected database.
for name, expected in EXPECTED_COUNTS.items():
    actual = len(source_data[name])
    if actual != expected:
        raise SystemExit(
            f"Unexpected {name} count: expected {expected}, found {actual}"
        )

engine = create_engine(DATABASE_URL)

# Create tables from the existing SQLAlchemy models.
db.metadata.create_all(engine)

with engine.begin() as connection:

    # Never overwrite existing PostgreSQL records.
    for name in TABLE_NAMES:
        count = connection.execute(
            text(f'SELECT COUNT(*) FROM "{name}"')
        ).scalar_one()

        if count != 0:
            raise RuntimeError(
                f"PostgreSQL table {name} is not empty. Migration aborted."
            )

    # Insert users first, then incidents, then activity records.
    for name in TABLE_NAMES:
        table = db.metadata.tables[name]
        records = source_data[name]

        for record in records:
            for column in table.columns:
                value = record.get(column.name)

                if value is None:
                    continue

                if isinstance(column.type, DateTime) and isinstance(value, str):
                    record[column.name] = datetime.fromisoformat(value)

                elif isinstance(column.type, Boolean):
                    record[column.name] = bool(value)

        if records:
            connection.execute(table.insert(), records)

    # Reset PostgreSQL auto-increment sequences.
    preparer = engine.dialect.identifier_preparer

    for name in TABLE_NAMES:
        quoted_name = preparer.quote(name)

        connection.execute(
            text(f"""
                SELECT setval(
                    pg_get_serial_sequence(:table_name, 'id'),
                    COALESCE(MAX(id), 1),
                    MAX(id) IS NOT NULL
                )
                FROM {quoted_name}
            """),
            {"table_name": name},
        )

    # Verify record counts before committing.
    for name in TABLE_NAMES:
        actual = connection.execute(
            text(f'SELECT COUNT(*) FROM "{name}"')
        ).scalar_one()

        expected = EXPECTED_COUNTS[name]

        if actual != expected:
            raise RuntimeError(
                f"Verification failed for {name}: {actual}/{expected}"
            )

engine.dispose()

print("\nMigration completed successfully!")

for name in TABLE_NAMES:
    print(f"{name}: {EXPECTED_COUNTS[name]} records migrated")

print("Total: 30 records")
