# escrow_migration.py
# Adds missing columns to escrow_transactions table.
# Safe to run multiple times — all operations use IF NOT EXISTS / Python checks.
#
# Run locally:
#   python escrow_migration.py
#
# Run on Railway (one-off command):
#   railway run python escrow_migration.py

import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
)

NEW_COLUMNS = [
    ("user_id",            "INTEGER"),
    ("escrow_item_id",     "VARCHAR"),
    ("escrow_raw_status",  "VARCHAR"),
    ("amount_usd",         "FLOAT DEFAULT 0.0"),
    ("milestone_percent",  "FLOAT DEFAULT 0.0"),
    ("notes",              "TEXT"),
    ("updated_at",         "TIMESTAMP"),
    ("funded_at",          "TIMESTAMP"),
    ("delivered_at",       "TIMESTAMP"),
    ("completed_at",       "TIMESTAMP"),
    ("cancelled_at",       "TIMESTAMP"),
]

INDEX_NAME = "ix_escrow_transactions_user_id"


def main():
    try:
        print("🔗 Connecting to database...")
        engine = create_engine(DATABASE_URL, future=True)

        # ── Phase 1: Add missing columns (single transaction, low lock) ──────
        print("⚙️  Phase 1: Adding missing columns to escrow_transactions...")
        with engine.begin() as conn:
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text("SET statement_timeout = '60s'"))

            for col_name, col_type in NEW_COLUMNS:
                conn.execute(text(f"""
                    ALTER TABLE escrow_transactions
                        ADD COLUMN IF NOT EXISTS {col_name} {col_type};
                """))
                print(f"   ✓ {col_name} ({col_type})")

        # ── Phase 2: Create index concurrently ────────────────────────────────
        # IMPORTANT: CREATE INDEX CONCURRENTLY cannot run inside a DO $$ block.
        # Check existence in Python, then execute the statement directly.
        print(f"⚙️  Phase 2: CREATE INDEX CONCURRENTLY {INDEX_NAME} on user_id...")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            exists = conn.execute(text("""
                SELECT 1 FROM pg_class i
                JOIN pg_namespace n ON n.oid = i.relnamespace
                WHERE i.relkind = 'i' AND i.relname = :idx
            """), {"idx": INDEX_NAME}).fetchone()

            if exists:
                print(f"   ✓ Index {INDEX_NAME} already exists, skipping")
            else:
                conn.execute(text(
                    f"CREATE INDEX CONCURRENTLY {INDEX_NAME} "
                    f"ON escrow_transactions(user_id)"
                ))
                print(f"   ✓ Index {INDEX_NAME} created")

        # ── Phase 3: Verify ───────────────────────────────────────────────────
        print("⚙️  Phase 3: Verifying final column list...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'escrow_transactions'
                ORDER BY ordinal_position;
            """))
            rows = result.fetchall()
            print(f"\n   escrow_transactions has {len(rows)} columns:")
            for col, dtype in rows:
                print(f"   • {col:<30} {dtype}")

        print("\n✅ Migration complete. escrow_transactions is fully up to date.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("• If lock timeout: no active queries should be running against escrow_transactions.")
        print("• Bump lock_timeout to '15s' if needed — the script is fully idempotent.")
        sys.exit(1)


if __name__ == "__main__":
    main()