# lawbot_proposal_generator.py - LawBot 360 Proposal & Invoice Generator

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime, timedelta
import os

def create_proposal_pdf(output_path, proposal_data):
    """
    Generate a professional LawBot 360 proposal PDF
    
    proposal_data = {
        'proposal_number': 'LB360-2024-001',
        'firm_name': 'Smith & Associates',
        'contact_name': 'John Smith',
        'contact_email': 'john@smithlaw.com',
        'contact_phone': '555-1234',
        'practice_areas': ['Personal Injury', 'Family Law'],
        'current_intake_method': 'Manual phone screening',
        'pain_points': ['Missing after-hours leads', 'Long intake times'],
        'monthly_inquiries': '50-100',
        'integration_needs': ['Clio', 'Salesforce'],
        'custom_features': [],
        'total_price': 25000,
        'maintenance_tier': 'Standard',  # Basic, Standard, Premium
        'timeline_weeks': 6,
    }
    """
    
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        spaceBefore=18,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#374151'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )
    
    # Header
    story.append(Paragraph("LAWBOT 360", title_style))
    story.append(Paragraph("AI-Powered Legal Intake System", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Proposal details
    today = datetime.now().strftime("%B %d, %Y")
    valid_until = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")
    
    proposal_info = [
        ['Proposal Number:', proposal_data.get('proposal_number', 'LB360-DRAFT')],
        ['Date:', today],
        ['Valid Until:', valid_until],
        ['Prepared For:', proposal_data['firm_name']],
    ]
    
    t = Table(proposal_info, colWidths=[2*inch, 3.5*inch])
    t.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#6b7280')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*inch))
    
    # Executive Summary
    story.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
    exec_summary = f"""
    This proposal outlines a custom LawBot 360 implementation for {proposal_data['firm_name']}.
    Based on our consultation, your firm is currently handling {proposal_data.get('monthly_inquiries', 'multiple')} 
    monthly inquiries across {', '.join(proposal_data.get('practice_areas', ['various practice areas']))}.
    LawBot 360 will automate your intake process, qualify leads 24/7, and integrate seamlessly with your existing systems.
    """
    story.append(Paragraph(exec_summary, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Identified Challenges
    if proposal_data.get('pain_points'):
        story.append(Paragraph("IDENTIFIED CHALLENGES", heading_style))
        for pain in proposal_data['pain_points']:
            story.append(Paragraph(f"• {pain}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    # Solution Overview
    story.append(Paragraph("SOLUTION OVERVIEW", heading_style))
    solution = """
    LawBot 360 is a fully customized AI-driven intake and engagement platform designed specifically for law firms.
    Our system will:
    """
    story.append(Paragraph(solution, styles['Normal']))
    
    benefits = [
        "Capture leads 24/7, including after-hours and weekends",
        "Pre-qualify potential clients before staff involvement",
        "Automate appointment scheduling with your calendar",
        "Collect case details and documents upfront",
        "Integrate with your existing CRM and case management systems",
        "Provide instant follow-up and confirmation emails",
        "Generate detailed intake reports for attorney review",
    ]
    
    for benefit in benefits:
        story.append(Paragraph(f"• {benefit}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Scope of Work
    story.append(Paragraph("SCOPE OF WORK", heading_style))
    
    scope_items = [
        ("Discovery & Planning", [
            "Practice area analysis and conversation flow design",
            "Custom intake questionnaires for each practice area",
            "Integration requirements assessment",
            "Branding and tone customization"
        ]),
        ("Development & Configuration", [
            "AI conversation engine setup",
            "Website chatbot integration",
            "Document upload system configuration",
            "Calendar/scheduling integration",
            f"CRM integration ({', '.join(proposal_data.get('integration_needs', []))})" if proposal_data.get('integration_needs') else "CRM integration setup",
            "Automated email/SMS follow-ups",
            "Lead qualification logic",
        ]),
        ("Testing & Deployment", [
            "Comprehensive testing across practice areas",
            "Staff training and documentation",
            "Go-live support and monitoring",
            "Post-launch optimization (30 days)"
        ])
    ]
    
    for scope_title, scope_list in scope_items:
        story.append(Paragraph(scope_title, subheading_style))
        for item in scope_list:
            story.append(Paragraph(f"• {item}", styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Custom Features
    if proposal_data.get('custom_features'):
        story.append(Paragraph("ADDITIONAL CUSTOM FEATURES", subheading_style))
        for feature in proposal_data['custom_features']:
            story.append(Paragraph(f"• {feature}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    # Timeline
    story.append(Paragraph("PROJECT TIMELINE", heading_style))
    timeline_weeks = proposal_data.get('timeline_weeks', 6)
    timeline_data = [
        ['Phase', 'Duration', 'Deliverables'],
        ['Discovery & Planning', '1-2 weeks', 'Custom scripts, integration plan'],
        ['Development', f'{timeline_weeks-3} weeks', 'Fully configured system'],
        ['Testing & Training', '1 week', 'Staff training, documentation'],
        ['Go-Live & Support', '30 days', 'Monitoring, optimization'],
    ]
    
    t = Table(timeline_data, colWidths=[1.8*inch, 1.5*inch, 3.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # Investment
    story.append(Paragraph("INVESTMENT", heading_style))
    
    total = proposal_data.get('total_price', 25000)
    deposit = total * 0.30
    milestone2 = total * 0.50
    final = total * 0.20
    
    pricing_data = [
        ['Item', 'Amount'],
        ['LawBot 360 Complete System', f'${total:,.2f}'],
        ['', ''],
        ['Payment Schedule:', ''],
        ['30% Deposit (upon signing)', f'${deposit:,.2f}'],
        ['50% Mid-Build (development complete)', f'${milestone2:,.2f}'],
        ['20% Final (go-live deployment)', f'${final:,.2f}'],
    ]
    
    t = Table(pricing_data, colWidths=[4*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('LINEABOVE', (0,1), (-1,1), 1, colors.HexColor('#1e40af')),
        ('LINEBELOW', (0,1), (-1,1), 1, colors.HexColor('#1e40af')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    
    # Maintenance Options
    maintenance_tier = proposal_data.get('maintenance_tier', 'Standard')
    maintenance_prices = {
        'Basic': 99,
        'Standard': 199,
        'Premium': 399
    }
    
    story.append(Paragraph("ONGOING MAINTENANCE (OPTIONAL)", heading_style))
    maintenance_desc = f"""
    Recommended: {maintenance_tier} tier - ${maintenance_prices.get(maintenance_tier, 199)}/month
    Includes system monitoring, updates, conversation flow optimization, and priority support.
    """
    story.append(Paragraph(maintenance_desc, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # ROI Projection
    story.append(Paragraph("RETURN ON INVESTMENT", heading_style))
    roi_text = f"""
    Based on industry averages, most law firms recoup their LawBot 360 investment with 1-2 cases.
    With {proposal_data.get('monthly_inquiries', '50+')} monthly inquiries, even a modest 10% increase in conversion
    can generate substantial ROI within the first 90 days.
    """
    story.append(Paragraph(roi_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Next Steps
    story.append(Paragraph("NEXT STEPS", heading_style))
    next_steps = [
        "Review and sign this proposal",
        "Schedule kickoff call for discovery phase",
        "Process 30% deposit payment",
        "Begin custom script development",
    ]
    for i, step in enumerate(next_steps, 1):
        story.append(Paragraph(f"{i}. {step}", styles['Normal']))
    
    story.append(Spacer(1, 0.4*inch))
    
    # Signature Section
    story.append(Paragraph("AGREEMENT", heading_style))
    story.append(Paragraph(f"""
    By signing below, {proposal_data['firm_name']} agrees to proceed with the LawBot 360 implementation
    as outlined in this proposal.
    """, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    sig_data = [
        ['Client Signature:', '_' * 50, 'Date:', '_' * 20],
        ['', '', '', ''],
        [f"{proposal_data.get('contact_name', 'Authorized Representative')}", '', '', ''],
        [proposal_data['firm_name'], '', '', ''],
        ['', '', '', ''],
        ['4D LegalTech Representative:', '_' * 50, 'Date:', '_' * 20],
    ]
    
    t = Table(sig_data, colWidths=[1.5*inch, 3*inch, 0.7*inch, 1.3*inch])
    t.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
    ]))
    story.append(t)
    
    # Footer
    story.append(Spacer(1, 0.3*inch))
    footer_text = """
    <font size=8 color=#6b7280>
    4D LegalTech | Email: legaltech@4dgaming.games | Website: 4dgaming.games
    <br/>This proposal is valid for 30 days from the date above.
    </font>
    """
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    return output_path


def create_invoice_pdf(output_path, invoice_data):
    """
    Generate a professional invoice PDF
    
    invoice_data = {
        'invoice_number': 'INV-2024-001',
        'firm_name': 'Smith & Associates',
        'contact_name': 'John Smith',
        'contact_email': 'john@smithlaw.com',
        'project_name': 'LawBot 360 Implementation',
        'milestone': 'Deposit Payment',
        'amount': 7500.00,
        'total_project_cost': 25000.00,
        'payment_link': 'https://stripe.com/...',
    }
    """
    
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    # Header
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Company Info & Invoice Details Side by Side
    today = datetime.now().strftime("%B %d, %Y")
    due_date = (datetime.now() + timedelta(days=15)).strftime("%B %d, %Y")
    
    header_data = [
        ['4D LegalTech', 'Invoice Number:', invoice_data.get('invoice_number', 'DRAFT')],
        ['legaltech@4dgaming.games', 'Date Issued:', today],
        ['4dgaming.games', 'Due Date:', due_date],
    ]
    
    t = Table(header_data, colWidths=[3*inch, 1.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (2,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # Bill To
    story.append(Paragraph("<b>BILL TO:</b>", styles['Normal']))
    story.append(Paragraph(f"<b>{invoice_data['firm_name']}</b>", styles['Normal']))
    story.append(Paragraph(invoice_data.get('contact_name', ''), styles['Normal']))
    story.append(Paragraph(invoice_data.get('contact_email', ''), styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Invoice Items
    items_data = [
        ['Description', 'Amount'],
        [invoice_data.get('project_name', 'LawBot 360 Implementation'), ''],
        [f"Milestone: {invoice_data.get('milestone', 'Deposit')}", f"${invoice_data.get('amount', 0):,.2f}"],
        ['', ''],
        ['<b>TOTAL DUE</b>', f"<b>${invoice_data.get('amount', 0):,.2f}</b>"],
    ]
    
    t = Table(items_data, colWidths=[4.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('LINEABOVE', (0,4), (-1,4), 2, colors.HexColor('#1e40af')),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor('#f3f4f6')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # Payment Schedule Context
    if invoice_data.get('total_project_cost'):
        total = invoice_data['total_project_cost']
        story.append(Paragraph("<b>PROJECT PAYMENT SCHEDULE:</b>", styles['Normal']))
        schedule_data = [
            ['30% Deposit', f'${total * 0.30:,.2f}'],
            ['50% Mid-Build', f'${total * 0.50:,.2f}'],
            ['20% Final Delivery', f'${total * 0.20:,.2f}'],
            ['<b>Total Project Cost</b>', f'<b>${total:,.2f}</b>'],
        ]
        
        t = Table(schedule_data, colWidths=[4.5*inch, 2*inch])
        t.setStyle(TableStyle([
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('LINEABOVE', (0,3), (-1,3), 1, colors.grey),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
    
    # Payment Methods
    story.append(Paragraph("<b>PAYMENT METHODS:</b>", styles['Normal']))
    
    if invoice_data.get('payment_link'):
        payment_text = f"""
        • <b>Pay Online (Recommended):</b> <link href="{invoice_data['payment_link']}" color="blue">Click here to pay securely via Stripe</link><br/>
        • <b>Bank Transfer:</b> Contact us for wire transfer details<br/>
        • <b>Credit Card:</b> Available via Stripe link above
        """
    else:
        payment_text = """
        • <b>Bank Transfer:</b> Contact us for wire transfer details<br/>
        • <b>Credit Card:</b> Stripe link will be provided via email<br/>
        • <b>Check:</b> Make payable to "4D LegalTech"
        """
    story.append(Paragraph(payment_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Terms
    story.append(Paragraph("<b>PAYMENT TERMS:</b>", styles['Normal']))
    terms_text = """
    Payment is due within 15 days of invoice date. Late payments may delay project milestones.
    For questions regarding this invoice, please contact legaltech@4dgaming.games.
    """
    story.append(Paragraph(terms_text, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_text = """
    <font size=8 color=#6b7280>
    Thank you for partnering with 4D LegalTech!<br/>
    4D LegalTech | legaltech@4dgaming.games | 4dgaming.games
    </font>
    """
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    return output_path


# Example usage
if __name__ == "__main__":
    # Test proposal generation
    sample_proposal = {
        'proposal_number': 'LB360-2024-001',
        'firm_name': 'Smith & Associates Law Firm',
        'contact_name': 'John Smith',
        'contact_email': 'john@smithlaw.com',
        'contact_phone': '555-123-4567',
        'practice_areas': ['Personal Injury', 'Family Law', 'Estate Planning'],
        'current_intake_method': 'Manual phone screening by receptionist',
        'pain_points': [
            'Missing after-hours leads',
            'Long intake times (15-20 minutes per call)',
            'Inconsistent data collection',
            'No lead qualification before attorney review'
        ],
        'monthly_inquiries': '75-100',
        'integration_needs': ['Clio', 'Google Calendar'],
        'custom_features': [
            'Spanish language support',
            'Text message appointment reminders',
        ],
        'total_price': 25000,
        'maintenance_tier': 'Standard',
        'timeline_weeks': 6,
    }
    
    sample_invoice = {
        'invoice_number': 'INV-2024-001',
        'firm_name': 'Smith & Associates Law Firm',
        'contact_name': 'John Smith',
        'contact_email': 'john@smithlaw.com',
        'project_name': 'LawBot 360 AI Intake System',
        'milestone': '30% Deposit Payment',
        'amount': 7500.00,
        'total_project_cost': 25000.00,
        'payment_link': 'https://buy.stripe.com/test_123456',
    }
    
    create_proposal_pdf('test_proposal.pdf', sample_proposal)
    create_invoice_pdf('test_invoice.pdf', sample_invoice)
    print("Test PDFs generated!")