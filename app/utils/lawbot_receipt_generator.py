"""
Receipt PDF Generator for 4D Gaming
Generates professional receipts for payments received
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
from pathlib import Path


def create_receipt_pdf(filepath, data):
    """
    Generate a professional receipt PDF
    
    Args:
        filepath: Path where PDF will be saved
        data: Dictionary containing:
            - receipt_number: str
            - firm_name: str
            - contact_name: str (optional)
            - contact_email: str (optional)
            - payment_date: str (YYYY-MM-DD format)
            - payment_method: str (e.g., "Credit Card", "Wire Transfer", "Check")
            - service_type: str (e.g., "LawBot 360", "AI Chatbot")
            - addons: list of dicts with 'label' and 'price'
            - milestone: str (e.g., "Deposit Payment", "Final Payment")
            - amount: float
            - total_project_cost: float
            - transaction_id: str (optional)
            - notes: str (optional)
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
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    receipt_header_style = ParagraphStyle(
        'ReceiptHeader',
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
    story.append(Paragraph("RECEIPT", title_style))
    story.append(Paragraph(
        f"Receipt #{data['receipt_number']}<br/>Date: {data.get('payment_date', datetime.now().strftime('%B %d, %Y'))}",
        receipt_header_style
    ))
    
    # Client Information
    story.append(Paragraph("PAYMENT RECEIVED FROM:", heading_style))
    
    client_info = [
        ['Client:', data['firm_name']],
    ]
    
    if data.get('contact_name'):
        client_info.append(['Contact:', data['contact_name']])
    if data.get('contact_email'):
        client_info.append(['Email:', data['contact_email']])
    
    client_table = Table(client_info, colWidths=[1.5*inch, 4.5*inch])
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
    
    # Payment Details
    story.append(Paragraph("PAYMENT DETAILS:", heading_style))
    
    # Build items table
    items_data = [
        [
            Paragraph('<b>Description</b>', styles['Normal']),
            Paragraph('<b>Amount</b>', ParagraphStyle('RightBold', parent=styles['Normal'], alignment=TA_RIGHT, fontName='Helvetica-Bold'))
        ]
    ]
    
    # Main service
    service_desc = data.get('service_type', 'Service')
    if data.get('milestone'):
        service_desc += f"\nMilestone: {data['milestone']}"
    
    items_data.append([
        Paragraph(service_desc, styles['Normal']),
        Paragraph(f"${data['amount']:,.2f}", ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT))
    ])
    
    # Add-ons if any
    if data.get('addons'):
        for addon in data['addons']:
            items_data.append([
                Paragraph(f"  + {addon['label']}", styles['Normal']),
                Paragraph(f"${addon['price']:,.2f}", ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT))
            ])
    
    items_table = Table(items_data, colWidths=[4.5*inch, 2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
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
    story.append(items_table)
    story.append(Spacer(1, 0.1*inch))
    
    # Total
    total_data = [
        [
            Paragraph('<b>TOTAL PAID</b>', styles['Normal']),
            Paragraph(f'<b>${data["amount"]:,.2f}</b>', ParagraphStyle('RightBold', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=14, textColor=colors.HexColor('#2563eb')))
        ]
    ]
    
    total_table = Table(total_data, colWidths=[4.5*inch, 2*inch])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
        ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor('#2563eb')),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Payment Method
    story.append(Paragraph("PAYMENT METHOD:", heading_style))
    
    payment_info = [
        ['Method:', data.get('payment_method', 'Not specified')],
    ]
    
    if data.get('payment_date'):
        payment_info.append(['Date Received:', data['payment_date']])
    
    if data.get('transaction_id'):
        payment_info.append(['Transaction ID:', data['transaction_id']])
    
    payment_table = Table(payment_info, colWidths=[1.5*inch, 4.5*inch])
    payment_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6b7280')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1f2937')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Project Summary (if applicable)
    if data.get('total_project_cost'):
        story.append(Paragraph("PROJECT SUMMARY:", heading_style))
        
        # Calculate payment schedule based on service type
        service = data.get('service_type', '')
        if 'LawBot 360' in service or 'lawbot' in service.lower():
            schedule = [30, 50, 20]
            schedule_labels = ['30% Deposit', '50% Mid-Build', '20% Final Delivery']
        else:
            schedule = [40, 40, 20]
            schedule_labels = ['40% Deposit', '40% Mid-Project', '20% Final Payment']
        
        total_cost = data['total_project_cost']
        
        project_data = []
        for i, (pct, label) in enumerate(zip(schedule, schedule_labels)):
            milestone_amount = (total_cost * pct) / 100
            project_data.append([label, f'${milestone_amount:,.2f}'])
        
        project_data.append(['', ''])  # Spacer row
        project_data.append([
            Paragraph('<b>Total Project Cost</b>', styles['Normal']),
            Paragraph(f'<b>${total_cost:,.2f}</b>', ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT))
        ])
        
        project_table = Table(project_data, colWidths=[4.5*inch, 2*inch])
        project_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -2), colors.HexColor('#6b7280')),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#2563eb')),
        ]))
        story.append(project_table)
        story.append(Spacer(1, 0.2*inch))
    
    # Notes
    if data.get('notes'):
        story.append(Paragraph("NOTES:", heading_style))
        story.append(Paragraph(data['notes'], styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(Spacer(1, 0.4*inch))
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    
    story.append(Paragraph("Thank you for your payment!", footer_style))
    story.append(Paragraph(
        "4D Gaming | legaltech@4dgaming.games | 4dgaming.games",
        footer_style
    ))
    
    # Build PDF
    doc.build(story)
    print(f"Receipt generated: {filepath}")


# Example usage
if __name__ == "__main__":
    sample_data = {
        'receipt_number': 'RCP-2025-001',
        'firm_name': 'ABC Law Firm',
        'contact_name': 'John Smith',
        'contact_email': 'john@abclaw.com',
        'payment_date': '2025-01-15',
        'payment_method': 'Credit Card (Stripe)',
        'service_type': 'LawBot 360',
        'addons': [
            {'label': 'Mobile Apps (iOS & Android)', 'price': 5000},
            {'label': 'Advanced Analytics Dashboard', 'price': 2000}
        ],
        'milestone': 'Deposit Payment',
        'amount': 9600,
        'total_project_cost': 32000,
        'transaction_id': 'ch_3ABC123XYZ',
        'notes': 'Thank you for choosing 4D Gaming for your legal intake automation needs.'
    }
    
    create_receipt_pdf('sample_receipt.pdf', sample_data)