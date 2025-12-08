"""
Proposal PDF Generator for 4D Gaming / LawBot 360
Updated to handle maintenance opt-out
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime


def create_proposal_pdf(filepath, data):
    """
    Generate a professional proposal PDF
    
    Args:
        filepath: Path where PDF will be saved
        data: Dictionary containing proposal information
    """
    
    # Create PDF
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for PDF elements
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    proposal_header_style = ParagraphStyle(
        'ProposalHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    # Header
    story.append(Paragraph("PROJECT PROPOSAL", title_style))
    story.append(Paragraph(
        f"Proposal #{data['proposal_number']}<br/>Date: {datetime.now().strftime('%B %d, %Y')}",
        proposal_header_style
    ))
    
    # Client Information
    story.append(Paragraph("CLIENT INFORMATION:", heading_style))
    
    client_info = [
        ['Company:', data['firm_name']],
        ['Contact:', data['contact_name']],
        ['Email:', data['contact_email']],
    ]
    
    if data.get('contact_phone'):
        client_info.append(['Phone:', data['contact_phone']])
    
    client_table = Table(client_info, colWidths=[1.5*inch, 5*inch])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1f2937')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Project Overview
    if data.get('current_intake_method'):
        story.append(Paragraph("PROJECT OVERVIEW:", heading_style))
        story.append(Paragraph(data['current_intake_method'], styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
    
    # Services
    if data.get('practice_areas'):
        story.append(Paragraph("SERVICES:", heading_style))
        
        service_names = {
            'chatbot': 'AI Chatbot Development',
            'mobile': 'Mobile App Development',
            'gamedev': 'Game Development Services',
            'web3': 'Web3 & Blockchain Solutions',
            'scraping': 'Web Scraping & Automation',
            'trading': 'Trading Bot Development',
            'website': 'Website Development',
            'lawbot360': 'LawBot 360 - Complete Legal Intake System',
            'custom': 'Custom Development Project'
        }
        
        for service in data['practice_areas']:
            service_name = service_names.get(service, service.title())
            story.append(Paragraph(f"• {service_name}", styles['Normal']))
        
        story.append(Spacer(1, 0.2*inch))
    
    # Add-ons
    if data.get('addons') and len(data['addons']) > 0:
        story.append(Paragraph("ENHANCEMENTS & ADD-ONS:", heading_style))
        
        for addon in data['addons']:
            story.append(Paragraph(
                f"• {addon['label']} - ${addon['price']:,}",
                styles['Normal']
            ))
        
        story.append(Spacer(1, 0.3*inch))
    
    # Timeline
    story.append(Paragraph("PROJECT TIMELINE:", heading_style))
    
    timeline_weeks = data.get('timeline_weeks', 6)
    story.append(Paragraph(
        f"Estimated completion: {timeline_weeks} weeks from project start",
        styles['Normal']
    ))
    story.append(Spacer(1, 0.1*inch))
    
    # Timeline phases (example)
    phases_data = [
        ['Phase', 'Duration', 'Deliverables'],
        ['Planning & Discovery', '1 week', 'Project plan, technical specs'],
        ['Development', f'{timeline_weeks - 2} weeks', 'Fully functional system'],
        ['Testing & Deployment', '1 week', 'Production-ready solution'],
    ]
    
    phases_table = Table(phases_data, colWidths=[2*inch, 1.5*inch, 3*inch])
    phases_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
    ]))
    story.append(phases_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Investment
    story.append(Paragraph("INVESTMENT", heading_style))
    
    investment_data = [
        [Paragraph('<b>Item</b>', styles['Normal']), 
         Paragraph('<b>Amount</b>', ParagraphStyle('RightBold', parent=styles['Normal'], alignment=TA_RIGHT, fontName='Helvetica-Bold'))]
    ]
    
    investment_data.append([
        'Complete Project',
        Paragraph(f'${data["total_price"]:,.2f}', ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT))
    ])
    
    investment_table = Table(investment_data, colWidths=[4.5*inch, 2*inch])
    investment_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#3b82f6')),
        ('LINEABOVE', (0, 1), (-1, 1), 0.5, colors.HexColor('#e5e7eb')),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(investment_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Payment Schedule
    story.append(Paragraph("Payment Schedule:", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    
    # Calculate payment schedule based on service type
    is_lawbot = 'lawbot360' in data.get('practice_areas', [])
    
    if is_lawbot:
        # LawBot 360: 30/50/20
        deposit = data['total_price'] * 0.30
        mid = data['total_price'] * 0.50
        final = data['total_price'] * 0.20
        
        schedule_text = f"""30% Deposit (upon contract signing)    ${deposit:,.2f}
