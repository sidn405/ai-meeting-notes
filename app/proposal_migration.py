# proposal_migration.py
# Adds proposal PDF + agreement columns to the project table.
# Run: python proposal_migration.py

import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "")


def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        sys.exit(1)

    engine = create_engine(DATABASE_URL, future=True)
    print("🔗 Connecting to database...")

    with engine.begin() as conn:
        conn.execute(text("SET lock_timeout = '5s'"))
        conn.execute(text("SET statement_timeout = '60s'"))

        cols = [
            ("proposal_pdf_key",   "VARCHAR"),
            ("proposal_pdf_url",   "VARCHAR"),
            ("proposal_agreed",    "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("proposal_agreed_at", "TIMESTAMP"),
        ]

        for col_name, col_type in cols:
            exists = conn.execute(text("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'project' AND column_name = :col
            """), {"col": col_name}).fetchone()

            if exists:
                print(f"   ✓ project.{col_name} already exists — skipped")
            else:
                conn.execute(text(f"ALTER TABLE project ADD COLUMN {col_name} {col_type}"))
                print(f"   ✓ project.{col_name} added")

    print("\n✅ Proposal migration complete.")


if __name__ == "__main__":
    main()