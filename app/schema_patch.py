# schema_patch.py
from sqlalchemy import create_engine, text
import sys

DATABASE_URL = "postgresql://postgres:FXEPELqBVBGwxwPjrVEkLaktyWwGiQAI@shortline.proxy.rlwy.net:30381/railway"

SQL = """
BEGIN;

-- Add missing columns to license_usage if they don't exist
ALTER TABLE license_usage
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Add missing columns to meeting if they don't exist
ALTER TABLE meeting
    ADD COLUMN IF NOT EXISTS email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS device_id VARCHAR(255);

COMMIT;
"""

def main():
    try:
        print("🔗 Connecting to database...")
        engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
        
        print("📝 Applying schema patch...")
        with engine.connect() as conn:
            conn.execute(text(SQL))
        
        print("✅ Schema patch applied successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()