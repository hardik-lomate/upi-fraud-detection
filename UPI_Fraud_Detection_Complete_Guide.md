# End-to-End Real-Time UPI Fraud Detection System

## Complete Build Documentation — Full Stack + Machine Learning

> **Audience:** Intermediate to advanced developers building a portfolio/hackathon project  
> **Stack:** React · FastAPI · XGBoost · PostgreSQL/SQLite · Python  
> **Cost:** 100% free and open-source tools  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Complete System Architecture](#2-complete-system-architecture)
3. [Tech Stack (100% Free)](#3-tech-stack-100-free)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Data Simulation](#5-data-simulation)
6. [Feature Engineering](#6-feature-engineering)
7. [Machine Learning Model](#7-machine-learning-model)
8. [Backend Development (FastAPI)](#8-backend-development-fastapi)
9. [Decision Engine](#9-decision-engine)
10. [Database Design](#10-database-design)
11. [Frontend UI (React)](#11-frontend-ui-react)
12. [Real-Time Simulation](#12-real-time-simulation)
13. [Optional Advanced (Kafka + Redis)](#13-optional-advanced-kafka--redis)
14. [Testing the System](#14-testing-the-system)
15. [Performance Optimization](#15-performance-optimization)
16. [Limitations](#16-limitations)
17. [Future Improvements](#17-future-improvements)
18. [Step-by-Step Build Plan](#18-step-by-step-build-plan)

---

## 1. Project Overview

### 1.1 Purpose

UPI (Unified Payments Interface) processes **billions of transactions monthly** in India. With this volume comes fraud — unauthorized transfers, SIM-swap attacks, phishing, and account takeovers. Banks and fintechs need systems that can score each transaction **in real-time** (under 100ms) and decide whether to allow, flag, or block it before money moves.

This project builds exactly that: a **complete, working fraud detection system** from scratch using only free tools.

### 1.2 System Goals

| Goal | Description |
|------|-------------|
| **Real-time scoring** | Every transaction gets a fraud probability score within 50–100ms |
| **Automated decisions** | Thresholds automatically allow, flag for review, or block transactions |
| **Full-stack UI** | React dashboard to submit transactions and view results |
| **ML-powered** | XGBoost model trained on realistic synthetic data |
| **Logged & auditable** | Every prediction is stored in a database for review |

### 1.3 How Real-Time Scoring Works (Simple)

```
User submits transaction → Backend receives JSON → Features are extracted
→ ML model predicts fraud probability (0.0 to 1.0) → Decision engine applies
thresholds → Result returned to user + logged to database
```

The entire flow completes in **under 100ms** on a modern laptop.

### 1.4 Final System Capabilities

When complete, you will have:
- A **React frontend** where you can fill in transaction details and get instant fraud scores
- A **FastAPI backend** that loads a trained XGBoost model and serves predictions
- A **trained ML model** with >90% AUC on synthetic data
- A **database** storing every transaction and its prediction
- A **simulation script** that fires continuous transactions for demo purposes

---

## 2. Complete System Architecture

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Transaction   │  │  Results     │  │  Transaction History  │  │
│  │ Form          │  │  Display     │  │  Table                │  │
│  └──────┬───────┘  └──────▲───────┘  └───────────▲───────────┘  │
│         │                 │                      │              │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │ POST /predict   │ JSON Response        │ GET /transactions
          ▼                 │                      │
┌─────────┼─────────────────┼──────────────────────┼──────────────┐
│         │           BACKEND (FastAPI)            │              │
│  ┌──────▼───────┐                                │              │
│  │  /predict    │──► Feature ──► ML Model ──► Decision          │
│  │  endpoint    │    Extract     (XGBoost)    Engine             │
│  └──────────────┘                    │           │              │
│                                      │     ┌─────▼─────┐       │
│                                      │     │  /transactions    │
│                                      │     │  endpoint  │       │
│                                      │     └───────────┘       │
└──────────────────────────────────────┼─────────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │   DATABASE      │
                              │ (PostgreSQL /   │
                              │  SQLite)        │
                              │                 │
                              │ transactions    │
                              │ predictions     │
                              └─────────────────┘
```

### 2.2 Data Flow

1. **User** fills out a transaction form in the React UI (amount, sender, receiver, etc.)
2. **Frontend** sends a `POST /predict` request with JSON payload to FastAPI
3. **Backend** extracts features from the raw transaction data
4. **ML Model** (pre-trained XGBoost) returns a fraud probability score (0.0–1.0)
5. **Decision Engine** classifies the transaction: `ALLOW`, `FLAG`, or `BLOCK`
6. **Database** stores the transaction, score, and decision
7. **Response** is sent back to the frontend with the result
8. **UI** displays the risk score, decision, and color-coded alert

---

## 3. Tech Stack (100% Free)

| Layer | Technology | Why This Choice |
|-------|-----------|-----------------|
| **Frontend** | React.js 18+ | Industry standard, component-based, massive ecosystem |
| **Backend** | FastAPI (Python) | Async, automatic OpenAPI docs, fast, Pythonic |
| **ML Framework** | XGBoost + scikit-learn | Best-in-class for tabular data, fast inference |
| **Database** | SQLite (dev) / PostgreSQL (prod) | Zero-config (SQLite) or robust (Postgres), both free |
| **Data Processing** | Pandas, NumPy | De facto standards for data manipulation in Python |
| **Model Serialization** | joblib | Fast save/load for sklearn-compatible models |
| **HTTP Client** | Axios (frontend), requests (Python) | Simple, reliable HTTP libraries |
| **Optional: Cache** | Redis | In-memory feature store for sub-ms lookups |
| **Optional: Streaming** | Apache Kafka | Real-time event streaming for production scale |

### Prerequisites

```bash
# Python 3.9+
python --version

# Node.js 18+
node --version

# pip and npm
pip --version
npm --version
```

---

## 4. Project Folder Structure

```
upi_fraud_detection/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── models.py            # Pydantic request/response models
│   │   ├── predict.py           # ML prediction logic
│   │   ├── decision_engine.py   # Threshold-based decision logic
│   │   ├── database.py          # Database connection and operations
│   │   └── feature_extract.py   # Feature extraction from raw transaction
│   ├── requirements.txt         # Python dependencies
│   └── run.sh                   # Start script
│
├── ml/
│   ├── data/
│   │   ├── raw/                 # Raw generated CSV files
│   │   └── processed/           # Feature-engineered datasets
│   ├── models/
│   │   └── xgboost_model.pkl    # Trained model file
│   ├── notebooks/
│   │   └── exploration.ipynb    # Optional: data exploration
│   ├── generate_data.py         # Synthetic data generator
│   ├── feature_engineering.py   # Feature engineering pipeline
│   ├── train_model.py           # Model training script
│   └── evaluate_model.py        # Model evaluation script
│
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js               # Main app component
│   │   ├── App.css              # Styles
│   │   ├── components/
│   │   │   ├── TransactionForm.js    # Input form
│   │   │   ├── ResultDisplay.js      # Score + decision display
│   │   │   └── TransactionHistory.js # Past transactions table
│   │   └── index.js             # React entry point
│   ├── package.json
│   └── .env                     # API URL config
│
├── scripts/
│   ├── simulate_realtime.py     # Real-time transaction simulator
│   └── setup_db.py              # Database initialization
│
├── docker-compose.yml           # Optional: containerized setup
├── README.md
└── .gitignore
```

### Folder Purposes

| Folder | Purpose |
|--------|---------|
| `backend/app/` | All FastAPI server code — routes, ML loading, DB operations |
| `ml/data/` | Raw and processed datasets (gitignored in production) |
| `ml/models/` | Serialized trained models ready for serving |
| `ml/` (root scripts) | Standalone scripts for data generation, training, evaluation |
| `frontend/src/components/` | Reusable React components for the UI |
| `scripts/` | Utility scripts for simulation and database setup |

---

## 5. Data Simulation

### 5.1 Why Simulate?

Real UPI transaction data is **not publicly available** due to banking regulations (RBI/NPCI). No open API exists to fetch real transactions. We create **realistic synthetic data** that mirrors real-world patterns — this is exactly what banks do internally for model development.

### 5.2 Transaction JSON Structure

Every transaction has this shape:

```json
{
  "transaction_id": "TXN_20240115_000001",
  "sender_upi": "user123@upi",
  "receiver_upi": "shop456@upi",
  "amount": 2500.00,
  "timestamp": "2024-01-15T14:32:00",
  "sender_device_id": "DEV_A1B2C3",
  "sender_ip": "192.168.1.45",
  "transaction_type": "purchase",
  "sender_location_lat": 19.076,
  "sender_location_lon": 72.877,
  "is_fraud": 0
}
```

### 5.3 Data Generator Script

```python
# ml/generate_data.py
import pandas as pd
import numpy as np
import random
import uuid
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

NUM_TRANSACTIONS = 100_000
FRAUD_RATIO = 0.03  # 3% fraud rate (realistic)

NUM_SENDERS = 5000
NUM_RECEIVERS = 8000

senders = [f"user{i}@upi" for i in range(NUM_SENDERS)]
receivers = [f"merchant{i}@upi" for i in range(NUM_RECEIVERS)]
devices = [f"DEV_{uuid.uuid4().hex[:8].upper()}" for _ in range(NUM_SENDERS)]
txn_types = ["purchase", "transfer", "bill_payment", "recharge"]

def generate_transaction(idx, is_fraud=False):
    sender_idx = random.randint(0, NUM_SENDERS - 1)
    timestamp = datetime(2024, 1, 1) + timedelta(
        seconds=random.randint(0, 90 * 24 * 3600)
    )

    if is_fraud:
        amount = round(random.choice([
            random.uniform(8000, 50000),   # unusually high
            random.uniform(1, 10),          # micro-test transaction
        ]), 2)
        hour = random.choice([0, 1, 2, 3, 4, 23])  # odd hours
        receiver_idx = random.randint(0, NUM_RECEIVERS - 1)
        # Fraudsters often use new devices
        device = f"DEV_{uuid.uuid4().hex[:8].upper()}"
    else:
        amount = round(random.uniform(10, 5000), 2)
        hour = random.randint(6, 22)
        receiver_idx = random.randint(0, NUM_RECEIVERS - 1)
        device = devices[sender_idx]

    timestamp = timestamp.replace(hour=hour)

    return {
        "transaction_id": f"TXN_{timestamp.strftime('%Y%m%d')}_{idx:06d}",
        "sender_upi": senders[sender_idx],
        "receiver_upi": receivers[receiver_idx],
        "amount": amount,
        "timestamp": timestamp.isoformat(),
        "sender_device_id": device,
        "sender_ip": f"{random.randint(1,255)}.{random.randint(0,255)}."
                      f"{random.randint(0,255)}.{random.randint(1,254)}",
        "transaction_type": random.choice(txn_types),
        "sender_location_lat": round(random.uniform(8.0, 37.0), 4),
        "sender_location_lon": round(random.uniform(68.0, 97.0), 4),
        "is_fraud": 1 if is_fraud else 0,
    }

# Generate data
num_fraud = int(NUM_TRANSACTIONS * FRAUD_RATIO)
num_legit = NUM_TRANSACTIONS - num_fraud

transactions = []
for i in range(num_legit):
    transactions.append(generate_transaction(i, is_fraud=False))
for i in range(num_fraud):
    transactions.append(generate_transaction(num_legit + i, is_fraud=True))

df = pd.DataFrame(transactions)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

df.to_csv("ml/data/raw/transactions.csv", index=False)
print(f"Generated {len(df)} transactions ({num_fraud} fraud, {num_legit} legit)")
print(f"Fraud ratio: {num_fraud/len(df)*100:.1f}%")
print(df.head())
```

Run it:
```bash
mkdir -p ml/data/raw ml/data/processed ml/models
python ml/generate_data.py
```

---

## 6. Feature Engineering

### 6.1 Feature List

Raw transaction fields are not enough for the model. We engineer **behavioral and statistical features**:

| Feature | Type | Description |
|---------|------|-------------|
| `amount` | Raw | Transaction amount |
| `hour` | Extracted | Hour of day (0–23) |
| `day_of_week` | Extracted | Day of week (0=Mon, 6=Sun) |
| `is_night` | Derived | 1 if hour ∈ [0,5], else 0 |
| `is_weekend` | Derived | 1 if Saturday/Sunday |
| `txn_type_encoded` | Encoded | One-hot or label encoded transaction type |
| `sender_txn_count_1h` | Behavioral | Number of txns by this sender in last 1 hour |
| `sender_txn_count_24h` | Behavioral | Number of txns by this sender in last 24 hours |
| `sender_avg_amount` | Behavioral | Sender's historical average amount |
| `sender_std_amount` | Behavioral | Standard deviation of sender's amounts |
| `amount_deviation` | Behavioral | (amount - sender_avg) / sender_std |
| `sender_unique_receivers_24h` | Behavioral | Unique receivers in past 24h |
| `is_new_device` | Behavioral | 1 if device not seen before for this sender |
| `is_new_receiver` | Behavioral | 1 if sender never transacted with this receiver |

### 6.2 Feature Engineering Script

```python
# ml/feature_engineering.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

def engineer_features(df):
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # --- Time features ---
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_night"] = df["hour"].apply(lambda h: 1 if h <= 5 else 0)
    df["is_weekend"] = df["day_of_week"].apply(lambda d: 1 if d >= 5 else 0)

    # --- Encode transaction type ---
    le = LabelEncoder()
    df["txn_type_encoded"] = le.fit_transform(df["transaction_type"])

    # --- Behavioral features (rolling window approximations) ---
    # Sender transaction counts in last 24h (approximated via groupby)
    sender_counts = df.groupby("sender_upi").cumcount()
    df["sender_txn_count_24h"] = sender_counts

    # Sender average and std amount (expanding window)
    sender_stats = df.groupby("sender_upi")["amount"].expanding()
    df["sender_avg_amount"] = sender_stats.mean().reset_index(level=0, drop=True)
    df["sender_std_amount"] = sender_stats.std().reset_index(level=0, drop=True)
    df["sender_std_amount"] = df["sender_std_amount"].fillna(0)

    # Amount deviation
    df["amount_deviation"] = np.where(
        df["sender_std_amount"] > 0,
        (df["amount"] - df["sender_avg_amount"]) / df["sender_std_amount"],
        0
    )

    # Unique receivers per sender (expanding)
    df["sender_unique_receivers_24h"] = df.groupby("sender_upi")["receiver_upi"] \
        .transform(lambda x: x.expanding().apply(lambda s: s.nunique()))

    # New device detection
    sender_devices = {}
    is_new_device = []
    for _, row in df.iterrows():
        sender = row["sender_upi"]
        device = row["sender_device_id"]
        if sender not in sender_devices:
            sender_devices[sender] = set()
            is_new_device.append(1)
        elif device not in sender_devices[sender]:
            is_new_device.append(1)
        else:
            is_new_device.append(0)
        sender_devices[sender].add(device)
    df["is_new_device"] = is_new_device

    # New receiver detection
    sender_receivers = {}
    is_new_receiver = []
    for _, row in df.iterrows():
        sender = row["sender_upi"]
        receiver = row["receiver_upi"]
        if sender not in sender_receivers:
            sender_receivers[sender] = set()
            is_new_receiver.append(1)
        elif receiver not in sender_receivers[sender]:
            is_new_receiver.append(1)
        else:
            is_new_receiver.append(0)
        sender_receivers[sender].add(receiver)
    df["is_new_receiver"] = is_new_receiver

    return df

if __name__ == "__main__":
    df = pd.read_csv("ml/data/raw/transactions.csv")
    df = engineer_features(df)

    FEATURE_COLS = [
        "amount", "hour", "day_of_week", "is_night", "is_weekend",
        "txn_type_encoded", "sender_txn_count_24h", "sender_avg_amount",
        "sender_std_amount", "amount_deviation", "sender_unique_receivers_24h",
        "is_new_device", "is_new_receiver"
    ]

    df_out = df[FEATURE_COLS + ["is_fraud"]]
    df_out.to_csv("ml/data/processed/features.csv", index=False)
    print(f"Saved {len(df_out)} rows with {len(FEATURE_COLS)} features")
    print(df_out.describe())
```

Run:
```bash
python ml/feature_engineering.py
```

### 6.3 Why Behavioral Features Matter

A transaction of ₹5,000 is not inherently suspicious. But if a user who **normally spends ₹200–500** suddenly sends **₹5,000 at 3 AM** to a **new receiver** from a **new device** — that combination screams fraud. Behavioral features capture this **context**.

---

## 7. Machine Learning Model

### 7.1 Why XGBoost?

- **Best performer** on tabular/structured data (consistently wins Kaggle competitions)
- **Fast inference** (~0.1ms per prediction) — critical for real-time
- **Handles imbalanced data** with `scale_pos_weight`
- **Feature importance** built-in for explainability

### 7.2 Full Training Script

```python
# ml/train_model.py
import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, roc_auc_score, confusion_matrix,
    precision_recall_curve, average_precision_score
)
import joblib

# --- Load data ---
df = pd.read_csv("ml/data/processed/features.csv")

FEATURE_COLS = [
    "amount", "hour", "day_of_week", "is_night", "is_weekend",
    "txn_type_encoded", "sender_txn_count_24h", "sender_avg_amount",
    "sender_std_amount", "amount_deviation", "sender_unique_receivers_24h",
    "is_new_device", "is_new_receiver"
]

X = df[FEATURE_COLS]
y = df["is_fraud"]

# --- Split ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# --- Handle imbalance ---
neg = (y_train == 0).sum()
pos = (y_train == 1).sum()
scale_weight = neg / pos
print(f"Class distribution: {neg} negative, {pos} positive")
print(f"scale_pos_weight: {scale_weight:.1f}")

# --- Train ---
model = XGBClassifier(
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    scale_pos_weight=scale_weight,
    eval_metric="aucpr",
    random_state=42,
    use_label_encoder=False,
)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=20
)

# --- Evaluate ---
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

print("\n=== Classification Report ===")
print(classification_report(y_test, y_pred))

print(f"ROC AUC: {roc_auc_score(y_test, y_proba):.4f}")
print(f"PR AUC:  {average_precision_score(y_test, y_proba):.4f}")

print("\n=== Confusion Matrix ===")
print(confusion_matrix(y_test, y_pred))

# --- Feature Importance ---
importance = model.feature_importances_
for feat, imp in sorted(zip(FEATURE_COLS, importance), key=lambda x: -x[1]):
    print(f"  {feat:30s} {imp:.4f}")

# --- Save ---
joblib.dump(model, "ml/models/xgboost_model.pkl")
joblib.dump(FEATURE_COLS, "ml/models/feature_columns.pkl")
print("\nModel saved to ml/models/xgboost_model.pkl")
```

Run:
```bash
python ml/train_model.py
```

**Expected output:** ROC AUC > 0.90, PR AUC > 0.60 (on 3% fraud rate data).

### 7.3 Key Decisions

- **`scale_pos_weight`**: Automatically compensates for the 97:3 class imbalance — no need for SMOTE
- **`eval_metric="aucpr"`**: Precision-Recall AUC is a better metric than ROC AUC for imbalanced data
- **`stratify=y`**: Ensures train/test split preserves the fraud ratio
- We save with **joblib** (faster than pickle for numpy arrays inside the model)

---

## 8. Backend Development (FastAPI)

### 8.1 Install Dependencies

```bash
cd backend
pip install fastapi uvicorn joblib xgboost scikit-learn pandas numpy sqlalchemy
```

Save to `requirements.txt`:
```
fastapi==0.104.1
uvicorn==0.24.0
joblib==1.3.2
xgboost==2.0.3
scikit-learn==1.3.2
pandas==2.1.4
numpy==1.26.2
sqlalchemy==2.0.23
```

### 8.2 Pydantic Models

```python
# backend/app/models.py
from pydantic import BaseModel
from typing import Optional

class TransactionRequest(BaseModel):
    transaction_id: Optional[str] = None
    sender_upi: str
    receiver_upi: str
    amount: float
    timestamp: Optional[str] = None
    sender_device_id: str
    sender_ip: Optional[str] = None
    transaction_type: str  # "purchase", "transfer", "bill_payment", "recharge"
    sender_location_lat: Optional[float] = None
    sender_location_lon: Optional[float] = None

class PredictionResponse(BaseModel):
    transaction_id: str
    fraud_score: float        # 0.0 - 1.0
    decision: str             # "ALLOW", "FLAG", "BLOCK"
    risk_level: str           # "LOW", "MEDIUM", "HIGH"
    message: str
```

### 8.3 Feature Extraction for Prediction

```python
# backend/app/feature_extract.py
from datetime import datetime
from sklearn.preprocessing import LabelEncoder

TXN_TYPE_MAP = {"purchase": 0, "transfer": 1, "bill_payment": 2, "recharge": 3}

# In-memory store for behavioral features (production would use Redis)
sender_history = {}

def extract_features(txn: dict) -> list:
    ts = datetime.fromisoformat(txn.get("timestamp", datetime.now().isoformat()))
    hour = ts.hour
    day_of_week = ts.weekday()
    is_night = 1 if hour <= 5 else 0
    is_weekend = 1 if day_of_week >= 5 else 0
    txn_type_encoded = TXN_TYPE_MAP.get(txn["transaction_type"], 0)

    sender = txn["sender_upi"]
    amount = txn["amount"]
    device = txn["sender_device_id"]
    receiver = txn["receiver_upi"]

    # Update and compute behavioral features
    if sender not in sender_history:
        sender_history[sender] = {
            "amounts": [], "devices": set(), "receivers": set(), "count": 0
        }

    hist = sender_history[sender]
    amounts = hist["amounts"]

    sender_txn_count_24h = hist["count"]
    sender_avg_amount = sum(amounts) / len(amounts) if amounts else amount
    sender_std_amount = (
        (sum((a - sender_avg_amount) ** 2 for a in amounts) / len(amounts)) ** 0.5
        if len(amounts) > 1 else 0
    )
    amount_deviation = (
        (amount - sender_avg_amount) / sender_std_amount
        if sender_std_amount > 0 else 0
    )
    sender_unique_receivers = len(hist["receivers"])
    is_new_device = 0 if device in hist["devices"] else 1
    is_new_receiver = 0 if receiver in hist["receivers"] else 1

    # Update history
    hist["amounts"].append(amount)
    hist["devices"].add(device)
    hist["receivers"].add(receiver)
    hist["count"] += 1

    return [
        amount, hour, day_of_week, is_night, is_weekend,
        txn_type_encoded, sender_txn_count_24h, sender_avg_amount,
        sender_std_amount, amount_deviation, sender_unique_receivers,
        is_new_device, is_new_receiver
    ]
```

### 8.4 Prediction Module

```python
# backend/app/predict.py
import joblib
import numpy as np
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "../../ml/models/xgboost_model.pkl")

_model = None

def get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
        print(f"Model loaded from {MODEL_PATH}")
    return _model

def predict_fraud(features: list) -> float:
    model = get_model()
    X = np.array(features).reshape(1, -1)
    proba = model.predict_proba(X)[0][1]  # Probability of class 1 (fraud)
    return round(float(proba), 4)
```

### 8.5 Main FastAPI Application

```python
# backend/app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

from .models import TransactionRequest, PredictionResponse
from .predict import predict_fraud
from .feature_extract import extract_features
from .decision_engine import make_decision
from .database import save_transaction, get_transactions, init_db

app = FastAPI(title="UPI Fraud Detection API", version="1.0.0")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

@app.post("/predict", response_model=PredictionResponse)
def predict(txn: TransactionRequest):
    try:
        # Generate transaction ID if not provided
        txn_id = txn.transaction_id or f"TXN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Set timestamp if not provided
        timestamp = txn.timestamp or datetime.now().isoformat()

        txn_dict = txn.dict()
        txn_dict["timestamp"] = timestamp

        # Extract features and predict
        features = extract_features(txn_dict)
        fraud_score = predict_fraud(features)

        # Make decision
        decision, risk_level, message = make_decision(fraud_score)

        # Save to database
        save_transaction(
            txn_id=txn_id,
            sender=txn.sender_upi,
            receiver=txn.receiver_upi,
            amount=txn.amount,
            fraud_score=fraud_score,
            decision=decision,
            timestamp=timestamp,
        )

        return PredictionResponse(
            transaction_id=txn_id,
            fraud_score=fraud_score,
            decision=decision,
            risk_level=risk_level,
            message=message,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transactions")
def list_transactions(limit: int = 50):
    return get_transactions(limit)

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
```

Run the server:
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs auto-available at: `http://localhost:8000/docs`

---

## 9. Decision Engine

### 9.1 Threshold Logic

```python
# backend/app/decision_engine.py

# Thresholds — tune these based on your model's performance
ALLOW_THRESHOLD = 0.3    # Below this → transaction is safe
FLAG_THRESHOLD = 0.7     # Between ALLOW and FLAG → needs manual review
                          # Above FLAG → auto-block

def make_decision(fraud_score: float) -> tuple:
    """
    Returns: (decision, risk_level, message)
    """
    if fraud_score < ALLOW_THRESHOLD:
        return (
            "ALLOW",
            "LOW",
            "Transaction appears legitimate. Approved."
        )
    elif fraud_score < FLAG_THRESHOLD:
        return (
            "FLAG",
            "MEDIUM",
            "Transaction flagged for manual review. Suspicious patterns detected."
        )
    else:
        return (
            "BLOCK",
            "HIGH",
            "Transaction blocked. High fraud probability detected."
        )
```

### 9.2 How to Tune Thresholds

| Adjustment | ALLOW Threshold | FLAG Threshold | Effect |
|------------|----------------|----------------|--------|
| **More strict** | Lower (0.2) | Lower (0.5) | Catches more fraud but more false positives |
| **More lenient** | Higher (0.4) | Higher (0.8) | Fewer false positives but may miss fraud |
| **Balanced** | 0.3 | 0.7 | Good starting point |

**Tuning approach:**
1. Run your test set through the model
2. Calculate precision/recall at different thresholds
3. Choose thresholds that match your business tolerance (e.g., banks prefer to over-flag rather than miss fraud)

---

## 10. Database Design

### 10.1 Schema

We use SQLAlchemy ORM for database-agnostic code. Switch between SQLite (development) and PostgreSQL (production) by changing one connection string.

```sql
-- SQL Schema (for reference)
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id VARCHAR(64) UNIQUE NOT NULL,
    sender_upi VARCHAR(64) NOT NULL,
    receiver_upi VARCHAR(64) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    fraud_score DECIMAL(5, 4),
    decision VARCHAR(10),          -- ALLOW / FLAG / BLOCK
    timestamp VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 10.2 Database Module

```python
# backend/app/database.py
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./fraud_detection.db"  # Change to PostgreSQL URL for prod
# PostgreSQL example: "postgresql://user:password@localhost:5432/fraud_db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TransactionRecord(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    transaction_id = Column(String(64), unique=True, index=True)
    sender_upi = Column(String(64))
    receiver_upi = Column(String(64))
    amount = Column(Float)
    fraud_score = Column(Float)
    decision = Column(String(10))
    timestamp = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Database initialized")

def save_transaction(txn_id, sender, receiver, amount, fraud_score, decision, timestamp):
    db = SessionLocal()
    try:
        record = TransactionRecord(
            transaction_id=txn_id,
            sender_upi=sender,
            receiver_upi=receiver,
            amount=amount,
            fraud_score=fraud_score,
            decision=decision,
            timestamp=timestamp,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()

def get_transactions(limit=50):
    db = SessionLocal()
    try:
        records = db.query(TransactionRecord) \
            .order_by(TransactionRecord.id.desc()) \
            .limit(limit).all()
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
```

### 10.3 Switching to PostgreSQL

1. Install: `pip install psycopg2-binary`
2. Change `DATABASE_URL`:
   ```python
   DATABASE_URL = "postgresql://postgres:password@localhost:5432/fraud_db"
   ```
3. Create database: `createdb fraud_db`
4. Everything else stays the same — SQLAlchemy handles the rest.

---

## 11. Frontend UI (React)

### 11.1 Create React App

```bash
npx -y create-react-app frontend
cd frontend
npm install axios
```

### 11.2 Environment Config

```env
# frontend/.env
REACT_APP_API_URL=http://localhost:8000
```

### 11.3 Main App Component

```jsx
// frontend/src/App.js
import React, { useState, useEffect } from 'react';
import TransactionForm from './components/TransactionForm';
import ResultDisplay from './components/ResultDisplay';
import TransactionHistory from './components/TransactionHistory';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API_URL}/transactions?limit=20`);
      setHistory(res.data);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleSubmit = async (transaction) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${API_URL}/predict`, transaction);
      setResult(res.data);
      fetchHistory(); // Refresh history after new prediction
    } catch (err) {
      setError(err.response?.data?.detail || 'Prediction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🛡️ UPI Fraud Detection System</h1>
        <p>Real-time transaction risk scoring powered by XGBoost</p>
      </header>

      <main className="app-main">
        <div className="left-panel">
          <TransactionForm onSubmit={handleSubmit} loading={loading} />
          {error && <div className="error-banner">{error}</div>}
          {result && <ResultDisplay result={result} />}
        </div>
        <div className="right-panel">
          <TransactionHistory history={history} />
        </div>
      </main>
    </div>
  );
}

export default App;
```

### 11.4 Transaction Form Component

```jsx
// frontend/src/components/TransactionForm.js
import React, { useState } from 'react';

function TransactionForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    sender_upi: '',
    receiver_upi: '',
    amount: '',
    transaction_type: 'purchase',
    sender_device_id: '',
    sender_ip: '',
  });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      ...form,
      amount: parseFloat(form.amount),
      timestamp: new Date().toISOString(),
    });
  };

  return (
    <div className="card">
      <h2>📝 New Transaction</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Sender UPI ID</label>
          <input name="sender_upi" value={form.sender_upi}
            onChange={handleChange} placeholder="user123@upi" required />
        </div>
        <div className="form-group">
          <label>Receiver UPI ID</label>
          <input name="receiver_upi" value={form.receiver_upi}
            onChange={handleChange} placeholder="merchant456@upi" required />
        </div>
        <div className="form-group">
          <label>Amount (₹)</label>
          <input name="amount" type="number" step="0.01" value={form.amount}
            onChange={handleChange} placeholder="1500.00" required />
        </div>
        <div className="form-group">
          <label>Transaction Type</label>
          <select name="transaction_type" value={form.transaction_type}
            onChange={handleChange}>
            <option value="purchase">Purchase</option>
            <option value="transfer">Transfer</option>
            <option value="bill_payment">Bill Payment</option>
            <option value="recharge">Recharge</option>
          </select>
        </div>
        <div className="form-group">
          <label>Device ID</label>
          <input name="sender_device_id" value={form.sender_device_id}
            onChange={handleChange} placeholder="DEV_ABC123" required />
        </div>
        <div className="form-group">
          <label>IP Address (optional)</label>
          <input name="sender_ip" value={form.sender_ip}
            onChange={handleChange} placeholder="192.168.1.1" />
        </div>
        <button type="submit" disabled={loading} className="submit-btn">
          {loading ? '⏳ Analyzing...' : '🔍 Check for Fraud'}
        </button>
      </form>
    </div>
  );
}

export default TransactionForm;
```

### 11.5 Result Display Component

```jsx
// frontend/src/components/ResultDisplay.js
import React from 'react';

function ResultDisplay({ result }) {
  const getColor = (decision) => {
    switch (decision) {
      case 'ALLOW': return '#22c55e';
      case 'FLAG': return '#f59e0b';
      case 'BLOCK': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getEmoji = (decision) => {
    switch (decision) {
      case 'ALLOW': return '✅';
      case 'FLAG': return '⚠️';
      case 'BLOCK': return '🚫';
      default: return '❓';
    }
  };

  return (
    <div className="card result-card"
      style={{ borderLeft: `4px solid ${getColor(result.decision)}` }}>
      <h2>{getEmoji(result.decision)} Prediction Result</h2>

      <div className="result-grid">
        <div className="result-item">
          <span className="label">Transaction ID</span>
          <span className="value">{result.transaction_id}</span>
        </div>
        <div className="result-item">
          <span className="label">Fraud Score</span>
          <span className="value score"
            style={{ color: getColor(result.decision) }}>
            {(result.fraud_score * 100).toFixed(1)}%
          </span>
        </div>
        <div className="result-item">
          <span className="label">Decision</span>
          <span className="value decision-badge"
            style={{ backgroundColor: getColor(result.decision) }}>
            {result.decision}
          </span>
        </div>
        <div className="result-item">
          <span className="label">Risk Level</span>
          <span className="value">{result.risk_level}</span>
        </div>
      </div>

      <p className="result-message">{result.message}</p>
    </div>
  );
}

export default ResultDisplay;
```

### 11.6 Transaction History Component

```jsx
// frontend/src/components/TransactionHistory.js
import React from 'react';

function TransactionHistory({ history }) {
  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'ALLOW': return '#22c55e';
      case 'FLAG': return '#f59e0b';
      case 'BLOCK': return '#ef4444';
      default: return '#6b7280';
    }
  };

  return (
    <div className="card">
      <h2>📊 Transaction History</h2>
      {history.length === 0 ? (
        <p className="empty-state">No transactions yet. Submit one to get started!</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Amount</th>
                <th>Score</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              {history.map((txn, idx) => (
                <tr key={idx}>
                  <td title={txn.transaction_id}>
                    {txn.transaction_id.substring(0, 15)}...
                  </td>
                  <td>₹{txn.amount.toLocaleString()}</td>
                  <td>{(txn.fraud_score * 100).toFixed(1)}%</td>
                  <td>
                    <span className="badge"
                      style={{ backgroundColor: getDecisionColor(txn.decision) }}>
                      {txn.decision}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default TransactionHistory;
```

### 11.7 Styles

```css
/* frontend/src/App.css */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Inter', sans-serif;
  background: #0f172a;
  color: #e2e8f0;
}

.app-header {
  text-align: center;
  padding: 2rem;
  background: linear-gradient(135deg, #1e293b, #0f172a);
  border-bottom: 1px solid #334155;
}
.app-header h1 { font-size: 1.8rem; color: #f8fafc; }
.app-header p  { color: #94a3b8; margin-top: 0.5rem; }

.app-main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

.card {
  background: #1e293b;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  border: 1px solid #334155;
}
.card h2 { font-size: 1.1rem; margin-bottom: 1rem; color: #f1f5f9; }

.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.85rem; color: #94a3b8; margin-bottom: 0.3rem; }
.form-group input, .form-group select {
  width: 100%; padding: 0.6rem 0.8rem; border-radius: 8px;
  border: 1px solid #475569; background: #0f172a; color: #e2e8f0;
  font-size: 0.9rem;
}
.form-group input:focus, .form-group select:focus {
  outline: none; border-color: #3b82f6;
}

.submit-btn {
  width: 100%; padding: 0.8rem; border: none; border-radius: 8px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white; font-size: 1rem; font-weight: 600; cursor: pointer;
  transition: transform 0.15s;
}
.submit-btn:hover { transform: translateY(-1px); }
.submit-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.result-card { margin-top: 1rem; }
.result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.result-item .label { display: block; font-size: 0.75rem; color: #94a3b8; }
.result-item .value { font-size: 1.1rem; font-weight: 600; }
.score { font-size: 1.5rem !important; }
.decision-badge {
  display: inline-block; padding: 0.25rem 0.75rem;
  border-radius: 20px; color: white; font-size: 0.85rem;
}
.result-message { margin-top: 1rem; color: #94a3b8; font-size: 0.9rem; }

.error-banner {
  background: #7f1d1d; color: #fecaca; padding: 0.8rem;
  border-radius: 8px; margin-top: 1rem;
}

table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-size: 0.75rem; color: #64748b; padding: 0.5rem; border-bottom: 1px solid #334155; }
td { padding: 0.6rem 0.5rem; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }
.badge {
  display: inline-block; padding: 0.15rem 0.5rem;
  border-radius: 12px; color: white; font-size: 0.75rem; font-weight: 600;
}
.table-wrapper { max-height: 500px; overflow-y: auto; }
.empty-state { color: #64748b; text-align: center; padding: 2rem; }

@media (max-width: 768px) {
  .app-main { grid-template-columns: 1fr; }
}
```

Start the frontend:
```bash
cd frontend
npm start
```

The app opens at `http://localhost:3000`.

---

## 12. Real-Time Simulation

### 12.1 Simulation Script

This script continuously sends random transactions to your backend, simulating a live system:

```python
# scripts/simulate_realtime.py
import requests
import random
import time
import uuid
from datetime import datetime

API_URL = "http://localhost:8000/predict"

senders = [f"user{i}@upi" for i in range(100)]
receivers = [f"merchant{i}@upi" for i in range(200)]
devices = [f"DEV_{uuid.uuid4().hex[:8].upper()}" for _ in range(100)]
txn_types = ["purchase", "transfer", "bill_payment", "recharge"]

def random_transaction(is_suspicious=False):
    if is_suspicious:
        return {
            "sender_upi": random.choice(senders),
            "receiver_upi": random.choice(receivers),
            "amount": round(random.uniform(10000, 50000), 2),
            "transaction_type": random.choice(txn_types),
            "sender_device_id": f"DEV_{uuid.uuid4().hex[:8].upper()}",  # new device
            "sender_ip": f"{random.randint(1,255)}.{random.randint(0,255)}.0.1",
            "timestamp": datetime.now().replace(hour=random.choice([1,2,3,4])).isoformat(),
        }
    return {
        "sender_upi": random.choice(senders),
        "receiver_upi": random.choice(receivers),
        "amount": round(random.uniform(50, 3000), 2),
        "transaction_type": random.choice(txn_types),
        "sender_device_id": random.choice(devices),
        "sender_ip": f"192.168.1.{random.randint(1,254)}",
        "timestamp": datetime.now().isoformat(),
    }

def main():
    print("🚀 Starting real-time transaction simulation...")
    print(f"   Target: {API_URL}")
    print(f"   Press Ctrl+C to stop\n")

    count = 0
    blocked = 0
    flagged = 0

    try:
        while True:
            # 5% chance of suspicious transaction
            is_suspicious = random.random() < 0.05
            txn = random_transaction(is_suspicious)

            try:
                resp = requests.post(API_URL, json=txn, timeout=5)
                data = resp.json()
                count += 1

                decision = data["decision"]
                score = data["fraud_score"]

                if decision == "BLOCK":
                    blocked += 1
                    icon = "🚫"
                elif decision == "FLAG":
                    flagged += 1
                    icon = "⚠️"
                else:
                    icon = "✅"

                print(f"  {icon} #{count:04d} | ₹{txn['amount']:>10,.2f} | "
                      f"Score: {score:.3f} | {decision:5s} | "
                      f"{txn['sender_upi']} → {txn['receiver_upi']}")

            except requests.exceptions.RequestException as e:
                print(f"  ❌ Request failed: {e}")

            time.sleep(random.uniform(0.5, 2.0))  # Random delay between txns

    except KeyboardInterrupt:
        print(f"\n\n📊 Simulation Summary:")
        print(f"   Total transactions: {count}")
        print(f"   Blocked:            {blocked}")
        print(f"   Flagged:            {flagged}")
        print(f"   Allowed:            {count - blocked - flagged}")

if __name__ == "__main__":
    main()
```

Run:
```bash
python scripts/simulate_realtime.py
```

### 12.2 How This Mimics Real-Time

In a production system, transactions arrive through payment gateways (Razorpay, Paytm, etc.) via webhooks or message queues. Our simulator replicates this by:
- Sending transactions at random intervals (0.5–2s)
- Mixing legitimate and suspicious patterns
- Printing real-time results like a monitoring dashboard

---

## 13. Optional Advanced (Kafka + Redis)

> ⚠️ **This section is optional and for advanced users.** The system works perfectly without Kafka and Redis.

### 13.1 Kafka Architecture

```
┌──────────┐     ┌────────────────┐     ┌──────────────┐     ┌──────────┐
│ Producer │ ──► │  Kafka Topic   │ ──► │   Consumer   │ ──► │ Database │
│ (Txn     │     │ "transactions" │     │ (ML Scoring) │     │          │
│  Source)  │     └────────────────┘     └──────────────┘     └──────────┘
└──────────┘
```

**Why Kafka?**
- **Decoupling**: Transaction ingestion is separated from scoring
- **Buffering**: If the ML service is slow, transactions queue up instead of being dropped
- **Replay**: Can re-process past transactions if the model is updated
- **Scale**: Multiple consumers can process in parallel

**Setup (Docker):**
```yaml
# docker-compose.yml (add to existing)
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports: ["9092:9092"]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
```

**Producer example:**
```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

producer.send('transactions', value=transaction_dict)
```

### 13.2 Redis Feature Store

Redis stores **pre-computed behavioral features** for sub-millisecond lookups:

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, db=0)

# Store sender stats
def update_sender_stats(sender_upi, amount):
    key = f"sender:{sender_upi}"
    stats = r.get(key)
    if stats:
        stats = json.loads(stats)
        stats["count"] += 1
        stats["total"] += amount
        stats["avg"] = stats["total"] / stats["count"]
    else:
        stats = {"count": 1, "total": amount, "avg": amount}
    r.setex(key, 86400, json.dumps(stats))  # TTL: 24 hours

# Read sender stats (< 1ms)
def get_sender_stats(sender_upi):
    key = f"sender:{sender_upi}"
    stats = r.get(key)
    return json.loads(stats) if stats else None
```

---

## 14. Testing the System

### 14.1 API Testing with cURL / Postman

**Legitimate transaction:**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "sender_upi": "john@upi",
    "receiver_upi": "amazon@upi",
    "amount": 499.00,
    "transaction_type": "purchase",
    "sender_device_id": "DEV_JOHN_PHONE",
    "timestamp": "2024-01-15T14:30:00"
  }'
```

**Suspicious transaction (high amount, new device, night):**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "sender_upi": "john@upi",
    "receiver_upi": "unknown_merchant@upi",
    "amount": 45000.00,
    "transaction_type": "transfer",
    "sender_device_id": "DEV_NEW_UNKNOWN",
    "timestamp": "2024-01-15T03:15:00"
  }'
```

### 14.2 Frontend Testing

1. Start backend: `uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm start`
3. Open `http://localhost:3000`
4. Fill in the form with normal values → expect `ALLOW`
5. Fill in with high amount + unusual device → expect `FLAG` or `BLOCK`

### 14.3 Running the Simulator

```bash
python scripts/simulate_realtime.py
```

Watch the terminal output — you should see a mix of ✅, ⚠️, and 🚫 results.

### 14.4 Debugging Tips

| Issue | Solution |
|-------|----------|
| CORS error in browser | Check `allow_origins` in FastAPI includes `http://localhost:3000` |
| Model not found | Verify `ml/models/xgboost_model.pkl` exists (run `train_model.py` first) |
| Features mismatch error | Ensure feature column order matches between training and prediction |
| Database locked (SQLite) | Restart the backend; SQLite doesn't support concurrent writes well |
| API returns 500 | Check backend terminal for the full stack trace |

---

## 15. Performance Optimization

### 15.1 Model Loading

**Problem:** Loading the model on every request is slow.

**Solution:** Load once at startup (already implemented in `predict.py` with the singleton pattern).

### 15.2 Caching with functools

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def load_model():
    return joblib.load("ml/models/xgboost_model.pkl")
```

### 15.3 Batch Predictions

For the simulation script or bulk processing:

```python
# Instead of predicting one at a time:
predictions = model.predict_proba(X_batch)[:, 1]  # Predict entire batch at once
```

### 15.4 Async Database Writes

Use background tasks to avoid blocking the response:

```python
from fastapi import BackgroundTasks

@app.post("/predict")
def predict(txn: TransactionRequest, background_tasks: BackgroundTasks):
    # ... compute prediction ...
    background_tasks.add_task(save_transaction, ...)  # Non-blocking DB write
    return response
```

### 15.5 Performance Targets

| Metric | Target | How to Measure |
|--------|--------|----------------|
| API latency (p50) | < 20ms | `time curl ...` |
| API latency (p99) | < 100ms | Load test with `locust` or `wrk` |
| Model inference | < 1ms | `time.perf_counter()` around predict call |
| Throughput | > 500 req/s | Load test with concurrent requests |

---

## 16. Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **No real banking API** | Cannot test with real UPI infrastructure | Synthetic data mimics real patterns closely |
| **Simulated environment** | Results may not transfer directly to production | Architecture is production-ready; only the data source changes |
| **No sequence modeling** | Cannot capture complex temporal fraud patterns | XGBoost with behavioral features covers 80% of cases |
| **In-memory feature store** | Behavioral features reset on server restart | Use Redis in production for persistence |
| **Single-node deployment** | Cannot scale horizontally as-is | Add Kafka + multiple workers for scale |
| **No explainability UI** | Cannot show *why* a transaction was flagged | Add SHAP values in a future iteration |

---

## 17. Future Improvements

### 17.1 Graph Neural Networks (GNN)

Fraudsters operate in networks. GNNs can detect:
- **Ring transactions**: A → B → C → A (money laundering)
- **Mule accounts**: One account receiving from many flagged senders
- Libraries: PyTorch Geometric, DGL

### 17.2 Behavioral Biometrics

- Typing speed, touch pressure, swipe patterns
- Device accelerometer data during transaction
- These are extremely hard to spoof

### 17.3 Cloud Deployment

```
Frontend → Vercel (free tier)
Backend  → Railway / Render (free tier)
Database → Supabase PostgreSQL (free tier)
Model    → Store in S3 / GCS, load at startup
```

### 17.4 Enhanced Dashboard

- Real-time charts (fraud rate over time)
- Geographic heatmaps of flagged transactions
- User risk profiles
- Alert management system
- Libraries: Recharts, D3.js, Leaflet

### 17.5 Model Improvements

- **Online learning**: Update model weights with each new labeled transaction
- **Ensemble**: Combine XGBoost with LightGBM and a neural net
- **Anomaly detection**: Isolation Forest as a secondary signal
- **SHAP explanations**: Show which features drove the decision

---

## 18. Step-by-Step Build Plan

### Week 1: Data + Machine Learning

| Day | Task | Files |
|-----|------|-------|
| 1 | Set up project structure, virtual environment | All folders |
| 2 | Write data generator, generate 100K transactions | `generate_data.py` |
| 3 | Feature engineering pipeline | `feature_engineering.py` |
| 4 | Train XGBoost model, evaluate | `train_model.py` |
| 5 | Tune hyperparameters, save final model | `xgboost_model.pkl` |

### Week 2: Backend API

| Day | Task | Files |
|-----|------|-------|
| 1 | Set up FastAPI, create models | `main.py`, `models.py` |
| 2 | Implement feature extraction for live requests | `feature_extract.py` |
| 3 | Build `/predict` endpoint, integrate model | `predict.py` |
| 4 | Add decision engine, database logging | `decision_engine.py`, `database.py` |
| 5 | Test API with cURL, fix bugs | — |

### Week 3: Frontend

| Day | Task | Files |
|-----|------|-------|
| 1 | Create React app, set up Axios | `App.js` |
| 2 | Build TransactionForm component | `TransactionForm.js` |
| 3 | Build ResultDisplay component | `ResultDisplay.js` |
| 4 | Build TransactionHistory, styling | `TransactionHistory.js`, `App.css` |
| 5 | Connect to backend, test end-to-end | — |

### Week 4: Integration + Polish

| Day | Task | Files |
|-----|------|-------|
| 1 | Write simulation script, test with backend | `simulate_realtime.py` |
| 2 | Fix edge cases, improve error handling | All backend files |
| 3 | Add loading states, animations to UI | Frontend components |
| 4 | Write README, document API | `README.md` |
| 5 | Final testing, record demo, deploy (optional) | — |

### Quick-Start Commands (After Building)

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm start

# Terminal 3: Simulator
python scripts/simulate_realtime.py
```

---

## Appendix: Complete File Checklist

| File | Status | Section |
|------|--------|---------|
| `ml/generate_data.py` | Must build | §5 |
| `ml/feature_engineering.py` | Must build | §6 |
| `ml/train_model.py` | Must build | §7 |
| `backend/app/__init__.py` | Empty file | §8 |
| `backend/app/main.py` | Must build | §8 |
| `backend/app/models.py` | Must build | §8 |
| `backend/app/predict.py` | Must build | §8 |
| `backend/app/feature_extract.py` | Must build | §8 |
| `backend/app/decision_engine.py` | Must build | §9 |
| `backend/app/database.py` | Must build | §10 |
| `backend/requirements.txt` | Must create | §8 |
| `frontend/src/App.js` | Must build | §11 |
| `frontend/src/App.css` | Must build | §11 |
| `frontend/src/components/TransactionForm.js` | Must build | §11 |
| `frontend/src/components/ResultDisplay.js` | Must build | §11 |
| `frontend/src/components/TransactionHistory.js` | Must build | §11 |
| `frontend/.env` | Must create | §11 |
| `scripts/simulate_realtime.py` | Must build | §12 |

---

*Document generated for portfolio/hackathon use. All components are free, open-source, and runnable on a standard development machine.*

