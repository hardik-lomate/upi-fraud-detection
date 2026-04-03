from pydantic import BaseModel, Field
from typing import Optional, Literal


VALID_TXN_TYPES = ("purchase", "transfer", "bill_payment", "recharge")


class TransactionRequest(BaseModel):
    transaction_id: Optional[str] = None
    sender_upi: str = Field(..., min_length=3, examples=["user123@upi"])
    receiver_upi: str = Field(..., min_length=3, examples=["merchant456@upi"])
    amount: float = Field(..., gt=0, le=500000, description="Transaction amount in INR")
    timestamp: Optional[str] = None
    sender_device_id: str = Field(..., min_length=1, examples=["DEV_ABC123"])
    sender_ip: Optional[str] = None
    transaction_type: Literal["purchase", "transfer", "bill_payment", "recharge"] = "purchase"
    sender_location_lat: Optional[float] = Field(None, ge=-90, le=90)
    sender_location_lon: Optional[float] = Field(None, ge=-180, le=180)


class RuleDetail(BaseModel):
    rule_name: str
    reason: str
    action: str


class DeviceAnomaly(BaseModel):
    type: str
    severity: str
    detail: str


class GraphInfo(BaseModel):
    out_degree: int = 0
    in_degree: int = 0
    pagerank: float = 0.0
    is_hub: bool = False
    is_mule_suspect: bool = False
    cycle_count: int = 0


class PredictionResponse(BaseModel):
    transaction_id: str
    fraud_score: float
    decision: str
    risk_level: str
    message: str
    # Industry-grade additions
    reasons: list[str] = []
    individual_scores: dict = {}
    models_used: list[str] = []
    rules_triggered: list[RuleDetail] = []
    device_anomalies: list[DeviceAnomaly] = []
    graph_info: Optional[GraphInfo] = None
    model_version: str = "1.0.0"


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24
