# lawbot_proposal_generator.py - Fixed Version

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime, timedelta
import os
import json

def create_proposal_pdf(output_path, proposal_data):
    """
    Generate a professional proposal PDF
    
    Fixed version with better error handling and data validation
    """
    
    # Validate and normalize data
    proposal_data = normalize_proposal_data(proposal_data)
    
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
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#3b82f6'),
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
    story.append(Paragraph("4D GAMING", title_style))
    story.append(Paragraph("Professional Development Services", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Proposal details
    today = datetime.now().strftime("%B %d, %Y")
    valid_until = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")
    
    proposal_info = [
        ['Proposal Number:', str(proposal_data.get('proposal_number', 'DRAFT'))],
        ['Date:', today],
        ['Valid Until:', valid_until],
        ['Prepared For:', str(proposal_data.get('firm_name', 'Client'))],
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
    
    services = proposal_data.get('practice_areas', [])
    if isinstance(services, str):
        services = [services]
    
    services_text = format_services_list(services)
    
    exec_summary = f"""
    This proposal outlines a custom implementation for {proposal_data.get('firm_name', 'your organization')}.
    The project includes: {services_text}.
    We will deliver a complete solution tailored to your specific requirements.
    """
    story.append(Paragraph(exec_summary, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Project Description
    if proposal_data.get('current_intake_method'):
        story.append(Paragraph("PROJECT OVERVIEW", heading_style))
        desc = str(proposal_data.get('current_intake_method', '')).strip()
        if desc:
            story.append(Paragraph(desc, styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
    
    # Services Included
    story.append(Paragraph("SERVICES INCLUDED", heading_style))
    for service in services:
        service_name = format_service_name(service)
        story.append(Paragraph(f"• {service_name}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Add-ons (if any)
    addons = proposal_data.get('addons', [])
    if addons and len(addons) > 0:
        story.append(Paragraph("ADDITIONAL FEATURES", heading_style))
        for addon in addons:
            if isinstance(addon, dict):
                addon_label = addon.get('label', 'Custom feature')
                addon_price = addon.get('price', 0)
                story.append(Paragraph(f"• {addon_label} (+${addon_price:,})", styles['Normal']))
            else:
                story.append(Paragraph(f"• {addon}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    # Scope of Work
    story.append(Paragraph("SCOPE OF WORK", heading_style))
    
    scope_items = [
        ("Planning & Discovery", [
            "Requirements gathering and analysis",
            "Technical architecture design",
            "Project timeline and milestone planning",
            "Communication protocol establishment"
        ]),
        ("Development & Implementation", [
            "Core functionality development",
            "Integration with existing systems",
            "User interface design and implementation",
            "Quality assurance and testing",
            "Documentation creation"
        ]),
        ("Deployment & Support", [
            "Production deployment",
            "Training and knowledge transfer",
            "Post-launch monitoring",
            "30-day optimization period"
        ])
    ]
    
    for scope_title, scope_list in scope_items:
        story.append(Paragraph(scope_title, subheading_style))
        for item in scope_list:
            story.append(Paragraph(f"• {item}", styles['Normal']))
        story.append(Spacer(1, 0.15*inch))
    
    # Timeline
    story.append(Paragraph("PROJECT TIMELINE", heading_style))
    timeline_weeks = int(proposal_data.get('timeline_weeks', 6))
    
    timeline_data = [
        ['Phase', 'Duration', 'Deliverables'],
        ['Planning & Discovery', '1 week', 'Project plan, technical specs'],
        ['Development', f'{timeline_weeks-2} weeks', 'Fully functional system'],
        ['Testing & Deployment', '1 week', 'Production-ready solution'],
    ]
    
    t = Table(timeline_data, colWidths=[1.8*inch, 1.5*inch, 3.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3b82f6')),
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
    
    total = float(proposal_data.get('total_price', 0))
    deposit = total * 0.30
    milestone2 = total * 0.50
    final = total * 0.20
    
    pricing_data = [
        ['Item', 'Amount'],
        ['Complete Project', f'${total:,.2f}'],
        ['', ''],
        ['Payment Schedule:', ''],
        ['30% Deposit (upon contract signing)', f'${deposit:,.2f}'],
        ['50% Mid-Project (development complete)', f'${milestone2:,.2f}'],
        ['20% Final (delivery & deployment)', f'${final:,.2f}'],
    ]
    
    t = Table(pricing_data, colWidths=[4*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('LINEABOVE', (0,1), (-1,1), 1, colors.HexColor('#3b82f6')),
        ('LINEBELOW', (0,1), (-1,1), 1, colors.HexColor('#3b82f6')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2*inch))
    
    # Maintenance Options
    maintenance_tier = str(proposal_data.get('maintenance_tier', 'Standard'))
    
    # Determine if this is LawBot pricing
    is_lawbot = 'lawbot' in str(services).lower() or total >= 20000
    
    if is_lawbot:
        maintenance_prices = {
            'Basic': 497,
            'Professional': 997,
            'Enterprise': 1997
        }
    else:
        maintenance_prices = {
            'Basic': 99,
            'Standard': 199,
            'Premium': 399
        }
    
    monthly_price = maintenance_prices.get(maintenance_tier, 199)
    
    story.append(Paragraph("ONGOING MAINTENANCE (OPTIONAL)", heading_style))
    maintenance_desc = f"""
    Recommended: {maintenance_tier} tier - ${monthly_price}/month<br/>
    Includes system monitoring, updates, optimization, and priority support.
    """
    story.append(Paragraph(maintenance_desc, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Next Steps
    story.append(Paragraph("NEXT STEPS", heading_style))
    next_steps = [
        "Review and approve this proposal",
        "Sign the agreement below",
        "Submit 30% deposit payment",
        "Schedule project kickoff meeting",
        "Begin development",
    ]
    for i, step in enumerate(next_steps, 1):
        story.append(Paragraph(f"{i}. {step}", styles['Normal']))
    
    story.append(Spacer(1, 0.4*inch))
    
    # Signature Section
    story.append(Paragraph("AGREEMENT", heading_style))
    story.append(Paragraph(f"""
    By signing below, {proposal_data.get('firm_name', 'the client')} agrees to proceed with 
    the project as outlined in this proposal.
    """, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    contact_name = str(proposal_data.get('contact_name', 'Authorized Representative'))
    firm_name = str(proposal_data.get('firm_name', 'Client'))
    
    sig_data = [
        ['Client Signature:', '_' * 50, 'Date:', '_' * 20],
        ['', '', '', ''],
        [contact_name, '', '', ''],
        [firm_name, '', '', ''],
        ['', '', '', ''],
        ['4D Gaming Representative:', '_' * 50, 'Date:', '_' * 20],
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
    4D Gaming | Email: legaltech@4dgaming.games | Website: 4dgaming.games
    <br/>This proposal is valid for 30 days from the date above.
    </font>
    """
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    return output_path


def normalize_proposal_data(data):
    """Ensure all data is properly formatted and safe"""
    
    # Create a clean copy
    clean_data = {}
    
    # Safe string fields
    string_fields = [
        'proposal_number', 'firm_name', 'contact_name', 'contact_email',
        'contact_phone', 'current_intake_method', 'monthly_inquiries',
        'maintenance_tier'
    ]
    
    for field in string_fields:
        value = data.get(field, '')
        clean_data[field] = str(value) if value else ''
    
    # Numeric fields
    clean_data['total_price'] = float(data.get('total_price', 0))
    clean_data['timeline_weeks'] = int(data.get('timeline_weeks', 6))
    
    # List fields
    clean_data['practice_areas'] = ensure_list(data.get('practice_areas', []))
    clean_data['pain_points'] = ensure_list(data.get('pain_points', []))
    clean_data['integration_needs'] = ensure_list(data.get('integration_needs', []))
    clean_data['custom_features'] = ensure_list(data.get('custom_features', []))
    clean_data['addons'] = ensure_list(data.get('addons', []))
    
    return clean_data


def ensure_list(value):
    """Convert value to list if it isn't already"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        # Try to parse as JSON
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        # Return as single-item list
        return [value] if value else []
    return [value]


def format_services_list(services):
    """Format list of services into readable text"""
    if not services:
        return "custom development services"
    
    formatted = [format_service_name(s) for s in services]
    
    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    else:
        return ", ".join(formatted[:-1]) + f", and {formatted[-1]}"


def format_service_name(service):
    """Convert service code to readable name"""
    service_names = {
        'chatbot': 'AI Chatbot Development',
        'mobile': 'Mobile App Development',
        'game': 'Game Development',
        'web3': 'Web3 & Blockchain Integration',
        'scraping': 'Web Scraping Solution',
        'trading': 'Trading Bot Development',
        'website': 'Website Development',
        'lawbot360': 'LawBot 360 AI System',
        'custom': 'Custom Solution'
    }
    
    service_str = str(service).lower().strip()
    return service_names.get(service_str, service.title())


def create_invoice_pdf(output_path, invoice_data):
    """
    Generate a professional invoice PDF
    """
    
    # Normalize invoice data
    invoice_data = normalize_invoice_data(invoice_data)
    
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    # Header
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Company Info & Invoice Details
    today = datetime.now().strftime("%B %d, %Y")
    due_date = (datetime.now() + timedelta(days=15)).strftime("%B %d, %Y")
    
    header_data = [
        ['4D Gaming', 'Invoice Number:', str(invoice_data.get('invoice_number', 'DRAFT'))],
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
    story.append(Paragraph(f"<b>{invoice_data.get('firm_name', '')}</b>", styles['Normal']))
    if invoice_data.get('contact_name'):
        story.append(Paragraph(invoice_data['contact_name'], styles['Normal']))
    if invoice_data.get('contact_email'):
        story.append(Paragraph(invoice_data['contact_email'], styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Invoice Items
    amount = float(invoice_data.get('amount', 0))
    
    items_data = [
        ['Description', 'Amount'],
        [invoice_data.get('project_name', 'Development Services'), ''],
        [f"Milestone: {invoice_data.get('milestone', 'Payment')}", f"${amount:,.2f}"],
        ['', ''],
        ['<b>TOTAL DUE</b>', f"<b>${amount:,.2f}</b>"],
    ]
    
    t = Table(items_data, colWidths=[4.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('LINEABOVE', (0,4), (-1,4), 2, colors.HexColor('#3b82f6')),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor('#f3f4f6')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))
    
    # Payment Schedule Context
    total_project = invoice_data.get('total_project_cost')
    if total_project:
        total = float(total_project)
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
    
    payment_link = invoice_data.get('payment_link', '')
    if payment_link:
        payment_text = f"""
        • <b>Pay Online (Recommended):</b> <link href="{payment_link}" color="blue">Click here to pay securely</link><br/>
        • <b>Bank Transfer:</b> Contact us for wire transfer details<br/>
        • <b>Credit Card:</b> Available via payment link above
        """
    else:
        payment_text = """
        • <b>Bank Transfer:</b> Contact us for wire transfer details<br/>
        • <b>Credit Card:</b> Payment link will be provided via email<br/>
        • <b>Check:</b> Make payable to "4D Gaming"
        """
    story.append(Paragraph(payment_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Terms
    story.append(Paragraph("<b>PAYMENT TERMS:</b>", styles['Normal']))
    terms_text = """
    Payment is due within 15 days of invoice date. Late payments may delay project milestones.
    For questions, please contact legaltech@4dgaming.games.
    """
    story.append(Paragraph(terms_text, styles['Normal']))
    story.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_text = """
    <font size=8 color=#6b7280>
    Thank you for your business!<br/>
    4D Gaming | legaltech@4dgaming.games | 4dgaming.games
    </font>
    """
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    return output_path


def normalize_invoice_data(data):
    """Ensure invoice data is properly formatted"""
    clean_data = {}
    
    string_fields = [
        'invoice_number', 'firm_name', 'contact_name', 'contact_email',
        'project_name', 'milestone', 'payment_link'
    ]
    
    for field in string_fields:
        value = data.get(field, '')
        clean_data[field] = str(value) if value else ''
    
    clean_data['amount'] = float(data.get('amount', 0))
    
    total_cost = data.get('total_project_cost')
    if total_cost:
        clean_data['total_project_cost'] = float(total_cost)
    
    return clean_data


# Example usage
if __name__ == "__main__":
    sample_proposal = {
        'proposal_number': '4DG-2024-001',
        'firm_name': 'Test Firm',
        'contact_name': 'Joe Sample',
        'contact_email': '4dsw99@gmail.com',
        'contact_phone': '',
        'practice_areas': ['lawbot360'],
        'addons': [
            {'label': 'Multi-language support', 'price': 1500}
        ],
        'current_intake_method': '',
        'total_price': 26500,
        'timeline_weeks': 2,
        'maintenance_tier': 'Professional',
    }
    
    create_proposal_pdf('test_proposal.pdf', sample_proposal)
    print("Test PDF generated!")