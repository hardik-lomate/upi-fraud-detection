"""
Case Management System — Lightweight fraud investigation workflow.

Analysts can escalate transactions to cases, assign to themselves, add notes
with timestamps, and close with resolution. Backed by SQLite.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from .database import Base, SessionLocal, engine

router = APIRouter(prefix="/cases", tags=["Case Management"])


# ==========================================
# DB Model
# ==========================================

class CaseRecord(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    txn_id = Column(String(64), index=True)
    status = Column(String(32), default="OPEN")
    assigned_to = Column(String(128), nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


def init_cases_table():
    """Create cases table if it doesn't exist."""
    CaseRecord.__table__.create(bind=engine, checkfirst=True)


# ==========================================
# Request/Response Models
# ==========================================

VALID_STATUSES = ("OPEN", "UNDER_REVIEW", "CLOSED_FRAUD", "CLOSED_LEGITIMATE")


class CreateCaseRequest(BaseModel):
    txn_id: str = Field(..., description="Transaction ID to create a case for")
    assigned_to: Optional[str] = Field(None, description="Analyst name or ID")
    notes: Optional[str] = Field("", description="Initial notes")


class UpdateCaseRequest(BaseModel):
    status: Optional[Literal["OPEN", "UNDER_REVIEW", "CLOSED_FRAUD", "CLOSED_LEGITIMATE"]] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None


class CaseResponse(BaseModel):
    id: int
    txn_id: str
    status: str
    assigned_to: Optional[str]
    notes: str
    created_at: str
    resolved_at: Optional[str]


def _to_response(record: CaseRecord) -> dict:
    return {
        "id": record.id,
        "txn_id": record.txn_id,
        "status": record.status,
        "assigned_to": record.assigned_to,
        "notes": record.notes or "",
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
    }


# ==========================================
# Endpoints
# ==========================================

@router.post("", summary="Create a new case from a transaction", response_model=CaseResponse)
def create_case(req: CreateCaseRequest):
    db = SessionLocal()
    try:
        case = CaseRecord(
            txn_id=req.txn_id,
            status="OPEN",
            assigned_to=req.assigned_to,
            notes=req.notes or "",
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return _to_response(case)
    finally:
        db.close()


@router.get("", summary="List all cases with optional filters")
def list_cases(
    status: Optional[str] = Query(None, description="Filter by status"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    limit: int = Query(50, ge=1, le=200),
):
    db = SessionLocal()
    try:
        q = db.query(CaseRecord)
        if status:
            q = q.filter(CaseRecord.status == status)
        if assigned_to:
            q = q.filter(CaseRecord.assigned_to == assigned_to)
        records = q.order_by(CaseRecord.id.desc()).limit(limit).all()
        return {
            "cases": [_to_response(r) for r in records],
            "total": len(records),
        }
    finally:
        db.close()


@router.get("/{case_id}", summary="Get a single case by ID", response_model=CaseResponse)
def get_case(case_id: int):
    db = SessionLocal()
    try:
        record = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        return _to_response(record)
    finally:
        db.close()


@router.patch("/{case_id}", summary="Update case status, assignee, or add notes", response_model=CaseResponse)
def update_case(case_id: int, req: UpdateCaseRequest):
    db = SessionLocal()
    try:
        record = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

        if req.status is not None:
            record.status = req.status
            if req.status.startswith("CLOSED"):
                record.resolved_at = datetime.utcnow()

        if req.assigned_to is not None:
            record.assigned_to = req.assigned_to

        if req.notes is not None:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            if record.notes:
                record.notes = f"{record.notes}\n[{timestamp}] {req.notes}"
            else:
                record.notes = f"[{timestamp}] {req.notes}"

        db.commit()
        db.refresh(record)
        return _to_response(record)
    finally:
        db.close()


@router.delete("/{case_id}", summary="Close/delete a case")
def delete_case(case_id: int):
    db = SessionLocal()
    try:
        record = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        record.status = "CLOSED_LEGITIMATE"
        record.resolved_at = datetime.utcnow()
        db.commit()
        return {"status": "closed", "case_id": case_id}
    finally:
        db.close()
