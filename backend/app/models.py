"""Pydantic models — enriched with descriptions and examples for OpenAPI docs."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


VALID_TXN_TYPES = ("purchase", "transfer", "bill_payment", "recharge")


class TransactionRequest(BaseModel):
    """A single UPI transaction to be analyzed for fraud."""
    transaction_id: Optional[str] = Field(None, description="Optional ID. Auto-generated if omitted.")
    sender_upi: str = Field(..., min_length=3, description="Sender's UPI ID", examples=["user123@upi"])
    receiver_upi: str = Field(..., min_length=3, description="Receiver's UPI ID", examples=["merchant456@upi"])
    amount: float = Field(..., gt=0, le=500000, description="Transaction amount in INR (₹1 to ₹5,00,000)")
    timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp. Auto-set to now if omitted.")
    sender_device_id: str = Field(..., min_length=1, description="Device fingerprint", examples=["DEV_ABC123"])
    sender_ip: Optional[str] = Field(None, description="Sender's IP address for geo-analysis")
    transaction_type: Literal["purchase", "transfer", "bill_payment", "recharge"] = Field(
        "purchase", description="Type of UPI transaction"
    )
    sender_location_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    sender_location_lon: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")

    model_config = {
        "json_schema_extra": {
            "example": {
                "sender_upi": "alice@upi",
                "receiver_upi": "merchant@upi",
                "amount": 2499.99,
                "transaction_type": "purchase",
                "sender_device_id": "IPHONE14_XYZ",
            }
        }
    }


class RuleDetail(BaseModel):
    rule_name: str = Field(..., description="Rule identifier e.g. SELF_TRANSFER")
    reason: str = Field(..., description="Human-readable explanation")
    action: str = Field(..., description="BLOCK or FLAG")


class DeviceAnomaly(BaseModel):
    type: str = Field(..., description="IMPOSSIBLE_TRAVEL, NEW_DEVICE, IP_MISMATCH")
    severity: str = Field(..., description="HIGH, MEDIUM, LOW")
    detail: str = Field(..., description="Human-readable detail")


class GraphInfo(BaseModel):
    out_degree: int = Field(0, description="Number of unique receivers")
    in_degree: int = Field(0, description="Number of unique senders to this account")
    pagerank: float = Field(0.0, description="PageRank centrality score")
    is_hub: bool = Field(False, description="True if account is a high-degree hub")
    is_mule_suspect: bool = Field(False, description="True if account shows mule patterns")
    cycle_count: int = Field(0, description="Number of cycles involving this account")


class RiskBreakdown(BaseModel):
    behavioral: float = Field(0.0, ge=0, le=100, description="Behavioral risk 0-100")
    temporal: float = Field(0.0, ge=0, le=100, description="Time-of-day risk 0-100")
    network: float = Field(0.0, ge=0, le=100, description="Network topology risk 0-100")
    device: float = Field(0.0, ge=0, le=100, description="Device anomaly risk 0-100")


class PredictionResponse(BaseModel):
    """Full prediction result with ML scores, rules, SHAP explanations, and risk breakdown."""
    transaction_id: str
    fraud_score: float = Field(..., ge=0.0, le=1.0,
        description="Ensemble fraud probability. XGBoost(45%) + LightGBM(35%) + IsoForest(20%)")
    decision: str = Field(..., description="ALLOW, FLAG, or BLOCK")
    risk_level: str = Field(..., description="LOW, MEDIUM, or HIGH")
    message: str = Field(..., description="Human-readable decision explanation")
    reasons: list[str] = Field(default=[], description="Top SHAP-based risk factors")
    individual_scores: dict = Field(default={}, description="Per-model fraud scores")
    models_used: list[str] = Field(default=[], description="Models that contributed to this prediction")
    rules_triggered: list[RuleDetail] = Field(default=[], description="Pre-ML rules that fired")
    device_anomalies: list[DeviceAnomaly] = Field(default=[], description="Device/geo anomalies detected")
    graph_info: Optional[GraphInfo] = Field(None, description="Network analysis results")
    risk_breakdown: Optional[RiskBreakdown] = Field(None, description="Multi-dimensional risk scores")
    model_version: str = Field("2.0.0", description="Model version used for this prediction")

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_id": "TXN_20260403_a1b2c3",
                "fraud_score": 0.15,
                "decision": "ALLOW",
                "risk_level": "LOW",
                "message": "Transaction appears legitimate (15.0%). Approved.",
                "models_used": ["xgboost", "lightgbm", "isolation_forest"],
                "model_version": "2.0.0",
            }
        }
    }


class TokenRequest(BaseModel):
    api_key: str = Field(..., description="Your API key from api_keys.json")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24


class FeedbackRequest(BaseModel):
    """Analyst feedback for a specific transaction — feeds into retraining pipeline."""
    transaction_id: str = Field(..., description="Transaction to label")
    analyst_verdict: Literal["confirmed_fraud", "false_positive", "true_negative"] = Field(
        ..., description="Analyst's assessment"
    )
    analyst_notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class BatchPredictSummary(BaseModel):
    total_processed: int
    blocked_count: int
    flagged_count: int
    allowed_count: int
    processing_time_ms: float
    high_risk_transactions: list[dict] = []
