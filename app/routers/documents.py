# backend/app/routers/documents.py
"""
API routes for generating proposals and invoices for LawBot 360
Simplified version without authentication (since admin portal already requires auth)
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from pathlib import Path

# Import your PDF generator
from app.utils.lawbot_proposal_generator import create_proposal_pdf, create_invoice_pdf

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


# ============================================================================
# API Endpoints (No Auth Required - Admin Portal Already Authenticated)
# ============================================================================

@router.post("/generate-proposal")
async def generate_proposal(request: ProposalRequest):
    """
    Generate a professional proposal PDF
    No auth required since admin portal is already authenticated
    """
    try:
        # Create directory for proposals if it doesn't exist
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
            'maintenance_tier': request.maintenance_tier,
        }
        
        # Generate PDF using the fixed generator
        create_proposal_pdf(str(filepath), proposal_data)
        
        # Return file URL
        pdf_url = f"/static/proposals/{filename}"
        
        return {
            "success": True,
            "message": "Proposal generated successfully",
            "pdf_url": pdf_url,
            "filename": filename,
            "proposal_number": request.proposal_number
        }
        
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
    Generate a professional invoice PDF
    No auth required since admin portal is already authenticated
    """
    try:
        # Create directory for invoices if it doesn't exist
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
        
        # Return file URL
        pdf_url = f"/static/invoices/{filename}"
        
        return {
            "success": True,
            "message": "Invoice generated successfully",
            "pdf_url": pdf_url,
            "filename": filename,
            "invoice_number": request.invoice_number,
            "amount": request.amount
        }
        
    except Exception as e:
        import traceback
        print(f"Error generating invoice: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invoice: {str(e)}"
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
                    "url": f"/static/proposals/{file.name}"
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
                    "url": f"/static/invoices/{file.name}"
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
    Delete a document (proposal or invoice)
    """
    if file_type not in ["proposals", "invoices"]:
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
    Download a generated PDF (proposal or invoice)
    """
    if file_type not in ["proposals", "invoices"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    filepath = Path(f"static/{file_type}/{filename}")
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf"
    )


@router.get("/projects")
async def get_projects():
    """
    Get all projects for dropdown selection
    Returns empty list for now - implement when needed
    """
    # TODO: Query your actual projects table
    # Example:
    # from app.models import Project
    # from app.portal_db import get_session
    # db = next(get_session())
    # projects = db.exec(select(Project)).all()
    # return [{"id": p.id, "project_name": p.name, ...} for p in projects]
    
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
            "/api/admin/generate-proposal",
            "/api/admin/generate-invoice",
            "/api/admin/project-documents/{project_id}",
            "/api/admin/download/{file_type}/{filename}"
        ]
    }