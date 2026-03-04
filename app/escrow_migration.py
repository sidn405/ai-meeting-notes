# escrow_migration.py
# Creates escrow_projects + escrow_milestones tables.
# Also patches the old escrow_transactions table (adds DEFAULT 0 to amount column)
# so it no longer breaks on insert if any old code still touches it.
#
# Run: python escrow_migration.py

import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
)

INDEX_NAME = "ix_escrow_projects_project_id"


def main():
    try:
        print("🔗 Connecting to database...")
        engine = create_engine(DATABASE_URL, future=True)

        # ── Phase 1: Fix old escrow_transactions table ────────────────────────
        print("⚙️  Phase 1: Patching escrow_transactions (old table)...")
        with engine.begin() as conn:
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text("SET statement_timeout = '60s'"))

            # Make the old `amount` column nullable so it no longer blocks inserts
            conn.execute(text("""
                ALTER TABLE IF EXISTS escrow_transactions
                    ALTER COLUMN amount DROP NOT NULL;
            """))
            print("   ✓ escrow_transactions.amount — NOT NULL constraint removed")

        # ── Phase 2: Create escrow_projects table ─────────────────────────────
        print("⚙️  Phase 2: Creating escrow_projects table...")
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS escrow_projects (
                    id                      SERIAL PRIMARY KEY,
                    project_id              INTEGER NOT NULL UNIQUE,
                    user_id                 INTEGER,
                    escrow_transaction_id   VARCHAR NOT NULL,
                    total_amount            FLOAT NOT NULL,
                    funding_url             VARCHAR,
                    status                  VARCHAR NOT NULL DEFAULT 'created',
                    raw_status              VARCHAR,
                    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at              TIMESTAMP,
                    funded_at               TIMESTAMP,
                    completed_at            TIMESTAMP
                );
            """))
            print("   ✓ escrow_projects created")

        # ── Phase 3: Create escrow_milestones table ───────────────────────────
        print("⚙️  Phase 3: Creating escrow_milestones table...")
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS escrow_milestones (
                    id                  SERIAL PRIMARY KEY,
                    escrow_project_id   INTEGER NOT NULL,
                    project_id          INTEGER NOT NULL,
                    milestone_number    INTEGER NOT NULL,
                    milestone_name      VARCHAR NOT NULL DEFAULT '',
                    amount              FLOAT NOT NULL,
                    percent             FLOAT NOT NULL DEFAULT 0.0,
                    escrow_item_id      VARCHAR,
                    status              VARCHAR NOT NULL DEFAULT 'pending',
                    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at          TIMESTAMP,
                    delivered_at        TIMESTAMP,
                    completed_at        TIMESTAMP
                );
            """))
            print("   ✓ escrow_milestones created")

        # ── Phase 4: Indexes (concurrently, outside transaction) ──────────────
        print("⚙️  Phase 4: Creating indexes...")
        indexes = [
            ("ix_escrow_projects_project_id",       "escrow_projects(project_id)"),
            ("ix_escrow_milestones_project_id",      "escrow_milestones(project_id)"),
            ("ix_escrow_milestones_ep_id",           "escrow_milestones(escrow_project_id)"),
            ("ix_escrow_milestones_item_id",         "escrow_milestones(escrow_item_id)"),
        ]
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for idx_name, idx_target in indexes:
                exists = conn.execute(text(
                    "SELECT 1 FROM pg_class WHERE relkind='i' AND relname=:n"
                ), {"n": idx_name}).fetchone()
                if exists:
                    print(f"   ✓ {idx_name} already exists, skipping")
                else:
                    conn.execute(text(
                        f"CREATE INDEX CONCURRENTLY {idx_name} ON {idx_target}"
                    ))
                    print(f"   ✓ {idx_name} created")

        # ── Phase 5: Verify ───────────────────────────────────────────────────
        print("\n⚙️  Phase 5: Verifying tables...")
        with engine.connect() as conn:
            for tbl in ("escrow_projects", "escrow_milestones"):
                rows = conn.execute(text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = :t ORDER BY ordinal_position
                """), {"t": tbl}).fetchall()
                print(f"\n   {tbl} ({len(rows)} columns):")
                for col, dtype in rows:
                    print(f"   • {col:<30} {dtype}")

        print("\n✅ Migration complete.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()