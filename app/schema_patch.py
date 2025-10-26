# schema_patch.py
import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:FXEPELqBVBGwxwPjrVEkLaktyWwGiQAI@shortline.proxy.rlwy.net:30381/railway",
)

FK_NAME = "meeting_license_id_fkey"
INDEX_NAME = "ix_meeting_license_id"

def main():
    try:
        print("🔗 Connecting to database...")
        engine = create_engine(DATABASE_URL, future=True)

        # ---- PHASE 1: add column + FK (NOT VALID) with short locks ----
        print("⚙️  Phase 1: ALTER meeting (single txn, low lock)…")
        with engine.begin() as conn:
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text("SET statement_timeout = '60s'"))

            # 1) Add column if missing
            conn.execute(text("""
                ALTER TABLE IF EXISTS meeting
                    ADD COLUMN IF NOT EXISTS license_id INTEGER;
            """))

            # 2) Add FK NOT VALID if it doesn't exist yet
            conn.execute(text(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = '{FK_NAME}'
                    ) THEN
                        ALTER TABLE meeting
                            ADD CONSTRAINT {FK_NAME}
                            FOREIGN KEY (license_id) REFERENCES license(id) NOT VALID;
                    END IF;
                END
                $$;
            """))

        # ---- PHASE 2: index concurrently (must be outside a txn) ----
        print("⚙️  Phase 2: CREATE INDEX CONCURRENTLY on meeting.license_id…")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_class i
                        JOIN pg_namespace n ON n.oid = i.relnamespace
                        WHERE i.relkind = 'i'
                          AND i.relname = '{INDEX_NAME}'
                    ) THEN
                        EXECUTE 'CREATE INDEX CONCURRENTLY {INDEX_NAME} ON meeting(license_id)';
                    END IF;
                END
                $$;
            """))

        # ---- PHASE 3: validate FK (short lock; separate txn) ----
        print("⚙️  Phase 3: VALIDATE FOREIGN KEY…")
        with engine.begin() as conn:
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text("SET statement_timeout = '5min'"))
            conn.execute(text(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = '{FK_NAME}' AND NOT convalidated
                    ) THEN
                        ALTER TABLE meeting VALIDATE CONSTRAINT {FK_NAME};
                    END IF;
                END
                $$;
            """))

        print("✅ Done. `meeting.license_id` added, indexed, and FK validated.")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nIf this still hits a lock timeout:")
        print("• Make sure your app is not writing to `meeting` during Phase 1/3.")
        print("• Temporarily bump: lock_timeout='15s', statement_timeout='5min'.")
        print("• As last resort: stop app traffic briefly and rerun (script is idempotent).")
        sys.exit(1)

if __name__ == "__main__":
    main()
