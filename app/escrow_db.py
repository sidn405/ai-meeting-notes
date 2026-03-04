# escrow_db.py
# SQLModel table for Escrow.com milestone transactions.
# Place in /app/app/ alongside portal_db.py

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class EscrowTransaction(SQLModel, table=True):
    __tablename__ = "escrow_transactions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Links
    project_id: int = Field(index=True)
    user_id: Optional[int] = Field(default=None, index=True)  # project owner

    # Milestone info
    milestone_number: int
    milestone_name: str = Field(default="")
    milestone_percent: float = Field(default=0.0)  # e.g. 0.30 for 30%

    # Amounts
    amount_usd: float = Field(default=0.0)

    # Escrow.com identifiers
    escrow_transaction_id: Optional[str] = Field(default=None, index=True)
    escrow_item_id: Optional[str] = Field(default=None)  # item ID within the transaction

    # Payment link sent to client
    funding_url: Optional[str] = Field(default=None)

    # Simplified internal status
    # Values: created | awaiting_payment | funded | in_progress |
    #         delivered | inspection | completed | cancelled | disputed
    escrow_status: str = Field(default="created")

    # Raw status string from Escrow.com API (for debugging)
    escrow_raw_status: Optional[str] = Field(default=None)

    # Optional admin notes
    notes: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    funded_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)