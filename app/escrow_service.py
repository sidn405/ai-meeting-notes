# escrow_service.py
# Escrow.com API v4 wrapper for 4D Gaming.
#
# NEW FLOW (single-transaction model):
#   1. Admin calls create_project_transaction() → one Escrow.com txn for full project amount
#   2. All milestones are separate "items" in that one transaction
#   3. Client receives ONE funding link → funds the full amount
#   4. Per milestone: admin calls mark_item_delivered() → client approves → that slice releases
#
# Docs: https://www.escrow.com/api/documentation

import os
import httpx
from typing import Optional

_SANDBOX = os.getenv("ESCROW_SANDBOX", "false").lower() == "true"
ESCROW_API_BASE = (
    "https://api.escrow-sandbox.com/2017-09-01"
    if _SANDBOX else
    "https://api.escrow.com/2017-09-01"
)

if _SANDBOX:
    print("⚠️  Escrow running in SANDBOX mode — no real money will move")
ESCROW_EMAIL   = os.getenv("ESCROW_EMAIL")     # your escrow.com account email
ESCROW_API_KEY = os.getenv("ESCROW_API_KEY")   # from escrow.com dashboard


class EscrowAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Escrow API {status_code}: {detail}")


def _auth() -> tuple:
    if not ESCROW_EMAIL or not ESCROW_API_KEY:
        raise RuntimeError("ESCROW_EMAIL and ESCROW_API_KEY must be set in environment")
    return (ESCROW_EMAIL, ESCROW_API_KEY)


def _handle(resp: httpx.Response) -> dict:
    if resp.status_code in (200, 201):
        return resp.json()
    raise EscrowAPIError(resp.status_code, resp.text)


# ── Core: single transaction covering all milestones ─────────────────────────

def create_project_transaction(
    *,
    project_id: int,
    project_name: str,
    client_email: str,
    client_name: str,
    milestones: list,           # [{"number":1,"name":"...","amount":7500.00}, ...]
    inspection_days: int = 5,
) -> dict:
    """
    Create ONE Escrow.com transaction for the full project.
    Each milestone becomes a separate item in the transaction.
    Client funds the full amount in one payment.

    Returns the full Escrow transaction object. Key fields:
      result["id"]                 → escrow_transaction_id  (store this)
      result["items"][n]["id"]     → escrow_item_id per milestone
      get_funding_url(result)      → URL to send the client
    """
    inspection_seconds = inspection_days * 86400  # API requires seconds

    items = []
    for m in milestones:
        items.append({
            "title": f"Milestone {m['number']}: {m['name']}",
            "description": (
                f"Project: {project_name}\n"
                f"Milestone {m['number']}: {m['name']}\n"
                f"Delivered by 4D Gaming (Project ID: {project_id})"
            ),
            "type": "general_merchandise",
            "inspection_period": inspection_seconds,
            "quantity": 1,
            "schedule": [
                {
                    "amount": round(float(m["amount"]), 2),
                    "payer_customer": client_email,
                    "beneficiary_customer": "me",   # authenticated seller = 4D Gaming
                }
            ],
        })

    payload = {
        "currency": "usd",
        "description": f"4D Gaming – {project_name} (Project #{project_id})",
        "items": items,
        "parties": [
            {"role": "buyer",  "customer": client_email, "agreed": False, "fee_payer": "50/50"},
            {"role": "seller", "customer": "me",         "agreed": True,  "fee_payer": "50/50"},
        ],
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{ESCROW_API_BASE}/transaction",
            json=payload,
            auth=_auth(),
        )
    return _handle(resp)


def get_transaction(escrow_transaction_id: str) -> dict:
    """Fetch full transaction + current status from Escrow.com."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{ESCROW_API_BASE}/transaction/{escrow_transaction_id}",
            auth=_auth(),
        )
    return _handle(resp)


def mark_item_delivered(escrow_transaction_id: str, item_id: str) -> dict:
    """
    Mark a single milestone item as delivered → starts client inspection period.
    Call this from admin portal when a milestone is complete.
    After inspection_days with no dispute, funds auto-release.
    """
    payload = {
        "action": "ship",
        "customer": "me",
        "line_items": [{"item_id": int(item_id)}],
    }
    with httpx.Client(timeout=30) as client:
        resp = client.patch(
            f"{ESCROW_API_BASE}/transaction/{escrow_transaction_id}/action",
            json=payload,
            auth=_auth(),
        )
    return _handle(resp)


# Keep old name as alias so existing escrow_routes.py admin routes don't break
mark_milestone_delivered = mark_item_delivered


def cancel_transaction(escrow_transaction_id: str) -> dict:
    """Cancel an unfunded transaction."""
    payload = {"action": "reject", "customer": "me"}
    with httpx.Client(timeout=30) as client:
        resp = client.patch(
            f"{ESCROW_API_BASE}/transaction/{escrow_transaction_id}/action",
            json=payload,
            auth=_auth(),
        )
    return _handle(resp)


# ── Schedule helpers ──────────────────────────────────────────────────────────

DEFAULT_SCHEDULE = [0.30, 0.50, 0.20]   # 30% / 50% / 20%


def calculate_milestone_amounts(
    total_amount: float,
    schedule: Optional[list] = None,
    milestone_names: Optional[list] = None,
) -> list:
    """
    Returns list of milestone dicts ready to pass to create_project_transaction().

    Default: 30% / 50% / 20%
    Custom:  calculate_milestone_amounts(5000, [0.25, 0.25, 0.50])
    """
    pcts = schedule or DEFAULT_SCHEDULE
    if abs(sum(pcts) - 1.0) > 0.001:
        raise ValueError(f"Schedule must sum to 1.0, got {sum(pcts):.4f}")

    names = milestone_names or [f"Milestone {i}" for i in range(1, len(pcts) + 1)]

    milestones = []
    running = 0.0
    for i, pct in enumerate(pcts, start=1):
        if i < len(pcts):
            amount = round(total_amount * pct, 2)
        else:
            # Last milestone gets the remainder to avoid rounding drift
            amount = round(total_amount - running, 2)
        running += amount
        milestones.append({
            "number": i,
            "percent": pct,
            "amount": amount,
            "name": names[i - 1] if i - 1 < len(names) else f"Milestone {i}",
        })
    return milestones


def get_funding_url(transaction_data: dict) -> Optional[str]:
    """Extract client funding URL from Escrow.com transaction response."""
    try:
        return transaction_data["payment_methods"]["escrow"]["url"]
    except (KeyError, TypeError):
        tid = transaction_data.get("id")
        return f"https://www.escrow.com/transactions/{tid}" if tid else None


def get_item_ids(transaction_data: dict) -> dict:
    """
    Returns {milestone_number: item_id} by matching item titles.
    Escrow.com returns items in order, so index = milestone_number - 1.
    """
    items = transaction_data.get("items", [])
    result = {}
    for idx, item in enumerate(items):
        result[idx + 1] = str(item.get("id", ""))
    return result


def map_status(raw: str) -> str:
    """Normalize Escrow.com raw status to our internal values."""
    return {
        "new":         "created",
        "in_progress": "funded",
        "shipped":     "delivered",
        "received":    "inspection",
        "completed":   "completed",
        "cancelled":   "cancelled",
        "disputed":    "disputed",
    }.get(raw.lower() if raw else "", raw.lower() if raw else "unknown")