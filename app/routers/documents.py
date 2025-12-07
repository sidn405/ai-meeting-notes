# backend/app/routers/documents.py
"""
API routes for generating proposals and invoices for LawBot 360
Fixed authentication with proper JWT handling
"""

from fastapi import APIRouter, Depends, HTTPException, status, Cookie
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import os
from pathlib import Path
from starlette.requests import Request

# Import your PDF generator
from app.utils.lawbot_proposal_generator import create_proposal_pdf, create_invoice_pdf

# JWT handling
from jose import jwt, JWTError

# Import your existing auth
from app.security import COOKIE_NAME
from app.portal_db import PortalUser, get_session
from sqlmodel import Session, select

router = APIRouter(prefix="/api/admin", tags=["documents"])


# ============================================================================
# Auth using your existing session system - FIXED VERSION
# ============================================================================

async def get_current_admin_user(
    request: Request,
    session_token: Optional[str] = Cookie(None, alias=COOKIE_NAME),
    db: Session = Depends(get_session)
):
    """
    Check if user is authenticated and is admin
    Uses your existing cookie-based JWT auth system
    """
    # Get token from cookie first
    token = session_token
    
    # If no cookie, try Authorization header
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - no token found"
        )
    
    try:
        # Get JWT secret from environment
        secret = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
        
        # Decode JWT token to get user_id
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        user_id_str = payload.get("sub")
        
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token - no user ID"
            )
        
        # Convert user_id from string to int
        user_id = int(user_id_str)
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token"
        )
    
    # Get user from database
    user = db.exec(select(PortalUser).where(PortalUser.id == user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return user


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
    milestone: str
    amount: float
    total_project_cost: float
    payment_link: Optional[str] = None
    project_id: Optional[int] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/generate-proposal")
async def generate_proposal(
    request: ProposalRequest,
    current_user: PortalUser = Depends(get_current_admin_user)
):
    """
    Generate a professional proposal PDF
    Requires admin authentication
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
        
        # If project_id provided, attach to project
        if request.project_id:
            # TODO: Add database logic to attach PDF to project
            pass
        
        # Return file URL
        pdf_url = f"/static/proposals/{filename}"
        
        return {
            "success": True,
            "message": "Proposal generated successfully",
            "pdf_url": pdf_url,
            "filename": filename,
            "proposal_number": request.proposal_number,
            "generated_by": current_user.email
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
async def generate_invoice(
    request: InvoiceRequest,
    current_user: PortalUser = Depends(get_current_admin_user)
):
    """
    Generate a professional invoice PDF
    Requires admin authentication
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
            pass
        
        # Return file URL
        pdf_url = f"/static/invoices/{filename}"
        
        return {
            "success": True,
            "message": "Invoice generated successfully",
            "pdf_url": pdf_url,
            "filename": filename,
            "invoice_number": request.invoice_number,
            "amount": request.amount,
            "generated_by": current_user.email
        }
        
    except Exception as e:
        import traceback
        print(f"Error generating invoice: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invoice: {str(e)}"
        )


@router.get("/test-auth")
async def test_auth(current_user: PortalUser = Depends(get_current_admin_user)):
    """
    Test endpoint to verify authentication is working
    """
    return {
        "success": True,
        "authenticated": True,
        "user_id": current_user.id,
        "email": current_user.email,
        "is_admin": current_user.is_admin
    }


@router.get("/projects")
async def get_projects(
    current_user: PortalUser = Depends(get_current_admin_user)
):
    """
    Get all projects for dropdown selection
    TODO: Replace with actual database query
    """
    # TODO: Query your actual projects table
    # Example:
    # from app.models import Project
    # projects = db.exec(select(Project)).all()
    # return [{"id": p.id, "project_name": p.name, ...} for p in projects]
    
    # Placeholder return
    return [
        {
            "id": 1,
            "project_name": "Sample Project",
            "client_name": "Test Client",
            "contact_name": "John Doe",
            "contact_email": "john@example.com"
        }
    ]


@router.get("/project-documents/{project_id}")
async def get_project_documents(
    project_id: int,
    current_user: PortalUser = Depends(get_current_admin_user)
):
    """
    Get all documents (proposals, invoices) for a specific project
    """
    try:
        documents = []
        
        # Check proposals directory
        proposals_dir = Path("static/proposals")
        if proposals_dir.exists():
            for file in proposals_dir.glob("*.pdf"):
                # You can add logic to filter by project_id if stored in filename or database
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
async def delete_document(
    file_type: str,
    filename: str,
    current_user: PortalUser = Depends(get_current_admin_user)
):
    """
    Delete a document (proposal or invoice)
    Requires admin authentication
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
async def download_pdf(
    file_type: str,
    filename: str,
    current_user: PortalUser = Depends(get_current_admin_user)
):
    """
    Download a generated PDF (proposal or invoice)
    Requires admin authentication
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