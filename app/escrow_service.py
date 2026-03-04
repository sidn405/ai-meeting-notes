"""
escrow_service.py — Escrow.com API v4 wrapper for 4D Gaming
Docs: https://www.escrow.com/api/documentation

Flow per milestone:
  1. 4D Gaming (seller) creates transaction → client (buyer) receives funding link
  2. Client funds escrow
  3. 4D Gaming completes milestone → marks as shipped/delivered
  4. Client has inspection period → approves → funds released to 4D Gaming
"""

import os
import httpx
from typing import Optional

ESCROW_API_BASE = "https://api.escrow.com/2017-09-01"
ESCROW_EMAIL = os.getenv("ESCROW_EMAIL")        # your escrow.com account email
ESCROW_API_KEY = os.getenv("ESCROW_API_KEY")    # from escrow.com dashboard


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _auth() -> tuple:
    """Returns (email, api_key) tuple for httpx BasicAuth."""
    if not ESCROW_EMAIL or not ESCROW_API_KEY:
        raise RuntimeError("ESCROW_EMAIL and ESCROW_API_KEY must be set in environment")
    return (ESCROW_EMAIL, ESCROW_API_KEY)


def _handle_response(resp: httpx.Response) -> dict:
    if resp.status_code in (200, 201):
        return resp.json()
    raise EscrowAPIError(
        status_code=resp.status_code,
        detail=resp.text,
    )


class EscrowAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Escrow API {status_code}: {detail}")


# ──────────────────────────────────────────────
# Core API calls
# ──────────────────────────────────────────────

def create_milestone_transaction(
    *,
    project_id: int,
    project_name: str,
    milestone_number: int,
    milestone_name: str,
    amount_usd: float,
    client_email: str,
    client_name: str,
    inspection_days: int = 5,
    notes: Optional[str] = None,
) -> dict:
    """
    Creates an Escrow.com transaction for a single milestone.

    Returns the full Escrow transaction object. Key fields to store:
      result["id"]                                → escrow_transaction_id
      get_funding_url(result)                     → URL to send the client
    """
    description = (
        f"{project_name} — Milestone {milestone_number}: {milestone_name}"
    )
    if notes:
        description += f"\n\nNotes: {notes}"

    payload = {
        "currency": "usd",
        "description": description,
        "items": [
            {
                "title": description,
                "description": description,
                "type": "general_merchandise",
                "inspection_period": inspection_days,
                "quantity": 1,
                "schedule": [
                    {
                        "amount": round(amount_usd, 2),
                        "payer_customer": client_email,
                        "beneficiary_customer": "me",  # 4D Gaming receives
                    }
                ],
            }
        ],
        "parties": [
            {
                "role": "buyer",
                "customer": client_email,
                "agreed": False,
            },
            {
                "role": "seller",
                "customer": "me",   # authenticated account = 4D Gaming
                "agreed": True,
            },
        ],
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{ESCROW_API_BASE}/transaction",
            json=payload,
            auth=_auth(),
        )
    return _handle_response(resp)


def get_transaction(escrow_transaction_id) -> dict:
    """Fetch full transaction details + current status."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{ESCROW_API_BASE}/transaction/{escrow_transaction_id}",
            auth=_auth(),
        )
    return _handle_response(resp)


def get_transaction_status(escrow_transaction_id) -> str:
    """
    Returns a simplified status string:
      'awaiting_payment'  — client has not funded yet
      'in_progress'       — funded, work underway
      'delivered'         — seller marked as delivered
      'inspection'        — client is reviewing
      'completed'         — funds released to 4D Gaming
      'cancelled'         — cancelled
      'disputed'          — in dispute
    """
    data = get_transaction(escrow_transaction_id)
    raw_status = data.get("status", "").lower()

    mapping = {
        "new": "awaiting_payment",
        "in_progress": "in_progress",
        "shipped": "delivered",
        "received": "inspection",
        "completed": "completed",
        "cancelled": "cancelled",
        "disputed": "disputed",
    }
    return mapping.get(raw_status, raw_status)


def mark_milestone_delivered(escrow_transaction_id, item_id) -> dict:
    """
    Seller action: mark work as delivered so inspection period starts.
    Call this from the admin portal when a milestone is complete.
    `item_id` comes from transaction["items"][0]["id"].
    """
    payload = {
        "action": "ship",
        "customer": "me",
        "line_items": [{"item_id": item_id}],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.patch(
            f"{ESCROW_API_BASE}/transaction/{escrow_transaction_id}/action",
            json=payload,
            auth=_auth(),
        )
    return _handle_response(resp)


def cancel_transaction(escrow_transaction_id) -> dict:
    """Cancel an unfunded/pending transaction."""
    payload = {
        "action": "reject",
        "customer": "me",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.patch(
            f"{ESCROW_API_BASE}/transaction/{escrow_transaction_id}/action",
            json=payload,
            auth=_auth(),
        )
    return _handle_response(resp)


# ──────────────────────────────────────────────
# Milestone schedule helpers
# ──────────────────────────────────────────────

DEFAULT_SCHEDULE = [0.30, 0.50, 0.20]   # 30% / 50% / 20%


def calculate_milestone_amounts(
    total_amount: float,
    schedule: Optional[list] = None,
    milestone_names: Optional[list] = None,
) -> list:
    """
    Returns list of milestone dicts for a project.

    Example (default):
      calculate_milestone_amounts(5000.00)
      → [
          {"number": 1, "percent": 0.30, "amount": 1500.00, "name": "Milestone 1"},
          {"number": 2, "percent": 0.50, "amount": 2500.00, "name": "Milestone 2"},
          {"number": 3, "percent": 0.20, "amount": 1000.00, "name": "Milestone 3"},
        ]

    Custom schedule:
      calculate_milestone_amounts(5000, [0.25, 0.50, 0.25])

    Custom names:
      calculate_milestone_amounts(5000, names=["Design", "Development", "Launch"])
    """
    pcts = schedule or DEFAULT_SCHEDULE
    if abs(sum(pcts) - 1.0) > 0.001:
        raise ValueError(f"Schedule must sum to 1.0, got {sum(pcts):.4f}")

    names = milestone_names or [f"Milestone {i}" for i in range(1, len(pcts) + 1)]

    milestones = []
    for i, pct in enumerate(pcts, start=1):
        milestones.append({
            "number": i,
            "percent": pct,
            "amount": round(total_amount * pct, 2),
            "name": names[i - 1] if i - 1 < len(names) else f"Milestone {i}",
        })
    return milestones


def get_funding_url(transaction_data: dict) -> Optional[str]:
    """Extract the client's payment/funding URL from a transaction response."""
    try:
        return transaction_data["payment_methods"]["escrow"]["url"]
    except (KeyError, TypeError):
        tid = transaction_data.get("id")
        return f"https://www.escrow.com/transactions/{tid}" if tid else None