50% Mid-Project (development complete)    ${mid:,.2f}
20% Final (delivery & deployment)    ${final:,.2f}"""
    else:
        # Other services: 40/40/20
        deposit = data['total_price'] * 0.40
        mid = data['total_price'] * 0.40
        final = data['total_price'] * 0.20
        
        schedule_text = f"""40% Deposit (upon contract signing)    ${deposit:,.2f}
40% Mid-Project (development complete)    ${mid:,.2f}
20% Final (delivery & deployment)    ${final:,.2f}"""
    
    story.append(Paragraph(schedule_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Maintenance Section - Handle Opt-Out
    maintenance_tier = data.get('maintenance_tier', 'Standard')
    
    story.append(Paragraph("ONGOING MAINTENANCE (OPTIONAL)", heading_style))
    
    if maintenance_tier == 'None':
        # Client opted out
        story.append(Paragraph(
            "<b>Recommended: None</b> - Client will handle their own maintenance and support.",
            styles['Normal']
        ))
        story.append(Paragraph(
            "The client has chosen to manage system maintenance, updates, and support independently.",
            styles['Normal']
        ))
    else:
        # Show selected maintenance tier
        maintenance_info = {
            # Standard tiers
            'Basic': {
                'price': '$99/month',
                'features': 'Includes system monitoring, updates, optimization, and priority support.'
            },
            'Standard': {
                'price': '$199/month',
                'features': 'Includes system monitoring, updates, optimization, and priority support.'
            },
            'Premium': {
                'price': '$399/month',
                'features': 'Includes system monitoring, updates, optimization, and priority support.'
            },
            # LawBot 360 tiers
            'Professional': {
                'price': '$997/month',
                'features': 'Includes system monitoring, updates, optimization, and priority support.'
            },
            'Enterprise': {
                'price': '$1,997/month',
                'features': 'Includes system monitoring, updates, optimization, and priority support.'
            },
        }
        
        if maintenance_tier in maintenance_info:
            tier_info = maintenance_info[maintenance_tier]
            story.append(Paragraph(
                f"<b>Recommended: {maintenance_tier} tier - {tier_info['price']}</b>",
                styles['Normal']
            ))
            story.append(Paragraph(tier_info['features'], styles['Normal']))
        else:
            # Fallback
            story.append(Paragraph(
                f"<b>Recommended: {maintenance_tier} tier</b>",
                styles['Normal']
            ))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Next Steps
    story.append(Paragraph("NEXT STEPS", heading_style))
    
    next_steps = [
        "1. Review and approve this proposal",
        "2. Sign the agreement below",
        "3. Submit 30% deposit payment" if is_lawbot else "3. Submit 40% deposit payment",
        "4. Schedule project kickoff meeting",
        "5. Begin development"
    ]
    
    for step in next_steps:
        story.append(Paragraph(step, styles['Normal']))
    
    story.append(Spacer(1, 0.4*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    
    story.append(Paragraph("Thank you for considering 4D Gaming!", footer_style))
    story.append(Paragraph(
        "4D Gaming | legaltech@4dgaming.games | 4dgaming.games",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    print(f"Proposal generated: {filepath}")


# For invoice generation (placeholder)
def create_invoice_pdf(filepath, data):
    """
    Generate invoice PDF (separate from proposal)
    """
    # This would be in a separate file typically
    pass