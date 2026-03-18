"""
Proposal PDF Generator for 4D Gaming / LawBot 360
- Detailed milestone scope descriptions
- 30/50/20 payment schedule
- Correct next steps flow
- Professional layout
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from datetime import datetime
import os

# Signature image — stored alongside this file in app/utils/
_HERE = os.path.dirname(os.path.abspath(__file__))
SIGNATURE_PATH = os.path.join(_HERE, "signature.png")

MILESTONE_SCOPE = {
    1: {
        "name": "Discovery & Custom Flow Design",
        "pct": "30%",
        "deliverables": [
            "Kickoff meeting to review your firm's intake requirements, practice areas, and workflows",
            "Custom conversation flow design tailored to your specific legal practice areas",
            "Intake questionnaire mapping — case-specific questions for each practice area selected",
            "Review and approval of all conversation scripts and intake logic before build begins",
            "Technical architecture document outlining integrations (CRM, scheduling, payment processor)",
            "Brand style guide configuration — colors, logo placement, tone, and legal disclaimers",
        ]
    },
    2: {
        "name": "Bot Build & System Integrations",
        "pct": "50%",
        "deliverables": [
            "Full AI chatbot build with all approved conversation flows implemented",
            "24/7 automated client intake — captures leads, qualifies cases, collects contact info",
            "Case-specific intake forms for each selected practice area",
            "Consultation scheduling integration (Calendly, Google Calendar, or built-in CRM)",
            "CRM/case management integration (Clio, Salesforce, MyCase, or equivalent)",
            "Document capture capability — clients can upload supporting documents through the bot",
            "Payment processor integration for accepting retainer payments through the chat",
            "SMS/WhatsApp integration (if selected) for multi-channel client outreach",
            "Mobile app build for iOS & Android (if selected)",
            "Website embedding — widget installed and tested on your law firm website",
            "Internal quality assurance testing across all conversation paths",
        ]
    },
    3: {
        "name": "Testing, Training & Launch",
        "pct": "20%",
        "deliverables": [
            "End-to-end user acceptance testing with your team",
            "Training session — walkthrough of the admin dashboard, lead management, and reporting",
            "Staff training documentation and video walkthrough provided",
            "Final adjustments based on your feedback before go-live",
            "Production deployment — system goes live on your website and all selected channels",
            "30-day post-launch monitoring for any issues or adjustments needed",
            "Handoff of all credentials, documentation, and ongoing support contact information",
        ]
    }
}

MAINTENANCE_FEATURES = {
    'Basic': {
        'price': '$497/month',
        'features': [
            'Server hosting & monitoring (99.9% uptime SLA)',
            'Security patches & software updates',
            'Bug fixes and error resolution',
            'Email support (48-hour response)',
            'Monthly performance reports',
            'Database backups (weekly)',
        ]
    },
    'Professional': {
        'price': '$997/month',
        'features': [
            'Everything in Basic, PLUS:',
            'Priority support (24-hour response)',
            'Phone support during business hours',
            'Monthly conversation flow optimization',
            'Database backups (daily)',
            'Minor content updates (up to 2 hours/month)',
            'Quarterly strategy & performance calls',
        ]
    },
    'Enterprise': {
        'price': '$1,997/month',
        'features': [
            'Everything in Professional, PLUS:',
            'Dedicated account manager',
            'Priority emergency support (4-hour response)',
            '24/7 emergency phone line',
            'Weekly performance reviews',
            'Advanced analytics & conversion insights',
            'Up to 10 hours/month of development time',
            'Custom feature requests prioritized',
        ]
    },
}


def create_proposal_pdf(filepath, data):
    doc = SimpleDocTemplate(
        filepath, pagesize=letter,
        rightMargin=0.75*inch, leftMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch
    )
    story = []
    styles = getSampleStyleSheet()
    W = 7.0 * inch

    # Style factory
    def S(name, **kw):
        base = kw.pop('base', 'Normal')
        return ParagraphStyle(name, parent=styles[base], **kw)

    title_s   = S('T',  fontSize=26, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#1e3a5f'), alignment=TA_CENTER, spaceAfter=2)
    sub_s     = S('Su', fontSize=10, textColor=colors.HexColor('#6b7280'),
                  alignment=TA_CENTER, spaceAfter=4)
    hdr_s     = S('HD', fontSize=11, fontName='Helvetica-Bold', textColor=colors.white)
    body_s    = S('Bo', fontSize=10, leading=15, alignment=TA_JUSTIFY,
                  textColor=colors.HexColor('#1f2937'))
    bullet_s  = S('Bu', fontSize=10, leading=14, leftIndent=14,
                  textColor=colors.HexColor('#374151'))
    small_s   = S('Sm', fontSize=8,  textColor=colors.HexColor('#9ca3af'), alignment=TA_CENTER)

    def bar(text):
        t = Table([[Paragraph(text, hdr_s)]], colWidths=[W])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor('#1e3a5f')),
            ('TOPPADDING',    (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING',   (0,0), (-1,-1), 10),
        ]))
        return t

    def hr():
        return HRFlowable(width='100%', thickness=0.5,
                          color=colors.HexColor('#e5e7eb'), spaceAfter=5)

    total_price = float(data.get('total_price', 0))
    amounts = [round(total_price * 0.30, 2), round(total_price * 0.50, 2), 0]
    amounts[2] = round(total_price - amounts[0] - amounts[1], 2)
    phases = data.get('timeline_phases', [])

    # ── HEADER ────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 0.1*inch),
        Paragraph("4D GAMING", title_s),
        Paragraph("LawBot 360 — AI Client Intake System", sub_s),
        Paragraph(f"Proposal #{data['proposal_number']} &nbsp;|&nbsp; Date: {datetime.now().strftime('%B %d, %Y')}", sub_s),
        Spacer(1, 0.1*inch),
        HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1e3a5f'), spaceAfter=12),
    ]

    # ── CLIENT INFO ───────────────────────────────────────────────────────────
    story.append(bar("CLIENT INFORMATION"))
    story.append(Spacer(1, 0.1*inch))
    ci_rows = [
        ['Company / Firm:', data['firm_name']],
        ['Contact Name:', data['contact_name']],
        ['Email:', data['contact_email']],
    ]
    if data.get('contact_phone'):
        ci_rows.append(['Phone:', data['contact_phone']])
    ct = Table(ci_rows, colWidths=[1.6*inch, W - 1.6*inch])
    ct.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR', (1,0), (1,-1), colors.HexColor('#1f2937')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story += [ct, Spacer(1, 0.15*inch)]

    # ── ADD-ONS ───────────────────────────────────────────────────────────────
    addons = data.get('addons', [])
    if addons:
        story.append(bar("SELECTED ENHANCEMENTS & ADD-ONS"))
        story.append(Spacer(1, 0.08*inch))
        ar = [[
            Paragraph('<b>Feature</b>', body_s),
            Paragraph('<b>Price</b>', S('ARH', alignment=TA_RIGHT, fontName='Helvetica-Bold', fontSize=10))
        ]] + [[
            Paragraph(a['label'], body_s),
            Paragraph(f"${a['price']:,}", S(f'ARV{i}', alignment=TA_RIGHT, fontSize=10))
        ] for i, a in enumerate(addons)]
        at = Table(ar, colWidths=[W - 1.2*inch, 1.2*inch])
        at.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f4ff')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8), ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story += [at, Spacer(1, 0.15*inch)]

    # ── SCOPE OF WORK ─────────────────────────────────────────────────────────
    story.append(bar("SCOPE OF WORK — PROJECT MILESTONES"))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "This project is delivered across three milestones. Your full project balance is held securely "
        "by Escrow.com and released only upon your review and approval of each milestone. You are never "
        "charged for work that has not been delivered and approved. 4D Gaming absorbs all Escrow.com fees.",
        body_s
    ))
    story.append(Spacer(1, 0.12*inch))

    for i in range(1, 4):
        sc  = MILESTONE_SCOPE[i]
        amt = amounts[i-1]
        dur = phases[i-1].get('duration', f'Week {i}') if len(phases) >= i else f'Week {i}'

        head = Table([[
            Paragraph(f"Milestone {i}: {sc['name']}", S(f'MH{i}', fontSize=11, fontName='Helvetica-Bold', textColor=colors.white)),
            Paragraph(f"{sc['pct']}  —  ${amt:,.2f}", S(f'MA{i}', fontSize=11, fontName='Helvetica-Bold', textColor=colors.HexColor('#93c5fd'), alignment=TA_RIGHT))
        ]], colWidths=[W * 0.65, W * 0.35])
        head.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#1e40af')),
            ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ]))

        sub = Table([[Paragraph(f"Target Timeline: {dur}", S(f'DR{i}', fontSize=9, fontName='Helvetica-Oblique', textColor=colors.HexColor('#4b5563')))]], colWidths=[W])
        sub.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eff6ff')),
            ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))

        deliv = Table([[Paragraph(f"&#10003;  {d}", bullet_s)] for d in sc['deliverables']], colWidths=[W])
        deliv.setStyle(TableStyle([
            ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafafa')),
            ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ]))
        story.append(KeepTogether([head, sub, deliv, Spacer(1, 0.15*inch)]))

    # ── PAYMENT SCHEDULE ──────────────────────────────────────────────────────
    story.append(bar("INVESTMENT & PAYMENT SCHEDULE"))
    story.append(Spacer(1, 0.1*inch))

    pay = [
        [Paragraph('<b>Milestone</b>', body_s), Paragraph('<b>Description</b>', body_s),
         Paragraph('<b>%</b>', S('PH3', alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=10)),
         Paragraph('<b>Amount (USD)</b>', S('PH4', alignment=TA_RIGHT, fontName='Helvetica-Bold', fontSize=10))],
        [Paragraph('Milestone 1', body_s),
         Paragraph('Discovery &amp; Custom Flow Design — funded when escrow is initiated', body_s),
         Paragraph('30%', S('P13', alignment=TA_CENTER, fontSize=10)),
         Paragraph(f'${amounts[0]:,.2f}', S('P14', alignment=TA_RIGHT, fontSize=10))],
        [Paragraph('Milestone 2', body_s),
         Paragraph('Bot Build &amp; System Integrations — released upon your delivery approval', body_s),
         Paragraph('50%', S('P23', alignment=TA_CENTER, fontSize=10)),
         Paragraph(f'${amounts[1]:,.2f}', S('P24', alignment=TA_RIGHT, fontSize=10))],
        [Paragraph('Milestone 3', body_s),
         Paragraph('Testing, Training &amp; Launch — released upon your final approval', body_s),
         Paragraph('20%', S('P33', alignment=TA_CENTER, fontSize=10)),
         Paragraph(f'${amounts[2]:,.2f}', S('P34', alignment=TA_RIGHT, fontSize=10))],
        [Paragraph('<b>TOTAL</b>', S('PT1', fontName='Helvetica-Bold', fontSize=11)),
         Paragraph('', body_s),
         Paragraph('<b>100%</b>', S('PT3', alignment=TA_CENTER, fontName='Helvetica-Bold', fontSize=11)),
         Paragraph(f'<b>${total_price:,.2f}</b>', S('PT4', alignment=TA_RIGHT, fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1e3a5f')))],
    ]
    pt = Table(pay, colWidths=[1*inch, W - 3.2*inch, 0.7*inch, 1.5*inch])
    pt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#eff6ff')),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor('#1e3a5f')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#f9fafb')]),
        ('TOPPADDING', (0,0), (-1,-1), 7), ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 8), ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (2,0), (2,-1), 'CENTER'), ('ALIGN', (3,0), (3,-1), 'RIGHT'),
    ]))
    story += [pt, Spacer(1, 0.07*inch)]
    story.append(Paragraph(
        "All Escrow.com service fees are covered by 4D Gaming. You pay only the project total shown above.",
        S('EN', fontSize=9, fontName='Helvetica-Oblique', textColor=colors.HexColor('#6b7280'))
    ))
    story.append(Spacer(1, 0.15*inch))

    # ── MAINTENANCE ───────────────────────────────────────────────────────────
    mt = data.get('maintenance_tier', 'None')
    story.append(bar("ONGOING MAINTENANCE (OPTIONAL)"))
    story.append(Spacer(1, 0.1*inch))
    if not mt or mt in ('None', 'none'):
        story.append(Paragraph(
            "No maintenance plan selected. The client will manage system maintenance, updates, and support "
            "independently. A maintenance plan can be added at any time after launch.", body_s))
    elif mt in MAINTENANCE_FEATURES:
        info = MAINTENANCE_FEATURES[mt]
        story.append(Paragraph(f"<b>Selected Plan: {mt} — {info['price']}</b>",
                                S('MPH', fontSize=11, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1e3a5f'), spaceAfter=3)))
        story.append(Paragraph("Automatically billed monthly starting 30 days after project launch. Cancel anytime.",
                                S('MPN', fontSize=9, fontName='Helvetica-Oblique',
                                  textColor=colors.HexColor('#6b7280'), spaceAfter=6)))
        for f in info['features']:
            story.append(Paragraph(f"&#10003;  {f}", bullet_s))
    else:
        story.append(Paragraph(f"<b>Selected Plan: {mt}</b>", body_s))
    story.append(Spacer(1, 0.15*inch))

    # ── NEXT STEPS ────────────────────────────────────────────────────────────
    story.append(bar("NEXT STEPS"))
    story.append(Spacer(1, 0.1*inch))

    steps = [
        ("1", "Review & Approve This Proposal",
         "Read through the full scope of work, payment schedule, and terms outlined above. "
         "Contact us at legaltech@4dgaming.games with any questions before signing."),
        ("2", "Sign the Agreement",
         "Sign below to confirm you agree to the project scope, timeline, and payment terms. "
         "Your agreement is also recorded digitally when you check the agreement box in your client portal."),
        ("3", "Fund Escrow",
         "Click the 'Fund Project Escrow' button in your 4D Gaming client portal. Your full project "
         "balance is held securely by Escrow.com — 4D Gaming cannot access any funds until you review "
         "and approve each milestone delivery. You are fully protected at every stage."),
        ("4", "Complete the Client Integration Form",
         "You will receive an email with a link to our integration form immediately after funding escrow. "
         "This form captures everything needed to begin your build — practice areas, CRM details, "
         "branding assets, website URL, and any special requirements."),
        ("5", "Build Begins",
         "Our team reviews your integration form within 24 hours and your project kickoff is scheduled. "
         "Discovery & Custom Flow Design begins immediately, and you will be kept updated at every step."),
    ]

    for n, title, desc in steps:
        row = Table([[
            Paragraph(f'<b>{n}</b>', S(f'SN{n}', fontSize=15, fontName='Helvetica-Bold',
                                       textColor=colors.HexColor('#1e3a5f'), alignment=TA_CENTER)),
            [Paragraph(f'<b>{title}</b>', S(f'ST{n}', fontSize=10, fontName='Helvetica-Bold',
                                             textColor=colors.HexColor('#1e3a5f'), spaceAfter=3)),
             Paragraph(desc, body_s)]
        ]], colWidths=[0.45*inch, W - 0.45*inch])
        row.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story += [row, hr()]
    story.append(Spacer(1, 0.15*inch))

    # ── AGREEMENT ────────────────────────────────────────────────────────────
    story.append(bar("AGREEMENT & SIGNATURES"))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "By signing below, both parties agree to the scope of work, project timeline, payment schedule "
        "(30% / 50% / 20% milestone structure via Escrow.com), and all terms outlined in this proposal. "
        "Work will commence upon receipt of the escrow payment and completed client integration form. "
        "This agreement is legally binding upon signature by both parties.",
        body_s
    ))
    story.append(Spacer(1, 0.3*inch))

    sig = [
        [Paragraph('<b>CLIENT SIGNATURE</b>', S('SH1', fontSize=10, fontName='Helvetica-Bold',
                                                  textColor=colors.HexColor('#1e3a5f'))),
         Paragraph('<b>4D GAMING AUTHORIZED SIGNATURE</b>', S('SH2', fontSize=10, fontName='Helvetica-Bold',
                                                                textColor=colors.HexColor('#1e3a5f')))],
        [Paragraph(data['firm_name'], S('FN', fontSize=9, textColor=colors.HexColor('#6b7280'))),
         Paragraph('4D Gaming LLC', S('CO', fontSize=9, textColor=colors.HexColor('#6b7280')))],
        ['', RLImage(SIGNATURE_PATH, width=1.6*inch, height=0.6*inch) if os.path.exists(SIGNATURE_PATH) else ''],
        [Paragraph('Signature: ' + '_' * 36, body_s), Paragraph('', body_s)],
        ['', ''],
        [Paragraph('Printed Name: ' + '_' * 30, body_s),
         Paragraph('Printed Name: Sidney Muhammad', S('PN', fontSize=10, textColor=colors.HexColor('#374151')))],
        ['', ''],
        [Paragraph('Date: ' + '_' * 38, body_s),
         Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", S('DS', fontSize=10, textColor=colors.HexColor('#374151')))],
    ]
    st = Table(sig, colWidths=[W/2 - 0.1*inch, W/2 - 0.1*inch])
    st.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,0), 0.5, colors.HexColor('#1e3a5f')),
    ]))
    story += [st, Spacer(1, 0.35*inch)]

    # ── FOOTER ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e5e7eb'), spaceAfter=5))
    story.append(Paragraph(
        f"Proposal #{data['proposal_number']} &nbsp;|&nbsp; 4D Gaming LLC &nbsp;|&nbsp; "
        "legaltech@4dgaming.games &nbsp;|&nbsp; (504) 383-3692 &nbsp;|&nbsp; 4dgaming.games", small_s))
    story.append(Paragraph(
        "This proposal is valid for 30 days from the date of issue. All prices in USD. Escrow fees covered by 4D Gaming.",
        small_s))

    doc.build(story)
    print(f"Proposal generated: {filepath}")


def create_invoice_pdf(filepath, data):
    pass