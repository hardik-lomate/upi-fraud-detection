# 🛡️ UPI Fraud Detection System

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green) ![React](https://img.shields.io/badge/React-18-61dafb) ![Docker](https://img.shields.io/badge/Docker-Ready-2496ED) ![License](https://img.shields.io/badge/License-MIT-yellow)

Real-time UPI fraud detection using ensemble ML, SHAP explainability, graph analysis, and a rules engine — built for production.

---

## Architecture

```
Transaction → Validate → Features → Rules → ML Ensemble → Decide → Explain → Device → Graph
                                      │           │
                                 Instant BLOCK  XGBoost (45%)
                                 or FLAG        LightGBM (35%)
                                                IsoForest (20%)
```

## Performance

| Metric | Value |
|--------|-------|
| Ensemble ROC AUC | ~0.97 |
| Ensemble PR AUC | ~0.81 |
| XGBoost CV ROC AUC | ~0.97 ± 0.002 |
| LightGBM CV ROC AUC | ~0.96 ± 0.003 |
| Thresholds | Optimized via F0.5 + Recall≥90% |

## Features

| Category | Feature |
|----------|---------|
| **ML** | 3-model ensemble (XGBoost + LightGBM + IsoForest) with calibrated scores |
| **Rules** | 6 pre-ML rules: amount limit, rapid-fire, midnight, self-transfer, velocity, new device |
| **Explainability** | SHAP TreeExplainer with per-transaction top-5 risk factors |
| **Graph** | NetworkX: PageRank, mule detection, ring transactions, hub accounts |
| **Device** | Impossible travel (Haversine), new device detection, IP anomaly |
| **Monitoring** | PSI drift detection, prediction statistics, model metadata |
| **Feedback** | Analyst verdict loop (confirmed_fraud / false_positive / true_negative) |
| **Live Feed** | WebSocket real-time transaction stream with auto-scrolling UI |
| **Batch** | CSV upload endpoint for bulk predictions |
| **Auth** | JWT + API key auth, rate limiting, RBAC permissions |
| **Audit** | Immutable JSONL compliance logging |
| **Risk Breakdown** | 4-dimensional risk scoring: behavioral, temporal, network, device |

## Quick Start

### Local Development

```bash
# 1. Clone
git clone https://github.com/hardik-lomate/upi-fraud-detection.git
cd upi-fraud-detection

# 2. Setup
cp .env.example .env
pip install -r backend/requirements.txt

# 3. Train models
python ml/generate_data.py
python ml/feature_engineering.py
python ml/train_ensemble.py

# 4. Start backend
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. Start frontend (new terminal)
cd frontend && npm install && npm start
```

### Docker

```bash
cp .env.example .env
docker-compose up -d
# Train models: docker-compose run trainer
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/predict` | Single transaction prediction (8-step pipeline) |
| POST | `/predict/batch` | Bulk CSV upload prediction |
| POST | `/feedback` | Submit analyst verdict |
| GET | `/feedback/stats` | Feedback aggregate statistics |
| GET | `/model/info` | Model metadata, CV results, thresholds |
| GET | `/transactions` | Recent transaction history |
| GET | `/monitoring/drift` | PSI-based feature drift report |
| GET | `/monitoring/stats` | Prediction statistics |
| GET | `/monitoring/graph` | Transaction graph statistics |
| GET | `/monitoring/store` | History store backend info |
| GET | `/audit/logs` | Immutable audit trail |
| GET | `/health` | Quick health check |
| GET | `/health/ready` | Deep readiness probe |
| WS | `/ws/live-feed` | Real-time transaction WebSocket |
| POST | `/auth/token` | Get JWT from API key |

## Testing

```bash
# Run tests
python -m pytest tests/ -q

# With coverage
python -m pytest tests/ --cov=backend/app --cov-report=term
```

## Project Structure

```
├── feature_contract.py      # Single source of truth (features, encoding, thresholds)
├── backend/app/
│   ├── main.py              # FastAPI app (16 endpoints)
│   ├── pipeline.py          # 8-step central controller
│   ├── predict.py           # Ensemble prediction + IsoForest calibration
│   ├── feature_extract.py   # Serving-time feature extraction
│   ├── rules_engine.py      # 6 pre-ML rules
│   ├── explainability.py    # SHAP TreeExplainer
│   ├── history_store.py     # Redis + in-memory fallback
│   ├── feedback.py          # Analyst verdict collection
│   ├── live_feed.py         # WebSocket live feed handler
│   ├── decision_engine.py   # Threshold-based decisions
│   ├── auth.py              # JWT + API key authentication
│   └── models.py            # Pydantic models with OpenAPI docs
├── ml/
│   ├── train_ensemble.py    # Training + CV + threshold optimization
│   ├── feature_engineering.py
│   ├── retrain.py           # Retraining loop with feedback
│   └── models/              # Saved models, calibration, metadata
├── frontend/src/
│   ├── App.js               # 3-tab app (Predict, Live Feed, Monitor)
│   └── components/
│       ├── FraudGauge.js     # Animated SVG gauge
│       ├── LiveFeed.js       # WebSocket live feed
│       ├── ResultDisplay.js  # Risk breakdown + feedback
│       └── ...
├── tests/
│   ├── test_pipeline.py     # Pipeline step tests
│   ├── test_rules_engine.py # Rules tests
│   └── test_api.py          # API integration tests
├── scripts/
│   └── demo_scenarios.py    # 6 pre-built demo scenarios
├── docker-compose.yml
└── .github/workflows/ci.yml # CI with coverage
```

## Design Decisions

- **Ensemble > Single Model**: XGBoost catches patterns, LightGBM provides diversity, IsoForest detects unseen anomalies. Reduces false positives by 15-20%.
- **Rules Before ML**: Instant blocking for obvious fraud (self-transfer, velocity limits). Avoids ML latency for clear-cut cases. Regulatory compliance (RBI).
- **Feature Contract**: `feature_contract.py` is the single source of truth. Eliminates training-serving skew — the #1 cause of silent ML failures in production.
- **IsoForest Calibration**: Min/max saved from training set and applied at serving time for consistent 0-1 normalization.

## License

MIT
