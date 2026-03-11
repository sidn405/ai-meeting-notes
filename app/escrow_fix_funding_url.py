# escrow_fix_funding_url.py
# Patches the stored funding_url for transaction 5581825 to the correct
# escrow-sandbox.com URL.
#
# Run: python escrow_fix_funding_url.py

import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "")

TRANSACTION_ID = "5581825"
CORRECT_URL = f"https://my.escrow-sandbox.com/myescrow/transaction.asp?tid={TRANSACTION_ID}"


def main():
    if not DATABASE_URL:
        print("❌ DATABASE_URL environment variable is not set")
        sys.exit(1)

    try:
        print("🔗 Connecting to database...")
        engine = create_engine(DATABASE_URL, future=True)

        with engine.begin() as conn:
            row = conn.execute(text("""
                SELECT id, escrow_transaction_id, funding_url
                FROM escrow_projects
                WHERE escrow_transaction_id = :txn_id
            """), {"txn_id": TRANSACTION_ID}).fetchone()

            if not row:
                print(f"❌ Transaction {TRANSACTION_ID} not found in escrow_projects table")
                sys.exit(1)

            print(f"   Found EscrowProject id={row[0]}")
            print(f"   Current funding_url : {row[2]}")
            print(f"   New     funding_url : {CORRECT_URL}")

            conn.execute(text("""
                UPDATE escrow_projects
                SET funding_url = :url,
                    updated_at  = NOW()
                WHERE escrow_transaction_id = :txn_id
            """), {"url": CORRECT_URL, "txn_id": TRANSACTION_ID})

            print(f"\n✅ funding_url patched for transaction {TRANSACTION_ID}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()