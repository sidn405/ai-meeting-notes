# schema_patch.py
from sqlalchemy import create_engine, text

# ⬇️ Put your DB URL here (use postgresql+psycopg2, not postgres://)
DATABASE_URL = "postgresql://postgres:FXEPELqBVBGwxwPjrVEkLaktyWwGiQAI@shortline.proxy.rlwy.net:30381/railway"

# First, list all tables
LIST_TABLES = """
SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' 
ORDER BY table_name;
"""

# Create the license table if it doesn't exist
CREATE_SCHEMA = """
BEGIN;

-- === Create license table ===
CREATE TABLE IF NOT EXISTS license (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(64) UNIQUE NOT NULL,
    tier VARCHAR(32) NOT NULL DEFAULT 'free',
    email VARCHAR(255),
    device_id VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    iap_purchase_token VARCHAR(512),
    iap_store VARCHAR(20),
    iap_product_id VARCHAR(128),
    gumroad_order_id VARCHAR(128),
    activated_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS ix_license_key ON license (license_key);
CREATE INDEX IF NOT EXISTS ix_license_device_id ON license (device_id);
CREATE INDEX IF NOT EXISTS ix_license_email ON license (email);
CREATE INDEX IF NOT EXISTS ix_license_tier ON license (tier);

-- === Create license_usage table ===
CREATE TABLE IF NOT EXISTS license_usage (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR(64) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    meetings_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (license_key, year, month),
    FOREIGN KEY (license_key) REFERENCES license(license_key) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_license_usage_key ON license_usage (license_key);

COMMIT;
"""

VERIFY = """
SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' 
ORDER BY table_name;
"""

def main():
    engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    
    print("🔍 Checking existing tables...")
    with engine.begin() as conn:
        rows = conn.execute(text(LIST_TABLES)).fetchall()
        if rows:
            print("Existing tables:")
            for r in rows:
                print(" -", r[0])
        else:
            print("No tables found in public schema")
    
    print("\n📝 Creating license schema...")
    with engine.begin() as conn:
        conn.execute(text(CREATE_SCHEMA))
        print("✅ License schema created!")
        
        print("\n🔍 Verifying tables...")
        rows = conn.execute(text(VERIFY)).fetchall()
        for r in rows:
            print(" -", r[0])

if __name__ == "__main__":
    main()