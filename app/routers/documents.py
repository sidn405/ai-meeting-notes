# backend/app/routers/documents.py
"""
API routes for generating proposals and invoices for LawBot 360
Returns PDF files directly as downloads
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import tempfile
import os

# Import your PDF generator
from app.utils.lawbot_proposal_generator import create_proposal_pdf, create_invoice_pdf
from app.utils.lawbot_receipt_generator import create_receipt_pdf

router = APIRouter(prefix="/api/admin", tags=["documents"])


# ============================================================================
# Pydantic models for request validation
# ============================================================================

class ProposalRequest(BaseModel):
    proposal_number: str
    firm_name: str
    contact_name: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    practice_areas: List[str]
    addons: List[dict] = []
    current_intake_method: Optional[str] = None
    pain_points: List[str] = []
    monthly_inquiries: Optional[str] = None
    integration_needs: List[str] = []
    custom_features: List[str] = []
    total_price: float
    timeline_weeks: int = 6
    timeline_phases: List[dict] = []
    maintenance_tier: str = "Standard"
    project_id: Optional[int] = None


class InvoiceRequest(BaseModel):
    invoice_number: str
    firm_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    project_name: str
    service_type: Optional[str] = None
    addons: List[dict] = []
    milestone: str
    amount: float
    total_project_cost: float
    payment_link: Optional[str] = None
    project_id: Optional[int] = None


class ReceiptRequest(BaseModel):
    receipt_number: str
    firm_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    payment_date: str  # YYYY-MM-DD format
    payment_method: str  # e.g., "Credit Card (Stripe)", "Wire Transfer", "Check"
    service_type: Optional[str] = None
    addons: List[dict] = []
    milestone: str
    amount: float
    total_project_cost: float
    transaction_id: Optional[str] = None
    notes: Optional[str] = None
    project_id: Optional[int] = None


class IntegrationInfoRequest(BaseModel):
    """Client system integration information"""
    companyName: str
    contactPerson: str
    email: EmailStr
    phone: Optional[str] = None
    systems: List[str] = []
    systemDetails: Optional[str] = None
    websiteUrl: str
    websitePlatform: Optional[str] = None
    hostingProvider: Optional[str] = None
    adminAccess: Optional[str] = None
    apiSystems: Optional[str] = None
    apiAvailability: Optional[str] = None
    crmSystem: Optional[str] = None
    crmApiDocs: Optional[str] = None
    features: List[str] = []
    additionalFeatures: Optional[str] = None
    existingContent: Optional[str] = None
    contentLocation: Optional[str] = None
    customerDatabase: Optional[str] = None
    compliance: List[str] = []
    privacyRequirements: Optional[str] = None
    technicalContactName: Optional[str] = None
    technicalContactEmail: Optional[str] = None
    timeline: Optional[str] = None
    additionalInfo: Optional[str] = None
    submittedAt: Optional[str] = None


# ============================================================================
# API Endpoints - Direct File Downloads
# ============================================================================

@router.post("/generate-proposal")
async def generate_proposal(request: ProposalRequest):
    """
    Generate a professional proposal PDF and return it directly as a download
    """
    try:
        # Create directory for proposals if it doesn't exist (for archival)
        proposals_dir = Path("static/proposals")
        proposals_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        firm_slug = request.firm_name.replace(" ", "_").replace("&", "and")[:30]
        filename = f"Proposal_{firm_slug}_{timestamp}.pdf"
        filepath = proposals_dir / filename
        
        # Prepare data for PDF generator
        proposal_data = {
            'proposal_number': request.proposal_number,
            'firm_name': request.firm_name,
            'contact_name': request.contact_name,
            'contact_email': request.contact_email,
            'contact_phone': request.contact_phone,
            'practice_areas': request.practice_areas,
            'addons': request.addons,
            'current_intake_method': request.current_intake_method,
            'pain_points': request.pain_points,
            'monthly_inquiries': request.monthly_inquiries,
            'integration_needs': request.integration_needs,
            'custom_features': request.custom_features,
            'total_price': request.total_price,
            'timeline_weeks': request.timeline_weeks,
            'timeline_phases': request.timeline_phases,
            'maintenance_tier': request.maintenance_tier,
        }
        
        # Debug logging
        print(f"Timeline phases received: {request.timeline_phases}")
        print(f"Number of custom phases: {len(request.timeline_phases)}")
        
        # Generate PDF
        create_proposal_pdf(str(filepath), proposal_data)
        
        # Return the PDF file directly as a download
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        import traceback
        print(f"Error generating proposal: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate proposal: {str(e)}"
        )


@router.post("/generate-invoice")
async def generate_invoice(request: InvoiceRequest):
    """
    Generate a professional invoice PDF and return it directly as a download
    """
    try:
        # Debug log the incoming request
        print(f"[INVOICE] Generating invoice for: {request.firm_name}")
        print(f"[INVOICE] Invoice number: {request.invoice_number}")
        print(f"[INVOICE] Amount: ${request.amount}")
        
        # Create directory for invoices if it doesn't exist (for archival)
        invoices_dir = Path("static/invoices")
        invoices_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        firm_slug = request.firm_name.replace(" ", "_").replace("&", "and")[:30]
        filename = f"Invoice_{request.invoice_number}_{firm_slug}_{timestamp}.pdf"
        filepath = invoices_dir / filename
        
        # Prepare data for PDF generator
        invoice_data = {
            'invoice_number': request.invoice_number,
            'firm_name': request.firm_name,
            'contact_name': request.contact_name,
            'contact_email': request.contact_email,
            'project_name': request.project_name,
            'service_type': request.service_type,
            'addons': request.addons,
            'milestone': request.milestone,
            'amount': request.amount,
            'total_project_cost': request.total_project_cost,
            'payment_link': request.payment_link,
        }
        
        # Generate PDF
        create_invoice_pdf(str(filepath), invoice_data)
        
        # Return the PDF file directly as a download
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        import traceback
        print(f"Error generating invoice: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invoice: {str(e)}"
        )


@router.post("/generate-receipt")
async def generate_receipt(request: ReceiptRequest):
    """
    Generate a professional receipt PDF and return it directly as a download
    For payments already received (not invoices for future payment)
    """
    try:
        # Debug log the incoming request
        print(f"[RECEIPT] Generating receipt for: {request.firm_name}")
        print(f"[RECEIPT] Receipt number: {request.receipt_number}")
        print(f"[RECEIPT] Amount: ${request.amount}")
        print(f"[RECEIPT] Payment method: {request.payment_method}")
        
        # Create directory for receipts if it doesn't exist (for archival)
        receipts_dir = Path("static/receipts")
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        firm_slug = request.firm_name.replace(" ", "_").replace("&", "and")[:30]
        filename = f"Receipt_{request.receipt_number}_{firm_slug}_{timestamp}.pdf"
        filepath = receipts_dir / filename
        
        # Prepare data for PDF generator
        receipt_data = {
            'receipt_number': request.receipt_number,
            'firm_name': request.firm_name,
            'contact_name': request.contact_name,
            'contact_email': request.contact_email,
            'payment_date': request.payment_date,
            'payment_method': request.payment_method,
            'service_type': request.service_type,
            'addons': request.addons,
            'milestone': request.milestone,
            'amount': request.amount,
            'total_project_cost': request.total_project_cost,
            'transaction_id': request.transaction_id,
            'notes': request.notes,
        }
        
        # Generate PDF
        create_receipt_pdf(str(filepath), receipt_data)
        
        # Return the PDF file directly as a download
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        import traceback
        print(f"Error generating receipt: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate receipt: {str(e)}"
        )


@router.get("/project-documents/{project_id}")
async def get_project_documents(project_id: int):
    """
    Get all documents (proposals, invoices) for a specific project
    """
    try:
        documents = []
        
        # Check proposals directory
        proposals_dir = Path("static/proposals")
        if proposals_dir.exists():
            for file in proposals_dir.glob("*.pdf"):
                documents.append({
                    "id": str(file.name),
                    "type": "proposal",
                    "filename": file.name,
                    "created_at": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    "size": file.stat().st_size,
                    "download_url": f"/api/admin/download/proposals/{file.name}"
                })
        
        # Check invoices directory
        invoices_dir = Path("static/invoices")
        if invoices_dir.exists():
            for file in invoices_dir.glob("*.pdf"):
                documents.append({
                    "id": str(file.name),
                    "type": "invoice",
                    "filename": file.name,
                    "created_at": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    "size": file.stat().st_size,
                    "download_url": f"/api/admin/download/invoices/{file.name}"
                })
        
        # Check receipts directory
        receipts_dir = Path("static/receipts")
        if receipts_dir.exists():
            for file in receipts_dir.glob("*.pdf"):
                documents.append({
                    "id": str(file.name),
                    "type": "receipt",
                    "filename": file.name,
                    "created_at": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
                    "size": file.stat().st_size,
                    "download_url": f"/api/admin/download/receipts/{file.name}"
                })
        
        # Sort by creation date, newest first
        documents.sort(key=lambda x: x["created_at"], reverse=True)
        
        return {
            "success": True,
            "project_id": project_id,
            "documents": documents
        }
        
    except Exception as e:
        print(f"Error fetching project documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch documents: {str(e)}"
        )


@router.delete("/documents/{file_type}/{filename}")
async def delete_document(file_type: str, filename: str):
    """
    Delete a document (proposal, invoice, or receipt)
    """
    if file_type not in ["proposals", "invoices", "receipts"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    filepath = Path(f"static/{file_type}/{filename}")
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        filepath.unlink()  # Delete the file
        return {
            "success": True,
            "message": f"Document {filename} deleted successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.get("/download/{file_type}/{filename}")
async def download_pdf(file_type: str, filename: str):
    """
    Download a generated PDF (proposal, invoice, or receipt) directly
    """
    if file_type not in ["proposals", "invoices", "receipts"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    filepath = Path(f"static/{file_type}/{filename}")
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/projects")
async def get_projects():
    """
    Get all projects for dropdown selection
    Returns empty list for now - implement when needed
    """
    # TODO: Query your actual projects table
    return []


@router.get("/health")
async def health_check():
    """
    Simple health check endpoint
    """
    return {
        "status": "healthy",
        "service": "documents",
        "endpoints": [
            "/api/admin/generate-proposal (POST) - Direct download",
            "/api/admin/generate-invoice (POST) - Direct download",
            "/api/admin/generate-receipt (POST) - Direct download",
            "/api/admin/submit-integration-info (POST) - Save client integration data",
            "/api/admin/project-documents/{project_id} (GET)",
            "/api/admin/download/{file_type}/{filename} (GET) - Direct download"
        ]
    }


@router.post("/submit-integration-info")
async def submit_integration_info(request: IntegrationInfoRequest):
    """
    Send client system integration information via email using Resend
    """
    try:
        import resend
        import os
        import json
        
        # Get Resend API key from environment
        resend.api_key = os.getenv("RESEND_API_KEY")
        
        if not resend.api_key:
            raise HTTPException(
                status_code=500,
                detail="Resend API key not configured"
            )
        
        # Format systems list
        systems_list = ', '.join(request.systems) if request.systems else 'None specified'
        
        # Format features list
        features_list = ', '.join(request.features) if request.features else 'None specified'
        
        # Format compliance list
        compliance_list = ', '.join(request.compliance) if request.compliance else 'None'
        
        # Create email body with all details
        email_body = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
        .section h3 {{ color: #667eea; margin-top: 0; }}
        .field {{ margin: 10px 0; }}
        .field strong {{ color: #555; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 2px solid #e5e7eb; font-size: 12px; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>🎯 New Client Integration Request</h2>
        <p>Submitted: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
    </div>
    
    <div class="section">
        <h3>📋 Client Information</h3>
        <div class="field"><strong>Company:</strong> {request.companyName}</div>
        <div class="field"><strong>Contact Person:</strong> {request.contactPerson}</div>
        <div class="field"><strong>Email:</strong> <a href="mailto:{request.email}">{request.email}</a></div>
        <div class="field"><strong>Phone:</strong> {request.phone or 'Not provided'}</div>
    </div>
    
    <div class="section">
        <h3>💻 Current Systems & Tools</h3>
        <div class="field"><strong>Systems:</strong> {systems_list}</div>
        <div class="field"><strong>Details:</strong> {request.systemDetails or 'Not provided'}</div>
    </div>
    
    <div class="section">
        <h3>🌐 Website & Hosting</h3>
        <div class="field"><strong>Website URL:</strong> <a href="{request.websiteUrl}" target="_blank">{request.websiteUrl}</a></div>
        <div class="field"><strong>Platform:</strong> {request.websitePlatform or 'Not specified'}</div>
        <div class="field"><strong>Hosting Provider:</strong> {request.hostingProvider or 'Not specified'}</div>
        <div class="field"><strong>Admin Access:</strong> {request.adminAccess or 'Not specified'}</div>
    </div>
    
    <div class="section">
        <h3>🔌 API & Integration Requirements</h3>
        <div class="field"><strong>Systems needing API integration:</strong> {request.apiSystems or 'Not specified'}</div>
        <div class="field"><strong>API Keys Available:</strong> {request.apiAvailability or 'Not specified'}</div>
        <div class="field"><strong>CRM System:</strong> {request.crmSystem or 'None'}</div>
        <div class="field"><strong>CRM API Docs:</strong> {request.crmApiDocs or 'Not provided'}</div>
    </div>
    
    <div class="section">
        <h3>🎯 Business Requirements</h3>
        <div class="field"><strong>Features Needed:</strong> {features_list}</div>
        <div class="field"><strong>Additional Features:</strong> {request.additionalFeatures or 'None specified'}</div>
    </div>
    
    <div class="section">
        <h3>📚 Content & Data</h3>
        <div class="field"><strong>Existing Content:</strong> {request.existingContent or 'Not specified'}</div>
        <div class="field"><strong>Content Location:</strong> {request.contentLocation or 'Not specified'}</div>
        <div class="field"><strong>Customer Database:</strong> {request.customerDatabase or 'Not specified'}</div>
    </div>
    
    <div class="section">
        <h3>🔒 Security & Compliance</h3>
        <div class="field"><strong>Compliance Requirements:</strong> {compliance_list}</div>
        <div class="field"><strong>Privacy Requirements:</strong> {request.privacyRequirements or 'None specified'}</div>
    </div>
    
    <div class="section">
        <h3>⚙️ Technical Contact & Timeline</h3>
        <div class="field"><strong>Technical Contact:</strong> {request.technicalContactName or 'Not provided'}</div>
        <div class="field"><strong>Technical Email:</strong> {request.technicalContactEmail or 'Not provided'}</div>
        <div class="field"><strong>Preferred Timeline:</strong> {request.timeline or 'Not specified'}</div>
    </div>
    
    <div class="section">
        <h3>📝 Additional Information</h3>
        <div class="field">{request.additionalInfo or 'None provided'}</div>
    </div>
    
    <div class="footer">
        <p>This integration request was submitted via the 4D Gaming client integration form.</p>
        <p>Complete data in JSON format attached below for your records.</p>
    </div>
    
    <details style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
        <summary style="cursor: pointer; font-weight: bold; color: #667eea;">Click to view JSON data</summary>
        <pre style="background: #1e293b; color: #e5e7eb; padding: 15px; border-radius: 5px; overflow-x: auto; margin-top: 10px;">{json.dumps(request.dict(), indent=2)}</pre>
    </details>
</body>
</html>
"""
        
        # Send email via Resend
        params = {
            "from": "Integration Form <4dgaming.games>",  # Update with your verified domain
            "to": ["legaltech@4dgaming.games"],  # Your email
            "subject": f"🎯 New Integration Request - {request.companyName}",
            "html": email_body,
        }
        
        email_response = resend.Emails.send(params)
        
        print(f"Integration email sent successfully!")
        print(f"Email ID: {email_response.get('id')}")
        print(f"Company: {request.companyName}")
        print(f"Contact: {request.contactPerson} ({request.email})")
        print(f"Systems: {systems_list}")
        print(f"Features needed: {features_list}")
        
        return {
            "success": True,
            "message": "Integration information sent successfully",
            "email_id": email_response.get('id'),
            "company": request.companyName,
            "contact": request.contactPerson
        }
        
    except Exception as e:
        import traceback
        print(f"Error sending integration info email: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send integration information: {str(e)}"
        )