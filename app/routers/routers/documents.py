# backend/app/routers/documents.py
"""
API routes for generating proposals and invoices for LawBot 360
Add this to your FastAPI backend
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import os
from pathlib import Path

# Import your PDF generator
from ..utils.lawbot_pdf_generator import create_proposal_pdf, create_invoice_pdf
# Import your auth dependencies
from ..dependencies import get_current_admin_user

router = APIRouter(prefix="/api/admin", tags=["documents"])

# Pydantic models for request validation
class ProposalRequest(BaseModel):
    proposal_number: str
    firm_name: str
    contact_name: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    practice_areas: List[str]
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
    milestone: str
    amount: float
    total_project_cost: float
    payment_link: Optional[str] = None
    project_id: Optional[int] = None


@router.post("/generate-proposal")
async def generate_proposal(
    request: ProposalRequest,
    current_user = Depends(get_current_admin_user)
):
    """
    Generate a professional proposal PDF for LawBot 360
    """
    try:
        # Create directory for proposals if it doesn't exist
        proposals_dir = Path("static/proposals")
        proposals_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        firm_slug = request.firm_name.replace(" ", "_").replace("&", "and")[:30]
        filename = f"LawBot360_Proposal_{firm_slug}_{timestamp}.pdf"
        filepath = proposals_dir / filename
        
        # Prepare data for PDF generator
        proposal_data = {
            'proposal_number': request.proposal_number,
            'firm_name': request.firm_name,
            'contact_name': request.contact_name,
            'contact_email': request.contact_email,
            'contact_phone': request.contact_phone,
            'practice_areas': request.practice_areas,
            'current_intake_method': request.current_intake_method,
            'pain_points': request.pain_points,
            'monthly_inquiries': request.monthly_inquiries,
            'integration_needs': request.integration_needs,
            'custom_features': request.custom_features,
            'total_price': request.total_price,
            'timeline_weeks': request.timeline_weeks,
            'maintenance_tier': request.maintenance_tier,
        }
        
        # Generate PDF
        create_proposal_pdf(str(filepath), proposal_data)
        
        # If project_id provided, attach to project
        if request.project_id:
            # TODO: Add database logic to attach PDF to project
            # Example:
            # await db.execute(
            #     "INSERT INTO project_files (project_id, file_path, file_type) VALUES (?, ?, ?)",
            #     (request.project_id, str(filepath), "proposal")
            # )
            pass
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate proposal: {str(e)}"
        )


@router.post("/generate-invoice")
async def generate_invoice(
    request: InvoiceRequest,
    current_user = Depends(get_current_admin_user)
):
    """
    Generate a professional invoice PDF for LawBot 360
    """
    try:
        # Create directory for invoices if it doesn't exist
        invoices_dir = Path("static/invoices")
        invoices_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        firm_slug = request.firm_name.replace(" ", "_").replace("&", "and")[:30]
        filename = f"LawBot360_Invoice_{request.invoice_number}_{firm_slug}_{timestamp}.pdf"
        filepath = invoices_dir / filename
        
        # Prepare data for PDF generator
        invoice_data = {
            'invoice_number': request.invoice_number,
            'firm_name': request.firm_name,
            'contact_name': request.contact_name,
            'contact_email': request.contact_email,
            'project_name': request.project_name,
            'milestone': request.milestone,
            'amount': request.amount,
            'total_project_cost': request.total_project_cost,
            'payment_link': request.payment_link,
        }
        
        # Generate PDF
        create_invoice_pdf(str(filepath), invoice_data)
        
        # If project_id provided, attach to project
        if request.project_id:
            # TODO: Add database logic to attach PDF to project
            # Example:
            # await db.execute(
            #     "INSERT INTO project_files (project_id, file_path, file_type) VALUES (?, ?, ?)",
            #     (request.project_id, str(filepath), "invoice")
            # )
            pass
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invoice: {str(e)}"
        )


@router.get("/projects")
async def get_projects(
    current_user = Depends(get_current_admin_user)
):
    """
    Get all projects for dropdown selection
    This is a placeholder - implement with your actual database
    """
    # TODO: Replace with actual database query
    # Example:
    # projects = await db.fetch_all("SELECT id, project_name, client_name, contact_name, contact_email FROM projects")
    # return projects
    
    # Placeholder return
    return [
        {
            "id": 1,
            "project_name": "LawBot 360 - Smith & Associates",
            "client_name": "Smith & Associates Law Firm",
            "contact_name": "John Smith",
            "contact_email": "john@smithlaw.com"
        }
    ]


# Helper endpoint to download generated PDFs
@router.get("/download/{file_type}/{filename}")
async def download_pdf(
    file_type: str,
    filename: str,
    current_user = Depends(get_current_admin_user)
):
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