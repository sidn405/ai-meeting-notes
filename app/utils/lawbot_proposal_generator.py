"""
Proposal PDF Generator for 4D Gaming / LawBot 360
- Rich scope-of-work descriptions per milestone
- 30/50/20 payment schedule (all services)
- Correct next steps flow
- Professional layout with section dividers
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from datetime import datetime


# ── Milestone scope-of-work descriptions ─────────────────────────────────────

MILESTONE_SCOPE = {
    1: {
        "name": "Milestone 1: Discovery & Custom Flow Design",
        "percent": "30%",
        "deliverables": [
            "Kick-off call and requirements deep-dive session",
            "Custom conversation flow architecture tailored to your practice areas",
            "Intake questionnaire design (case type, urgency, contact info, documents needed)",
            "Bot personality, tone, and brand voice definition",
            "Integration map — CRM, scheduling, payment, and document systems",
            "UI/UX wireframes for chat widget placement and appearance",
            "Written technical specification document for client approval",
        ]
    },
    2: {
        "name": "Milestone 2: Bot Build & System Integrations",
        "percent": "50%",
        "deliverables": [
            "Full AI chatbot build with approved conversation flows",
            "24/7 automated client intake — qualifies leads, collects intake data",
            "Practice-area-specific question sets (PI, Family Law, Criminal, Immigration, etc.)",
            "Consultation scheduling integration (Calendly, Acuity, or built-in CRM)",
            "CRM / case management sync (Clio, MyCase, Salesforce, or custom webhook)",
            "Document capture — clients can upload files directly through the chat",
            "Payment processing integration (LawPay, Stripe, or PayPal)",
            "SMS / WhatsApp channel setup (if selected)",
            "Mobile app build (iOS & Android, if selected)",
            "Analytics dashboard setup (if selected)",
            "Staging environment delivery for client review and feedback",
        ]
    },
    3: {
        "name": "Milestone 3: Testing, Training & Launch",
        "percent": "20%",
        "deliverables": [
            "Full QA — functional testing across all conversation paths and edge cases",
            "Cross-device testing (desktop, mobile, tablet)",
            "Staff training session — how to manage leads, view intake data, update flows",
            "Admin portal walkthrough — adding/editing questions, viewing analytics",
            "Website embed code and installation support",
            "Go-live deployment to production",
            "30-day post-launch support window for bug fixes and minor adjustments",
            "Final project documentation and handoff package",
        ]
    },
}

GENERIC_MILESTONE_SCOPE = {
    1: {
        "name": "Milestone 1: Discovery & Planning",
        "percent": "30%",
        "deliverables": [
            "Requirements gathering and project scoping session",
            "Technical architecture and system design",
            "UI/UX wireframes and design mockups",
            "Written technical specification for client approval",
            "Project timeline and milestone plan",
        ]
    },
    2: {
        "name": "Milestone 2: Development & Integration",
        "percent": "50%",
        "deliverables": [
            "Core feature development per approved specification",
            "Third-party integrations and API connections",
            "Database design and backend infrastructure",
            "Staging environment delivery for client review",
            "Iteration based on client feedback",
        ]
    },
    3: {
        "name": "Milestone 3: Testing, Training & Launch",
        "percent": "20%",
        "deliverables": [
            "Full QA and cross-device/browser testing",
            "Staff training and admin portal walkthrough",
            "Production deployment",
            "30-day post-launch support for bug fixes",
            "Final documentation and project handoff",
        ]
    },
}


def create_proposal_pdf(filepath, data):
    """Generate a professional proposal PDF."""

    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []
    styles = getSampleStyleSheet()

    # ── Styles ────────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        fontSize=30, textColor=colors.HexColor("#3b82f6"),
        spaceAfter=4, alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER, spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#1e3a5f"),
        spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold",
        borderPad=0,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=15, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#374151"),
    )
    bullet_style = ParagraphStyle(
        "Bullet", parent=styles["Normal"],
        fontSize=10, leading=14,
        textColor=colors.HexColor("#374151"),
        leftIndent=12, spaceAfter=2,
    )
    milestone_title_style = ParagraphStyle(
        "MilestoneTitle", parent=styles["Normal"],
        fontSize=11, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1e3a5f"),
        spaceAfter=4, spaceBefore=2,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontSize=10, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#6b7280"),
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#1f2937"),
    )
    right_style = ParagraphStyle(
        "Right", parent=styles["Normal"],
        fontSize=10, alignment=TA_RIGHT,
        textColor=colors.HexColor("#1f2937"),
    )
    right_bold_style = ParagraphStyle(
        "RightBold", parent=styles["Normal"],
        fontSize=10, alignment=TA_RIGHT,
        fontName="Helvetica-Bold", textColor=colors.HexColor("#1f2937"),
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#9ca3af"),
        alignment=TA_CENTER,
    )

    def divider():
        return HRFlowable(width="100%", thickness=0.5,
                          color=colors.HexColor("#e5e7eb"), spaceAfter=8)

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("4D GAMING", title_style))
    story.append(Paragraph(
        f"Proposal #{data['proposal_number']} &nbsp;|&nbsp; "
        f"Date: {datetime.now().strftime('%B %d, %Y')}",
        subtitle_style,
    ))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=colors.HexColor("#3b82f6"), spaceAfter=14))

    # ── Client Information ────────────────────────────────────────────────────
    story.append(Paragraph("CLIENT INFORMATION", section_style))

    client_rows = [
        [Paragraph("Company:", label_style),  Paragraph(data["firm_name"], value_style)],
        [Paragraph("Contact:", label_style),  Paragraph(data["contact_name"], value_style)],
        [Paragraph("Email:", label_style),    Paragraph(data["contact_email"], value_style)],
    ]
    if data.get("contact_phone"):
        client_rows.append([
            Paragraph("Phone:", label_style),
            Paragraph(data["contact_phone"], value_style),
        ])

    client_tbl = Table(client_rows, colWidths=[1.3 * inch, 5.2 * inch])
    client_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(client_tbl)
    story.append(Spacer(1, 0.1 * inch))
    story.append(divider())

    # ── Services ──────────────────────────────────────────────────────────────
    service_names = {
        "chatbot":   "AI Chatbot Development",
        "mobile":    "Mobile App Development",
        "gamedev":   "Game Development Services",
        "web3":      "Web3 & Blockchain Solutions",
        "scraping":  "Web Scraping & Automation",
        "trading":   "Trading Bot Development",
        "website":   "Website Development",
        "lawbot360": "LawBot 360 — Complete AI Legal Intake System",
        "custom":    "Custom Development Project",
    }

    is_lawbot = any(
        "lawbot" in str(s).lower()
        for s in data.get("practice_areas", [])
    )
    scope_map = MILESTONE_SCOPE if is_lawbot else GENERIC_MILESTONE_SCOPE

    story.append(Paragraph("SCOPE OF WORK", section_style))

    if data.get("practice_areas"):
        for svc in data["practice_areas"]:
            story.append(Paragraph(
                f"• {service_names.get(svc, svc.title())}",
                bullet_style,
            ))
        story.append(Spacer(1, 0.08 * inch))

    if data.get("addons") and len(data["addons"]) > 0:
        story.append(Paragraph("Selected Add-Ons:", ParagraphStyle(
            "AddOnLabel", parent=styles["Normal"],
            fontSize=10, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#374151"), spaceAfter=3,
        )))
        for addon in data["addons"]:
            story.append(Paragraph(
                f"• {addon['label']} (+${addon['price']:,})",
                bullet_style,
            ))
        story.append(Spacer(1, 0.08 * inch))

    story.append(Spacer(1, 0.05 * inch))

    # Per-milestone scope blocks
    custom_phases = data.get("timeline_phases", [])
    print(f"PDF Generator - Received {len(custom_phases)} custom timeline phases")

    for ms_num in [1, 2, 3]:
        ms = scope_map[ms_num]

        # Override deliverables with custom phases if provided
        if custom_phases and ms_num <= len(custom_phases):
            cp = custom_phases[ms_num - 1]
            duration_label = cp.get("duration", "")
        else:
            duration_label = ""

        # Milestone header row
        pct_label = f"{ms['percent']} of total"
        header_data = [[
            Paragraph(ms["name"], milestone_title_style),
            Paragraph(pct_label, ParagraphStyle(
                "PctRight", parent=styles["Normal"],
                fontSize=10, alignment=TA_RIGHT,
                textColor=colors.HexColor("#3b82f6"),
                fontName="Helvetica-Bold",
            )),
        ]]
        header_tbl = Table(header_data, colWidths=[4.5 * inch, 2 * inch])
        header_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
        ]))

        deliverable_paras = [header_tbl]
        if duration_label:
            deliverable_paras.append(Paragraph(
                f"<i>Target: {duration_label}</i>",
                ParagraphStyle("DurLabel", parent=styles["Normal"],
                               fontSize=9, textColor=colors.HexColor("#6b7280"),
                               leftIndent=10, spaceBefore=4),
            ))

        for item in ms["deliverables"]:
            deliverable_paras.append(Paragraph(
                f"✓  {item}",
                ParagraphStyle("Deliv", parent=styles["Normal"],
                               fontSize=9.5, leading=14,
                               textColor=colors.HexColor("#374151"),
                               leftIndent=14, spaceAfter=1),
            ))

        deliverable_paras.append(Spacer(1, 0.1 * inch))
        story.append(KeepTogether(deliverable_paras))

    story.append(divider())

    # ── Investment & Payment Schedule ─────────────────────────────────────────
    story.append(Paragraph("INVESTMENT & PAYMENT SCHEDULE", section_style))

    total = float(data["total_price"])
    first = round(total * 0.30, 2)
    mid   = round(total * 0.50, 2)
    final = round(total - first - mid, 2)   # avoids rounding drift

    pay_data = [
        [
            Paragraph("<b>Milestone</b>", body_style),
            Paragraph("<b>Description</b>", body_style),
            Paragraph("<b>%</b>", ParagraphStyle("CtrBold", parent=styles["Normal"],
                                                  fontSize=10, fontName="Helvetica-Bold",
                                                  alignment=TA_CENTER)),
            Paragraph("<b>Amount</b>", right_bold_style),
        ],
        [
            Paragraph("Milestone 1", body_style),
            Paragraph("Fund Escrow upon signing — Discovery & Flow Design begins", body_style),
            Paragraph("30%", ParagraphStyle("Ctr", parent=styles["Normal"],
                                             fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"${first:,.2f}", right_style),
        ],
        [
            Paragraph("Milestone 2", body_style),
            Paragraph("Bot Build & System Integrations complete — staging delivered", body_style),
            Paragraph("50%", ParagraphStyle("Ctr2", parent=styles["Normal"],
                                             fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"${mid:,.2f}", right_style),
        ],
        [
            Paragraph("Milestone 3", body_style),
            Paragraph("Testing, Training & Launch — go-live approval", body_style),
            Paragraph("20%", ParagraphStyle("Ctr3", parent=styles["Normal"],
                                             fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"${final:,.2f}", right_style),
        ],
        [
            Paragraph("<b>TOTAL PROJECT COST</b>", ParagraphStyle(
                "TotalLabel", parent=styles["Normal"],
                fontSize=11, fontName="Helvetica-Bold",
                textColor=colors.HexColor("#1e3a5f"),
            )),
            Paragraph("", body_style),
            Paragraph("", body_style),
            Paragraph(f"<b>${total:,.2f}</b>", ParagraphStyle(
                "TotalAmt", parent=styles["Normal"],
                fontSize=11, fontName="Helvetica-Bold",
                alignment=TA_RIGHT, textColor=colors.HexColor("#3b82f6"),
            )),
        ],
    ]

    pay_tbl = Table(pay_data, colWidths=[1.1 * inch, 3.5 * inch, 0.6 * inch, 1.3 * inch])
    pay_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -2), [colors.HexColor("#f8fafc"), colors.white]),
        ("BACKGROUND",    (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
        ("LINEABOVE",     (0, -1), (-1, -1), 1.5, colors.HexColor("#3b82f6")),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("SPAN",          (0, -1), (2, -1)),
    ]))
    story.append(pay_tbl)

    story.append(Paragraph(
        "<i>All payments are processed securely through Escrow.com. "
        "Funds are held and released only upon your approval of each milestone delivery. "
        "Your money is protected at every stage.</i>",
        ParagraphStyle("EscrowNote", parent=styles["Normal"],
                       fontSize=9, textColor=colors.HexColor("#6b7280"),
                       spaceBefore=6, spaceAfter=4, leading=13),
    ))
    story.append(divider())

    # ── Maintenance ───────────────────────────────────────────────────────────
    maintenance_tier = data.get("maintenance_tier", "None")

    maintenance_info = {
        "Basic":        {"price": "$497/month",   "desc": "Server hosting & monitoring, security patches, bug fixes, email support (48-hr response), monthly performance reports, weekly database backups."},
        "Standard":     {"price": "$497/month",   "desc": "Server hosting & monitoring, security patches, bug fixes, email support, monthly reports."},
        "Professional": {"price": "$997/month",   "desc": "Everything in Basic plus priority phone support (24-hr response), monthly optimization & improvements, daily database backups, minor content updates (up to 2 hrs/month), quarterly strategy calls."},
        "Enterprise":   {"price": "$1,997/month", "desc": "Everything in Professional plus dedicated account manager, 4-hour emergency response, 24/7 phone support, weekly performance reviews, advanced analytics, up to 10 hrs/month development time, custom feature requests prioritized."},
    }

    story.append(Paragraph("ONGOING MAINTENANCE (OPTIONAL)", section_style))

    if maintenance_tier in maintenance_info:
        info = maintenance_info[maintenance_tier]
        maint_data = [[
            Paragraph(f"<b>{maintenance_tier} Maintenance Plan — {info['price']}</b>",
                      ParagraphStyle("MaintTitle", parent=styles["Normal"],
                                     fontSize=11, fontName="Helvetica-Bold",
                                     textColor=colors.HexColor("#1e3a5f"))),
        ], [
            Paragraph(info["desc"], body_style),
        ]]
        maint_tbl = Table(maint_data, colWidths=[6.5 * inch])
        maint_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
            ("BACKGROUND",    (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
        ]))
        story.append(maint_tbl)
    else:
        story.append(Paragraph(
            "No maintenance plan selected. The client will manage system maintenance, "
            "updates, and support independently after launch.",
            body_style,
        ))

    story.append(divider())

    # ── Next Steps ────────────────────────────────────────────────────────────
    story.append(Paragraph("NEXT STEPS", section_style))

    steps = [
        ("1", "Review and approve this proposal"),
        ("2", "Sign the agreement below"),
        ("3", "Fund escrow via the client portal — securely held by Escrow.com until delivery"),
        ("4", "Complete the client integration form (sent via email after escrow is funded)"),
        ("5", "4D Gaming begins development — kick-off call scheduled within 24 hours"),
    ]

    steps_data = [[
        Paragraph(f"<b>{n}</b>", ParagraphStyle(
            "StepNum", parent=styles["Normal"],
            fontSize=12, fontName="Helvetica-Bold",
            textColor=colors.white, alignment=TA_CENTER,
        )),
        Paragraph(text, body_style),
    ] for n, text in steps]

    steps_tbl = Table(steps_data, colWidths=[0.35 * inch, 6.15 * inch])
    steps_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#3b82f6")),
        ("BACKGROUND",    (1, 0), (1, -1), colors.white),
        ("ROWBACKGROUNDS",(1, 0), (1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (0, -1), 6),
        ("LEFTPADDING",   (1, 0), (1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
    ]))
    story.append(steps_tbl)
    story.append(Spacer(1, 0.3 * inch))
    story.append(divider())

    # ── Agreement & Signatures ────────────────────────────────────────────────
    story.append(Paragraph("AGREEMENT", section_style))
    story.append(Paragraph(
        "By signing below, both parties agree to the scope of work, timeline, payment schedule, "
        "and all terms outlined in this proposal. This document constitutes the binding agreement "
        "between the Client and 4D Gaming LLC. Work commences upon receipt of the Milestone 1 "
        "escrow funding.",
        body_style,
    ))
    story.append(Spacer(1, 0.35 * inch))

    sig_data = [
        [Paragraph("<b>CLIENT SIGNATURE</b>", body_style),
         Paragraph("<b>4D GAMING LLC SIGNATURE</b>", body_style)],
        ["", ""],
        [Paragraph("_" * 42, body_style), Paragraph("_" * 42, body_style)],
        [Paragraph(data["contact_name"], ParagraphStyle(
            "SigName", parent=styles["Normal"], fontSize=9,
            textColor=colors.HexColor("#6b7280"))),
         Paragraph("Authorized Representative", ParagraphStyle(
             "SigName2", parent=styles["Normal"], fontSize=9,
             textColor=colors.HexColor("#6b7280")))],
        ["", ""],
        [Paragraph("Date: _______________________", body_style),
         Paragraph("Date: _______________________", body_style)],
    ]

    sig_tbl = Table(sig_data, colWidths=[3.25 * inch, 3.25 * inch])
    sig_tbl.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 0.4 * inch))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(
        f"4D Gaming LLC  ·  legaltech@4dgaming.games  ·  4dgaming.games  ·  (504) 383-3692",
        footer_style,
    ))
    story.append(Paragraph(
        f"Proposal #{data['proposal_number']}  ·  Generated {datetime.now().strftime('%B %d, %Y')}  ·  "
        "Confidential — For Recipient Only",
        footer_style,
    ))

    doc.build(story)
    print(f"Proposal generated: {filepath}")


def create_invoice_pdf(filepath, data):
    pass