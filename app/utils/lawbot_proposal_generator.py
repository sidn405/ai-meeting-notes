"""
Proposal PDF Generator — 4D Gaming / LawBot 360
- Dynamic scope using client's selected CRM, scheduling, practice areas, add-ons
- 30/50/20 payment schedule
- Signature sits ON the line (nested table approach)
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether, Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from datetime import datetime
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
SIGNATURE_PATH = os.path.join(_HERE, "signature.png")

# ── Static deliverables (milestone 1 & 3 don't vary much) ────────────────────

M1_BASE = [
    "Kickoff consultation to review the firm's intake requirements, practice areas, and workflows",
    "Custom conversation flow architecture tailored to the firm's specific legal practice areas",
    "Intake questionnaire mapping — case-specific questions for each selected practice area",
    "Review and written approval of all conversation scripts and intake logic before build begins",
    "Technical architecture document outlining all system integrations",
    "Brand configuration — colors, logo placement, tone of voice, and legal disclaimer language",
]

M3_BASE = [
    "End-to-end user acceptance testing with the client's team",
    "Admin dashboard training session — lead management, reporting, and conversation flow editing",
    "Staff training documentation and recorded video walkthrough",
    "Final adjustments based on client feedback before go-live",
    "Production deployment — system goes live on all selected channels",
    "30-day post-launch monitoring window for bug fixes and minor adjustments",
    "Handoff of all credentials, documentation, and ongoing support contact information",
]

MAINTENANCE_FEATURES = {
    "Basic": {
        "price": "$497/month",
        "features": [
            "Server hosting & monitoring (99.9% uptime SLA)",
            "Security patches & software updates",
            "Bug fixes and error resolution",
            "Email support (48-hour response)",
            "Monthly performance reports",
            "Database backups (weekly)",
        ],
    },
    "Professional": {
        "price": "$997/month",
        "features": [
            "Everything in Basic, PLUS:",
            "Priority support (24-hour response)",
            "Phone support during business hours",
            "Monthly conversation flow optimization",
            "Database backups (daily)",
            "Minor content updates (up to 2 hours/month)",
            "Quarterly strategy & performance calls",
        ],
    },
    "Enterprise": {
        "price": "$1,997/month",
        "features": [
            "Everything in Professional, PLUS:",
            "Dedicated account manager",
            "Priority emergency support (4-hour response)",
            "24/7 emergency phone line",
            "Weekly performance reviews",
            "Advanced analytics & conversion insights",
            "Up to 10 hours/month of development time",
            "Custom feature requests prioritized",
        ],
    },
}


def _build_m2_deliverables(data):
    """Build Milestone 2 deliverable list dynamically from project details."""
    crm       = (data.get("crm") or "").strip()
    sched     = (data.get("scheduling_system") or "").strip()
    payment   = (data.get("payment_processor") or "").strip()
    areas     = (data.get("practice_areas_text") or "").strip()
    addons    = [a.get("label", "").lower() for a in data.get("addons", [])]

    has_sms      = any("sms" in a or "whatsapp" in a for a in addons)
    has_mobile   = any("mobile" in a or "ios" in a or "android" in a for a in addons)
    has_voice    = any("voice" in a or "phone" in a or "twilio" in a for a in addons)
    has_analytics= any("analytics" in a for a in addons)
    has_multilang= any("language" in a for a in addons)
    has_multiloc = any("location" in a for a in addons)

    deliverables = [
        "Full AI chatbot build with all approved conversation flows implemented",
        "24/7 automated client intake — captures leads, qualifies cases, collects full contact info",
    ]

    # Practice-area-specific intake
    if areas:
        deliverables.append(
            f"Case-specific intake questionnaires configured for: {areas}"
        )
    else:
        deliverables.append(
            "Case-specific intake questionnaires for each selected practice area"
        )

    # Scheduling
    if sched:
        deliverables.append(
            f"Consultation scheduling integration with {sched}"
        )
    else:
        deliverables.append(
            "Consultation scheduling integration (Calendly, Google Calendar, or built-in CRM)"
        )

    # CRM
    if crm:
        deliverables.append(
            f"CRM integration with {crm} — leads and intake data synced automatically"
        )
    else:
        deliverables.append(
            "CRM/case management integration (Clio, Salesforce, MyCase, or equivalent)"
        )

    # Payment
    if payment:
        deliverables.append(
            f"Payment integration with {payment} — clients can pay retainers directly through the bot"
        )
    else:
        deliverables.append(
            "Payment processor integration — clients can submit retainer payments through the chat"
        )

    deliverables.append(
        "Document capture — clients can upload supporting files directly through the chat"
    )

    # Add-ons
    if has_voice:
        deliverables.append(
            "Voice/phone integration via Twilio — automated follow-up calls and voice intake enabled"
        )
    if has_sms:
        deliverables.append(
            "SMS & WhatsApp integration — multi-channel client outreach and follow-up"
        )
    if has_mobile:
        deliverables.append(
            "Native iOS & Android mobile app build and App Store/Play Store submission"
        )
    if has_analytics:
        deliverables.append(
            "Advanced analytics dashboard — lead volume, conversion rates, and intake performance"
        )
    if has_multilang:
        deliverables.append(
            "Multi-language support — bot configured to serve clients in selected languages"
        )
    if has_multiloc:
        deliverables.append(
            "Multi-location support — separate intake flows configured per office location"
        )

    deliverables += [
        "Website embedding — chat widget installed and tested on the law firm's website",
        "Internal QA testing across all conversation paths and edge cases",
    ]

    return deliverables


def create_proposal_pdf(filepath, data):
    doc = SimpleDocTemplate(
        filepath, pagesize=letter,
        rightMargin=0.75*inch, leftMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
    )
    story = []
    styles = getSampleStyleSheet()
    W = 7.0 * inch

    def S(name, **kw):
        base = kw.pop("base", "Normal")
        return ParagraphStyle(name, parent=styles[base], **kw)

    title_s  = S("T",  fontSize=26, fontName="Helvetica-Bold",
                 textColor=colors.HexColor("#1e3a5f"), alignment=TA_CENTER, spaceAfter=2)
    sub_s    = S("Su", fontSize=10, textColor=colors.HexColor("#6b7280"),
                 alignment=TA_CENTER, spaceAfter=4)
    hdr_s    = S("HD", fontSize=11, fontName="Helvetica-Bold", textColor=colors.white)
    body_s   = S("Bo", fontSize=10, leading=15, alignment=TA_JUSTIFY,
                 textColor=colors.HexColor("#1f2937"))
    bullet_s = S("Bu", fontSize=10, leading=14, leftIndent=14,
                 textColor=colors.HexColor("#374151"))
    small_s  = S("Sm", fontSize=8,  textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)

    def bar(text):
        t = Table([[Paragraph(text, hdr_s)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#1e3a5f")),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ]))
        return t

    def hr():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor("#e5e7eb"), spaceAfter=5)

    total_price = float(data.get("total_price", 0))
    amounts = [round(total_price * 0.30, 2), round(total_price * 0.50, 2), 0]
    amounts[2] = round(total_price - amounts[0] - amounts[1], 2)
    phases = data.get("timeline_phases", [])

    # ── HEADER ───────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 0.1*inch),
        Paragraph("4D GAMING", title_s),
        Paragraph("LawBot 360 — AI Client Intake System", sub_s),
        Paragraph(
            f"Proposal #{data['proposal_number']} &nbsp;|&nbsp; "
            f"Date: {datetime.now().strftime('%B %d, %Y')}",
            sub_s,
        ),
        Spacer(1, 0.1*inch),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f"), spaceAfter=12),
    ]

    # ── CLIENT INFO ──────────────────────────────────────────────────────────
    story.append(bar("CLIENT INFORMATION"))
    story.append(Spacer(1, 0.1*inch))
    ci_rows = [
        ["Company / Firm:", data["firm_name"]],
        ["Contact Name:",   data["contact_name"]],
        ["Email:",          data["contact_email"]],
    ]
    if data.get("contact_phone"):
        ci_rows.append(["Phone:", data["contact_phone"]])
    if data.get("website_url"):
        ci_rows.append(["Website:", data["website_url"]])
    if data.get("practice_areas_text"):
        ci_rows.append(["Practice Areas:", data["practice_areas_text"]])
    if data.get("crm"):
        ci_rows.append(["CRM / Case Mgmt:", data["crm"]])
    if data.get("scheduling_system"):
        ci_rows.append(["Scheduling:", data["scheduling_system"]])
    if data.get("payment_processor"):
        ci_rows.append(["Payment Processor:", data["payment_processor"]])

    ct = Table(ci_rows, colWidths=[1.7*inch, W - 1.7*inch])
    ct.setStyle(TableStyle([
        ("FONTNAME",      (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 10),
        ("TEXTCOLOR",     (0,0), (0,-1), colors.HexColor("#6b7280")),
        ("TEXTCOLOR",     (1,0), (1,-1), colors.HexColor("#1f2937")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story += [ct, Spacer(1, 0.15*inch)]

    # ── ADD-ONS ──────────────────────────────────────────────────────────────
    addons = data.get("addons", [])
    if addons:
        story.append(bar("SELECTED ENHANCEMENTS & ADD-ONS"))
        story.append(Spacer(1, 0.08*inch))
        ar = [[
            Paragraph("<b>Feature</b>", body_s),
            Paragraph("<b>Price</b>", S("ARH", alignment=TA_RIGHT,
                                         fontName="Helvetica-Bold", fontSize=10)),
        ]] + [[
            Paragraph(a["label"], body_s),
            Paragraph(f"${a['price']:,.0f}", S(f"ARV{i}", alignment=TA_RIGHT, fontSize=10)),
        ] for i, a in enumerate(addons)]
        at = Table(ar, colWidths=[W - 1.2*inch, 1.2*inch])
        at.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f0f4ff")),
            ("GRID",       (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("ALIGN",      (1,0), (1,-1), "RIGHT"),
        ]))
        story += [at, Spacer(1, 0.15*inch)]

    # ── SCOPE OF WORK ────────────────────────────────────────────────────────
    story.append(bar("SCOPE OF WORK — PROJECT MILESTONES"))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "This project is delivered across three milestones. The full project balance is held securely "
        "by Escrow.com and released only upon the Client's review and approval of each milestone. "
        "The Client is never charged for work that has not been delivered and approved. "
        "4D Gaming absorbs all Escrow.com service fees.",
        body_s,
    ))
    story.append(Spacer(1, 0.12*inch))

    # Milestone 1 — discovery items mention specific CRM/scheduling if provided
    m1_deliverables = list(M1_BASE)
    crm   = (data.get("crm") or "").strip()
    sched = (data.get("scheduling_system") or "").strip()
    if crm or sched:
        systems = " and ".join(filter(None, [crm, sched]))
        m1_deliverables[4] = (
            f"Technical architecture document outlining integrations with {systems} "
            "and all other required third-party systems"
        )

    milestone_deliverables = {
        1: m1_deliverables,
        2: _build_m2_deliverables(data),
        3: M3_BASE,
    }
    milestone_names = {
        1: "Discovery & Custom Flow Design",
        2: "Bot Build & System Integrations",
        3: "Testing, Training & Launch",
    }
    milestone_pcts = {1: "30%", 2: "50%", 3: "20%"}

    for i in range(1, 4):
        amt = amounts[i - 1]
        dur = phases[i - 1].get("duration", f"Week {i}") if len(phases) >= i else f"Week {i}"

        head = Table([[
            Paragraph(f"Milestone {i}: {milestone_names[i]}",
                      S(f"MH{i}", fontSize=11, fontName="Helvetica-Bold", textColor=colors.white)),
            Paragraph(f"{milestone_pcts[i]}  —  ${amt:,.2f}",
                      S(f"MA{i}", fontSize=11, fontName="Helvetica-Bold",
                        textColor=colors.HexColor("#93c5fd"), alignment=TA_RIGHT)),
        ]], colWidths=[W * 0.65, W * 0.35])
        head.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#1e40af")),
            ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING", (0,0), (-1,-1), 10), ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ]))

        sub = Table([[Paragraph(
            f"Target Timeline: {dur}",
            S(f"DR{i}", fontSize=9, fontName="Helvetica-Oblique",
              textColor=colors.HexColor("#4b5563")),
        )]], colWidths=[W])
        sub.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#eff6ff")),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
        ]))

        deliv = Table(
            [[Paragraph(f"&#10003;  {d}", bullet_s)] for d in milestone_deliverables[i]],
            colWidths=[W],
        )
        deliv.setStyle(TableStyle([
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 12),
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#fafafa")),
            ("LINEBELOW",     (0,-1), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ]))
        story.append(KeepTogether([head, sub, deliv, Spacer(1, 0.15*inch)]))

    # ── PAYMENT SCHEDULE ─────────────────────────────────────────────────────
    story.append(bar("INVESTMENT & PAYMENT SCHEDULE"))
    story.append(Spacer(1, 0.1*inch))

    pay = [
        [Paragraph("<b>Milestone</b>", body_s),
         Paragraph("<b>Description</b>", body_s),
         Paragraph("<b>%</b>",  S("PH3", alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=10)),
         Paragraph("<b>Amount (USD)</b>", S("PH4", alignment=TA_RIGHT, fontName="Helvetica-Bold", fontSize=10))],
        [Paragraph("Milestone 1", body_s),
         Paragraph("Discovery &amp; Custom Flow Design — funded when escrow is initiated", body_s),
         Paragraph("30%", S("P13", alignment=TA_CENTER, fontSize=10)),
         Paragraph(f"${amounts[0]:,.2f}", S("P14", alignment=TA_RIGHT, fontSize=10))],
        [Paragraph("Milestone 2", body_s),
         Paragraph("Bot Build &amp; System Integrations — released upon your delivery approval", body_s),
         Paragraph("50%", S("P23", alignment=TA_CENTER, fontSize=10)),
         Paragraph(f"${amounts[1]:,.2f}", S("P24", alignment=TA_RIGHT, fontSize=10))],
        [Paragraph("Milestone 3", body_s),
         Paragraph("Testing, Training &amp; Launch — released upon your final approval", body_s),
         Paragraph("20%", S("P33", alignment=TA_CENTER, fontSize=10)),
         Paragraph(f"${amounts[2]:,.2f}", S("P34", alignment=TA_RIGHT, fontSize=10))],
        [Paragraph("<b>TOTAL</b>", S("PT1", fontName="Helvetica-Bold", fontSize=11)),
         Paragraph("", body_s),
         Paragraph("<b>100%</b>", S("PT3", alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=11)),
         Paragraph(f"<b>${total_price:,.2f}</b>",
                   S("PT4", alignment=TA_RIGHT, fontName="Helvetica-Bold", fontSize=11,
                     textColor=colors.HexColor("#1e3a5f")))],
    ]
    pt = Table(pay, colWidths=[1*inch, W - 3.2*inch, 0.7*inch, 1.5*inch])
    pt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
        ("BACKGROUND",    (0,-1), (-1,-1), colors.HexColor("#eff6ff")),
        ("LINEABOVE",     (0,-1), (-1,-1), 1.5, colors.HexColor("#1e3a5f")),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.white, colors.HexColor("#f9fafb")]),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ALIGN",         (2,0), (2,-1), "CENTER"),
        ("ALIGN",         (3,0), (3,-1), "RIGHT"),
    ]))
    story += [pt, Spacer(1, 0.07*inch)]
    story.append(Paragraph(
        "All Escrow.com service fees are covered by 4D Gaming. "
        "The Client pays only the project total shown above.",
        S("EN", fontSize=9, fontName="Helvetica-Oblique",
          textColor=colors.HexColor("#6b7280")),
    ))
    story.append(Spacer(1, 0.15*inch))

    # ── MAINTENANCE ──────────────────────────────────────────────────────────
    mt = data.get("maintenance_tier", "None")
    story.append(bar("ONGOING MAINTENANCE (OPTIONAL)"))
    story.append(Spacer(1, 0.1*inch))
    if not mt or mt in ("None", "none"):
        story.append(Paragraph(
            "No maintenance plan selected. The Client will manage system maintenance, updates, and "
            "support independently. A maintenance plan may be added at any time after launch.",
            body_s,
        ))
    elif mt in MAINTENANCE_FEATURES:
        info = MAINTENANCE_FEATURES[mt]
        story.append(Paragraph(
            f"<b>Selected Plan: {mt} — {info['price']}</b>",
            S("MPH", fontSize=11, fontName="Helvetica-Bold",
              textColor=colors.HexColor("#1e3a5f"), spaceAfter=3),
        ))
        story.append(Paragraph(
            "Automatically billed monthly starting 30 days after project launch. Cancel anytime.",
            S("MPN", fontSize=9, fontName="Helvetica-Oblique",
              textColor=colors.HexColor("#6b7280"), spaceAfter=6),
        ))
        for f in info["features"]:
            story.append(Paragraph(f"&#10003;  {f}", bullet_s))
    else:
        story.append(Paragraph(f"<b>Selected Plan: {mt}</b>", body_s))
    story.append(Spacer(1, 0.15*inch))

    # ── NEXT STEPS ───────────────────────────────────────────────────────────
    story.append(bar("NEXT STEPS"))
    story.append(Spacer(1, 0.1*inch))

    steps = [
        ("1", "Review & Approve This Proposal",
         "Read through the full scope of work, payment schedule, and terms outlined above. "
         "Contact us at legaltech@4dgaming.games with any questions before signing."),
        ("2", "Sign the Agreement",
         "Sign below to confirm agreement to the project scope, timeline, and payment terms. "
         "Your agreement is also recorded electronically when you check the agreement box "
         "in your 4D Gaming client portal."),
        ("3", "Fund Escrow",
         "Click the 'Fund Project Escrow' button in your 4D Gaming client portal. "
         "Your full project balance is held securely by Escrow.com — 4D Gaming cannot access "
         "any funds until you review and approve each milestone delivery. "
         "You are fully protected at every stage."),
        ("4", "Complete the Client Integration Form",
         "You will receive an email with a link to our integration form immediately after "
         "funding escrow. This form captures everything needed to begin your build — practice "
         "areas, CRM details, branding assets, website URL, and any special requirements."),
        ("5", "Build Begins",
         "Our team reviews your integration form within 24 hours and your project kickoff is "
         "scheduled. Discovery & Custom Flow Design begins immediately, and you will be kept "
         "updated at every step."),
    ]

    for n, title, desc in steps:
        row = Table([[
            Paragraph(f"<b>{n}</b>",
                      S(f"SN{n}", fontSize=15, fontName="Helvetica-Bold",
                        textColor=colors.HexColor("#1e3a5f"), alignment=TA_CENTER)),
            [Paragraph(f"<b>{title}</b>",
                       S(f"ST{n}", fontSize=10, fontName="Helvetica-Bold",
                         textColor=colors.HexColor("#1e3a5f"), spaceAfter=3)),
             Paragraph(desc, body_s)],
        ]], colWidths=[0.45*inch, W - 0.45*inch])
        row.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story += [row, hr()]
    story.append(Spacer(1, 0.15*inch))

    # ── AGREEMENT & SIGNATURES ───────────────────────────────────────────────
    story.append(bar("AGREEMENT & SIGNATURES"))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "By signing below, both parties agree to the scope of work, project timeline, payment "
        "schedule (30% / 50% / 20% milestone structure via Escrow.com), and all terms outlined "
        "in this proposal. Work will commence upon receipt of the Milestone 1 escrow payment "
        "and completed client integration form. This agreement is legally binding upon execution "
        "by both parties.",
        body_s,
    ))
    story.append(Spacer(1, 0.3*inch))

    half = W / 2 - 0.1 * inch

    # ── Nested table: signature image sits in top cell, LINEBELOW = the line ──
    sig_img_cell = RLImage(SIGNATURE_PATH, width=1.7*inch, height=0.58*inch) \
        if os.path.exists(SIGNATURE_PATH) else Paragraph("", body_s)

    right_sig = Table([
        [sig_img_cell],          # image row — line drawn below this
    ], colWidths=[half])
    right_sig.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "BOTTOM"),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        # THE signature line — right beneath the image
        ("LINEBELOW",     (0,0), (-1,0),  0.8, colors.HexColor("#333333")),
    ]))

    left_sig = Table([
        [Paragraph("", body_s)],   # empty cell same height — line drawn below
    ], colWidths=[half])
    left_sig.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 30),   # height to match image cell
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("LINEBELOW",     (0,0), (-1,0),  0.8, colors.HexColor("#333333")),
    ]))

    sig_outer = Table([
        # Row 0: Headers
        [Paragraph("<b>CLIENT SIGNATURE</b>",
                   S("SH1", fontSize=10, fontName="Helvetica-Bold",
                     textColor=colors.HexColor("#1e3a5f"))),
         Paragraph("<b>4D GAMING LLC — AUTHORIZED SIGNATURE</b>",
                   S("SH2", fontSize=10, fontName="Helvetica-Bold",
                     textColor=colors.HexColor("#1e3a5f")))],
        # Row 1: Entity names
        [Paragraph(data["firm_name"],
                   S("FN", fontSize=9, textColor=colors.HexColor("#6b7280"))),
         Paragraph("4D Gaming LLC",
                   S("CO", fontSize=9, textColor=colors.HexColor("#6b7280")))],
        # Row 2: Signature cells (nested tables with line below)
        [left_sig, right_sig],
        # Row 3: Spacer
        [Paragraph("", body_s), Paragraph("", body_s)],
        # Row 4: Printed name
        [Paragraph("Printed Name: ________________________________", body_s),
         Paragraph("Printed Name: <b>Sidney Muhammad</b>", body_s)],
        # Row 5: Spacer
        [Paragraph("", body_s), Paragraph("", body_s)],
        # Row 6: Date
        [Paragraph("Date: ________________________________________", body_s),
         Paragraph(f"Date: <b>{datetime.now().strftime('%B %d, %Y')}</b>", body_s)],
    ], colWidths=[half, half])

    sig_outer.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "BOTTOM"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        # Header row underline
        ("LINEBELOW",     (0,0), (-1,0),  0.5, colors.HexColor("#1e3a5f")),
        ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#f8f8f8")),
    ]))

    story += [sig_outer, Spacer(1, 0.35*inch)]

    # ── FOOTER ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#e5e7eb"), spaceAfter=5))
    story.append(Paragraph(
        f"Proposal #{data['proposal_number']} &nbsp;|&nbsp; 4D Gaming LLC &nbsp;|&nbsp; "
        "legaltech@4dgaming.games &nbsp;|&nbsp; (504) 383-3692 &nbsp;|&nbsp; 4dgaming.games",
        small_s,
    ))
    story.append(Paragraph(
        "This proposal is valid for 30 days from the date of issue. "
        "All prices in USD. Escrow fees covered by 4D Gaming.",
        small_s,
    ))

    doc.build(story)
    print(f"Proposal generated: {filepath}")


def create_invoice_pdf(filepath, data):
    pass