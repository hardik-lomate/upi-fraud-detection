from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

DATABASE_URL = "sqlite:///./fraud_detection.db"
# PostgreSQL example: "postgresql://user:password@localhost:5432/fraud_db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String(64), unique=True, index=True)
    sender_upi = Column(String(64), index=True)
    receiver_upi = Column(String(64))
    amount = Column(Float)
    fraud_score = Column(Float)
    decision = Column(String(10))
    device_id = Column(String(64), default="")
    timestamp = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialized")


def save_transaction(txn_id, sender, receiver, amount, fraud_score, decision, timestamp, device_id=""):
    db = SessionLocal()
    try:
        record = TransactionRecord(
            transaction_id=txn_id,
            sender_upi=sender,
            receiver_upi=receiver,
            amount=amount,
            fraud_score=fraud_score,
            decision=decision,
            device_id=device_id,
            timestamp=timestamp,
        )
        db.add(record)
        db.commit()
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
                "timestamp": r.timestamp,
            }
            for r in records
        ]
    finally:
        db.close()


def load_recent_history(days: int = 7) -> list:
    """
    Load recent transactions from DB for hydrating sender_history on startup.
    Returns list of dicts with sender, receiver, amount, device_id, timestamp.
    """
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
