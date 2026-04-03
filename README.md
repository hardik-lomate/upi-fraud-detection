# 🛡️ UPI Fraud Detection System

**Industry-grade real-time fraud detection powered by Ensemble ML, SHAP Explainability, Graph Analysis, and Compliance Logging.**

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green) ![React](https://img.shields.io/badge/React-18-61dafb) ![XGBoost](https://img.shields.io/badge/XGBoost-2.0-orange) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Architecture

```
Request → Rate Limiter → JWT Auth → Rules Engine (6 rules)
    → Feature Extract (13 features, real 24h window)
    → Ensemble ML (XGBoost 45% + LightGBM 35% + IsoForest 20%)
    → SHAP Explainability (top 5 reasons)
    → Device Fingerprinting (impossible travel, IP anomaly)
    → Graph Analysis (PageRank, mule detection, ring transactions)
    → Decision Engine → Async DB + Audit Trail
```

## Features

| Category | Details |
|----------|---------|
| **Ensemble ML** | XGBoost + LightGBM + Isolation Forest with weighted scoring |
| **Explainability** | SHAP TreeExplainer — returns human-readable reasons per prediction |
| **Rules Engine** | 6 pre-ML rules: amount limits, rapid-fire, midnight checks, self-transfer, velocity, new device |
| **Graph Analysis** | NetworkX — PageRank, mule account detection, ring transaction detection |
| **Device Fingerprint** | Impossible travel (haversine), IP subnet change, new device detection |
| **Model Monitoring** | PSI drift detection with reference distribution comparison |
| **Auth & Security** | JWT + API key authentication, rate limiting (100 req/min) |
| **Audit Trail** | Immutable JSONL daily logs with model version tracking |
| **Dashboard** | React + Recharts — pie/bar charts, drift panel, graph stats |

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, SQLite
- **ML:** XGBoost, LightGBM, scikit-learn, SHAP, NetworkX
- **Frontend:** React 18, Axios, Recharts
- **Auth:** python-jose (JWT), slowapi (rate limiting)

## Quick Start

### 1. Train Models
```bash
pip install -r backend/requirements.txt
python ml/generate_data.py
python ml/feature_engineering.py
python ml/train_ensemble.py
```

### 2. Start Backend
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. Start Frontend
```bash
cd frontend
npm install
npm start
```

### 4. Run Simulator (optional)
```bash
python scripts/simulate_realtime.py
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Full 9-step prediction pipeline |
| `/transactions` | GET | Transaction history |
| `/auth/token` | POST | Exchange API key for JWT |
| `/monitoring/drift` | GET | PSI drift report |
| `/monitoring/stats` | GET | Prediction statistics |
| `/monitoring/graph` | GET | Transaction graph stats |
| `/audit/logs` | GET | Audit trail viewer |
| `/health` | GET | Health check |

## Project Structure

```
upi_fraud_detection/
├── backend/app/
│   ├── main.py              # FastAPI app (9-step pipeline)
│   ├── predict.py           # Ensemble model loader
│   ├── feature_extract.py   # 13 features, real 24h window
│   ├── rules_engine.py      # 6 pre-ML fraud rules
│   ├── explainability.py    # SHAP TreeExplainer
│   ├── graph_features.py    # NetworkX graph analysis
│   ├── device_fingerprint.py# Impossible travel detection
│   ├── monitoring.py        # PSI drift detection
│   ├── auth.py              # JWT + API key auth
│   ├── audit.py             # Immutable audit trail
│   ├── decision_engine.py   # Threshold-based decisions
│   ├── database.py          # SQLAlchemy ORM
│   └── models.py            # Pydantic schemas
├── ml/
│   ├── generate_data.py     # 100K synthetic transactions
│   ├── feature_engineering.py
│   ├── train_model.py       # Single XGBoost trainer
│   └── train_ensemble.py    # Ensemble trainer (3 models)
├── frontend/src/
│   ├── App.js               # Tabbed UI (Predict / Monitor)
│   ├── components/
│   │   ├── TransactionForm.js
│   │   ├── ResultDisplay.js  # Scores, SHAP, rules, graph
│   │   ├── TransactionHistory.js
│   │   └── MonitoringPanel.js# Recharts dashboard
│   └── App.css              # Dark theme
└── scripts/
    └── simulate_realtime.py  # Continuous transaction generator
```

## License

MIT
