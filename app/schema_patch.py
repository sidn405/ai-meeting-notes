# schema_patch.py
from sqlalchemy import create_engine, text

# ⬇️ Put your DB URL here (use postgresql+psycopg2, not postgres://)
DATABASE_URL = "postgresql://postgres:FXEPELqBVBGwxwPjrVEkLaktyWwGiQAI@shortline.proxy.rlwy.net:30381/railway"

SQL = """
BEGIN;

-- === meeting table: add columns if missing ===
ALTER TABLE meeting
    ADD COLUMN IF NOT EXISTS license_key VARCHAR(64),
    ADD COLUMN IF NOT EXISTS tier VARCHAR(32),
    ADD COLUMN IF NOT EXISTS iap_purchase_token VARCHAR(512),
    ADD COLUMN IF NOT EXISTS iap_store VARCHAR(20),
    ADD COLUMN IF NOT EXISTS iap_product_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS gumroad_order_id VARCHAR(128);


-- index on license_key if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'i'
          AND c.relname = 'ix_meeting_license_key'
          AND n.nspname = 'public'
    ) THEN
        CREATE INDEX ix_meeting_license_key ON meeting (license_key);
    END IF;
END$$;

-- === license_usage: enforce one row per (license_key, year, month) ===
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_license_usage_key_year_month'
    ) THEN
        ALTER TABLE license_usage
        ADD CONSTRAINT uq_license_usage_key_year_month
        UNIQUE (license_key, year, month);
    END IF;
END$$;

COMMIT;
"""

VERIFY = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'meeting'
ORDER BY ordinal_position;
"""

def main():
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.begin() as conn:
        conn.execute(text(SQL))
        print("✅ Manual schema patch applied.")
        print("🔎 Verifying meeting columns...")
        rows = conn.execute(text(VERIFY)).fetchall()
        for r in rows:
            print(" -", r[0], r[1])

if __name__ == "__main__":
    main()
