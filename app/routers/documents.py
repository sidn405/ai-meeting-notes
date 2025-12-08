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
    Save client system integration information
    Stores data in JSON file for now - can be moved to database later
    """
    try:
        import json
        
        # Create directory for integration info if it doesn't exist
        integration_dir = Path("static/integration-info")
        integration_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename based on company name and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company_name = "".join(c for c in request.companyName if c.isalnum() or c in (' ', '-', '_')).replace(' ', '_')
        filename = f"{safe_company_name}_{timestamp}.json"
        filepath = integration_dir / filename
        
        # Convert request to dict and save
        data = request.dict()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Integration info saved: {filepath}")
        print(f"Company: {request.companyName}")
        print(f"Contact: {request.contactPerson} ({request.email})")
        print(f"Systems: {', '.join(request.systems) if request.systems else 'None specified'}")
        print(f"Features needed: {', '.join(request.features) if request.features else 'None specified'}")
        
        return {
            "success": True,
            "message": "Integration information saved successfully",
            "filename": filename,
            "company": request.companyName,
            "contact": request.contactPerson
        }
        
    except Exception as e:
        import traceback
        print(f"Error saving integration info: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save integration information: {str(e)}"
        )