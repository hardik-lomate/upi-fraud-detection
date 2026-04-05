import os

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fraud_detection.db")
# PostgreSQL example: "postgresql://user:password@localhost:5432/fraud_db"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# Transaction States (spec-aligned)
# ==========================================
# ALLOWED               - passed all checks, approved
# BLOCKED               - blocked by rules/ML or biometric failure
# PENDING_VERIFICATION  - step-up auth required, waiting for biometric verification
# VERIFIED              - biometric passed, transaction approved


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String(64), unique=True, index=True)
    sender_upi = Column(String(64), index=True)
    receiver_upi = Column(String(64))
    amount = Column(Float)
    fraud_score = Column(Float)
    decision = Column(String(20))  # ALLOW, BLOCK, VERIFY
    status = Column(String(32), default="ALLOWED")  # ALLOWED, BLOCKED, PENDING_VERIFICATION, VERIFIED
    device_id = Column(String(64), default="")
    timestamp = Column(String(32))
    response_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FraudHistory(Base):
    """Per-user fraud history for step-up authentication decisions."""
    __tablename__ = "fraud_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upi_id = Column(String(64), unique=True, index=True)
    fraud_count = Column(Integer, default=0)  # times flagged/blocked
    block_count = Column(Integer, default=0)  # times fully blocked
    is_flagged = Column(Boolean, default=False)  # currently flagged as risky
    last_fraud_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)

    # Lightweight schema migration (SQLite): add response_json if missing.
    # This enables deterministic idempotent reads of the full API response.
    if DATABASE_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(transactions)").fetchall()]
                if "response_json" not in cols:
                    conn.exec_driver_sql("ALTER TABLE transactions ADD COLUMN response_json TEXT")
        except Exception as e:
            logger.warning(f"DB migration skipped/failed: {e}")

    # Lightweight value migration for demo stability
    db = SessionLocal()
    try:
        db.query(TransactionRecord).filter(TransactionRecord.status == "PENDING_BIOMETRIC").update(
            {TransactionRecord.status: "PENDING_VERIFICATION"}, synchronize_session=False
        )
        db.query(TransactionRecord).filter(TransactionRecord.status == "BIOMETRIC_FAILED").update(
            {TransactionRecord.status: "BLOCKED"}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    print("Database initialized")


def save_transaction(
    txn_id,
    sender,
    receiver,
    amount,
    fraud_score,
    decision,
    timestamp,
    device_id="",
    status=None,
    response_json: Optional[str] = None,
):
    db = SessionLocal()
    try:
        # Determine status from decision if not explicitly set
        if status is None:
            if decision == "VERIFY":
                status = "PENDING_VERIFICATION"
            elif decision == "BLOCK":
                status = "BLOCKED"
            else:
                status = "ALLOWED"
        record = TransactionRecord(
            transaction_id=txn_id,
            sender_upi=sender,
            receiver_upi=receiver,
            amount=amount,
            fraud_score=fraud_score,
            decision=decision,
            status=status,
            device_id=device_id,
            timestamp=timestamp,
            response_json=response_json,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Idempotency: update existing row
            existing = db.query(TransactionRecord).filter(TransactionRecord.transaction_id == txn_id).first()
            if existing:
                existing.sender_upi = sender
                existing.receiver_upi = receiver
                existing.amount = amount
                existing.fraud_score = fraud_score
                existing.decision = decision
                existing.status = status
                existing.device_id = device_id
                existing.timestamp = timestamp
                existing.response_json = response_json
                db.commit()
    finally:
        db.close()


def get_transaction_by_id(txn_id: str) -> Optional[dict]:
    db = SessionLocal()
    try:
        r = db.query(TransactionRecord).filter(TransactionRecord.transaction_id == txn_id).first()
        if not r:
            return None
        return {
            "transaction_id": r.transaction_id,
            "sender_upi": r.sender_upi,
            "receiver_upi": r.receiver_upi,
            "amount": r.amount,
            "fraud_score": r.fraud_score,
            "decision": r.decision,
            "status": r.status,
            "timestamp": r.timestamp,
            "device_id": r.device_id or "",
            "response_json": r.response_json,
        }
    finally:
        db.close()


def update_transaction_status(txn_id: str, new_status: str, new_decision: str = None):
    """Update transaction status after biometric verification."""
    db = SessionLocal()
    try:
        record = db.query(TransactionRecord).filter(
            TransactionRecord.transaction_id == txn_id
        ).first()
        if record:
            record.status = new_status
            if new_decision:
                record.decision = new_decision
            db.commit()
            return True
        return False
    finally:
        db.close()


def get_transactions(limit=50):
    db = SessionLocal()
    try:
        records = (
            db.query(TransactionRecord)
            .order_by(TransactionRecord.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "transaction_id": r.transaction_id,
                "sender_upi": r.sender_upi,
                "receiver_upi": r.receiver_upi,
                "amount": r.amount,
                "fraud_score": r.fraud_score,
                "decision": r.decision,
                "status": r.status or r.decision,
                "timestamp": r.timestamp,
            }
            for r in records
        ]
    finally:
        db.close()


def load_recent_history(days: int = 7) -> list:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        records = (
            db.query(TransactionRecord)
            .filter(TransactionRecord.created_at >= cutoff)
            .order_by(TransactionRecord.id.asc())
            .all()
        )
        return [
            {
                "sender_upi": r.sender_upi,
                "receiver_upi": r.receiver_upi,
                "amount": r.amount,
                "device_id": r.device_id or "",
                "timestamp": r.timestamp,
            }
            for r in records
        ]
    finally:
        db.close()


def count_recent_sender_transactions(sender_upi: str, seconds: int = 60) -> int:
    """Count how many transactions this sender initiated in the last N seconds.

    Uses DB arrival time (created_at) so it reflects real-time velocity, and it
    remains persistent across backend restarts.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=seconds)
        return (
            db.query(TransactionRecord)
            .filter(TransactionRecord.sender_upi == sender_upi)
            .filter(TransactionRecord.created_at >= cutoff)
            .count()
        )
    finally:
        db.close()


# ==========================================
# Fraud History Helpers
# ==========================================

def get_user_fraud_history(upi_id: str) -> dict:
    """Get fraud history for a user. Returns dict with fraud_count, is_flagged, etc."""
    db = SessionLocal()
    try:
        record = db.query(FraudHistory).filter(FraudHistory.upi_id == upi_id).first()
        if record:
            return {
                "upi_id": record.upi_id,
                "fraud_count": record.fraud_count,
                "block_count": record.block_count,
                "is_flagged": record.is_flagged,
                "last_fraud_at": record.last_fraud_at.isoformat() if record.last_fraud_at else None,
            }
        return {"upi_id": upi_id, "fraud_count": 0, "block_count": 0, "is_flagged": False, "last_fraud_at": None}
    finally:
        db.close()


def increment_fraud_count(upi_id: str, was_blocked: bool = False):
    """Increment fraud count for a user when flagged or blocked."""
    db = SessionLocal()
    try:
        record = db.query(FraudHistory).filter(FraudHistory.upi_id == upi_id).first()
        if not record:
            record = FraudHistory(upi_id=upi_id, fraud_count=0, block_count=0, is_flagged=False)
            db.add(record)
            db.flush()  # ensure defaults are populated before += 
        record.fraud_count = (record.fraud_count or 0) + 1
        if was_blocked:
            record.block_count = (record.block_count or 0) + 1
        if record.fraud_count >= 3:
            record.is_flagged = True
        record.last_fraud_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def get_flagged_users(limit: int = 50) -> list:
    """Get all flagged users for the monitoring panel."""
    db = SessionLocal()
    try:
        records = (
            db.query(FraudHistory)
            .filter(FraudHistory.fraud_count > 0)
            .order_by(FraudHistory.fraud_count.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "upi_id": r.upi_id,
                "fraud_count": r.fraud_count,
                "block_count": r.block_count,
                "is_flagged": r.is_flagged,
                "last_fraud_at": r.last_fraud_at.isoformat() if r.last_fraud_at else None,
            }
            for r in records
        ]
    finally:
        db.close()
