"""
Feedback Loop — analyst verdict collection for model retraining.
"""

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .database import Base, SessionLocal, engine


class FeedbackRecord(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(64), index=True)
    analyst_verdict = Column(String(32))  # confirmed_fraud, false_positive, true_negative
    analyst_notes = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# Create table if not exists
Base.metadata.create_all(bind=engine)


def save_feedback(transaction_id: str, verdict: str, notes: str = ""):
    db = SessionLocal()
    try:
        record = FeedbackRecord(
            transaction_id=transaction_id,
            analyst_verdict=verdict,
            analyst_notes=notes,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()


def get_feedback_stats() -> dict:
    db = SessionLocal()
    try:
        total = db.query(FeedbackRecord).count()
        if total == 0:
            return {"total_reviewed": 0, "message": "No feedback submitted yet"}

        confirmed = db.query(FeedbackRecord).filter(FeedbackRecord.analyst_verdict == "confirmed_fraud").count()
        false_pos = db.query(FeedbackRecord).filter(FeedbackRecord.analyst_verdict == "false_positive").count()
        true_neg = db.query(FeedbackRecord).filter(FeedbackRecord.analyst_verdict == "true_negative").count()

        return {
            "total_reviewed": total,
            "confirmed_fraud": confirmed,
            "false_positive": false_pos,
            "true_negative": true_neg,
            "confirmed_fraud_rate": round(confirmed / total, 4) if total else 0,
            "false_positive_rate": round(false_pos / total, 4) if total else 0,
        }
    finally:
        db.close()
