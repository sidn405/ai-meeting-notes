# escrow_db.py
# SQLModel table for tracking Escrow.com transactions per milestone.
# Mirrors the pattern used in portal_db.py — drop this in your /app directory.

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class EscrowTransaction(SQLModel, table=True):
    __tablename__ = "escrow_transactions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Link to project
    project_id: int = Field(index=True)

    # Milestone this transaction covers (1, 2, 3…)
    milestone_number: int

    # Escrow.com transaction ID returned from their API
    escrow_transaction_id: str = Field(index=True)

    # Dollar amount held in escrow
    amount: float

    # Percentage of total project this milestone represents (e.g. 0.30 for 30%)
    milestone_percent: float = Field(default=0.0)

    # Human-readable name (e.g. "Discovery & Conversation Flows")
    milestone_name: str = Field(default="")

    # Escrow.com transaction status
    # Possible values: created, awaiting_payment, funded, in_progress,
    #                  delivered, inspection, completed, cancelled, disputed
    escrow_status: str = Field(default="created")

    # URL for the client to fund this transaction on Escrow.com
    funding_url: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    funded_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)