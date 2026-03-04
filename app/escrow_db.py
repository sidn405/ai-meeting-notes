# escrow_db.py
# Two tables:
#   EscrowProject     — one per project, the single Escrow.com transaction for full amount
#   EscrowMilestone   — one per milestone item within that transaction

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class EscrowProject(SQLModel, table=True):
    """
    One record per project.
    Represents the SINGLE Escrow.com transaction that holds the full project amount.
    Client funds this once; milestones are released individually as work is delivered.
    """
    __tablename__ = "escrow_projects"

    id: Optional[int] = Field(default=None, primary_key=True)

    project_id: int = Field(index=True, unique=True)
    user_id: Optional[int] = Field(default=None)       # project owner (buyer)

    # Escrow.com transaction ID (e.g. "13157737")
    escrow_transaction_id: str = Field(index=True)

    # Full project amount held in escrow
    total_amount: float

    # Link sent to client to fund the full transaction
    funding_url: Optional[str] = Field(default=None)

    # Overall transaction status mirrored from Escrow.com
    # Values: created | funded | in_progress | completed | cancelled | disputed
    status: str = Field(default="created")
    raw_status: Optional[str] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    funded_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)


class EscrowMilestone(SQLModel, table=True):
    """
    One record per milestone within the project's Escrow transaction.
    Each milestone is a separate 'item' in the Escrow.com transaction.
    Released independently when delivered and approved.
    """
    __tablename__ = "escrow_milestones"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Links
    escrow_project_id: int = Field(index=True)         # FK → escrow_projects.id
    project_id: int = Field(index=True)                # denormalized for easy querying

    # Milestone details
    milestone_number: int                               # 1, 2, 3...
    milestone_name: str = Field(default="")
    amount: float                                       # dollar amount for this milestone
    percent: float = Field(default=0.0)                 # e.g. 0.30 for 30%

    # Escrow.com item ID within the parent transaction
    escrow_item_id: Optional[str] = Field(default=None)

    # Per-milestone status
    # Values: pending | funded | delivered | inspection | completed | cancelled | disputed
    status: str = Field(default="pending")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)


# Backward-compatibility alias — main.py imports EscrowTransaction at line 29.
# Remove this once main.py is updated to import EscrowProject / EscrowMilestone.
EscrowTransaction = EscrowProject