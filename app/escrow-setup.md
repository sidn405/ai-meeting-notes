# Escrow.com Integration Setup

## Files Added (Stripe NOT touched)
| File | Purpose |
|------|---------|
| escrow_service.py | Escrow.com API v4 wrapper |
| escrow_db.py | EscrowTransaction SQLModel table |
| escrow_routes.py | FastAPI router (admin + client endpoints) |
| client-portal-escrow-patch.js | Drop-in frontend JS |

---

## Step 1 — Add Railway ENV vars

ESCROW_EMAIL=your@email.com
ESCROW_API_KEY=from_escrow_dashboard
ESCROW_WEBHOOK_SECRET=optional_recommended

Get API key: https://www.escrow.com/api/keys

---

## Step 2 — Register in main.py

Add 3 lines (Stripe stays unchanged):

  # BEFORE SQLModel.metadata.create_all(engine):
  from app.escrow_db import EscrowTransaction

  # WITH the other app.include_router() lines:
  from app.escrow_routes import escrow_router
  app.include_router(escrow_router)

---

## Step 3 — Escrow.com Webhook

Dashboard > Webhooks > Add URL:
  https://4dgaming.games/api/escrow/webhook

---

## Step 4 — client-portal.html

Where you want milestone info to show:
  <div id="escrow-section" data-escrow-project-id="PROJ_ID"></div>

Before </body>:
  <script src="/static/client-portal-escrow-patch.js"></script>

Or dynamically call:
  loadEscrowForProject(projectId, "escrow-section");

---

## Step 5 — Admin Workflow

Setup milestones (30/50/20 default):
  POST /api/escrow/admin/setup-milestones
  { project_id: 42, total_amount: 5000.00 }

Custom schedule (25/50/25):
  POST /api/escrow/admin/setup-milestones
  { project_id: 42, total_amount: 5000.00,
    schedule: [0.25, 0.50, 0.25],
    milestone_names: [Design, Development, Launch] }

When milestone is done:
  POST /api/escrow/admin/deliver/{db_id}
  (starts 5-day client inspection, auto-releases if no dispute)

If webhook missed an event:
  POST /api/escrow/admin/sync/{db_id}

---

## Payment Flow

OLD (Stripe): Client pays BEFORE work -> money goes straight to you
NEW (Escrow): Client funds escrow -> you build -> you mark delivered
             -> client reviews (5 days) -> client approves -> YOU GET PAID

Both methods coexist. Subscriptions still use Stripe unchanged.

---

## All Endpoints

ADMIN (admin cookie required):
  POST /api/escrow/admin/setup-milestones  - Create all milestones at once
  POST /api/escrow/admin/milestone         - Create one milestone
  POST /api/escrow/admin/deliver/{id}      - Mark milestone delivered
  GET  /api/escrow/admin/project/{id}      - List project escrow records
  POST /api/escrow/admin/sync/{id}         - Force sync from Escrow.com API

CLIENT:
  GET /api/escrow/project/{project_id}     - View milestones + funding URLs

WEBHOOK:
  POST /api/escrow/webhook