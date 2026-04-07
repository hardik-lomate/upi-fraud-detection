# System Architecture — User-Side AI Fraud Prevention

## System Overview — User-Side AI Fraud Prevention
This platform protects users before UPI PIN submission by intercepting payment intent and returning a risk score, explainable reasons, and a warning payload. It does not replace bank-side controls; it closes the last-mile gap where users are socially engineered into sending funds.

## Component Diagram

```text
+----------------------+       +---------------------------+
|  User Mobile/Web UI  | ----> |  Pre-Check API (/api/v1) |
|  PayScreen + Warning |       |  FastAPI + Rules + ML     |
+----------+-----------+       +-----+---------------------+
           |                         |
           | warning payload         | feature extraction
           v                         v
+----------------------+      +---------------------------+
| FraudWarningModal    |      | Feature Layer             |
| (proceed / cancel)   |      | history_store + Redis     |
+----------+-----------+      +-------------+-------------+
           |                                  |
           | confirm/cancel                    | model input (32 features)
           v                                  v
+----------------------+      +---------------------------+
| Confirm/Cancel API   |      | Ensemble Inference        |
| audit + persistence  |      | LightGBM/XGBoost/CatBoost |
+----------+-----------+      | + IsolationForest          |
           |                  +-------------+-------------+
           |                                    |
           v                                    v
+----------------------+      +---------------------------+
| PostgreSQL/SQLite    | <--- | Explainability (SHAP)     |
| transactions + cases |      | top risk reasons          |
+----------------------+      +---------------------------+
```

## Data Flow: User taps Pay -> Pre-Check API -> ML Pipeline -> Warning UI
1. User enters receiver UPI and amount on Pay screen.
2. Frontend calls `/api/v1/pre-check` before PIN prompt.
3. Backend runs: validation -> features -> rules -> ML -> SHAP -> decision -> warning payload.
4. API returns `user_warning` with risk tier, reasons, and action buttons.
5. User chooses:
   - Proceed Anyway -> `/api/v1/pre-check/{id}/confirm`
   - Cancel Payment -> `/api/v1/pre-check/{id}/cancel`

## ML Stack
- Primary: LightGBM
- Secondary: XGBoost
- Additional learners: CatBoost, IsolationForest
- Ensemble weights: LightGBM 0.35, XGBoost 0.30, CatBoost 0.25, IsolationForest 0.10

## Feature Store
- Hot path: Redis cache (`user_features:{sender_upi}`)
- Cold path: relational transaction store
- In-memory fallback when Redis is unavailable

## Explainability
- SHAP TreeExplainer is loaded at startup
- Top positive contributors are mapped to plain-English UPI reasons
- Reasons are returned to UI for warning cards and audit logs

## Risk Tiers
- LOW: allow
- MEDIUM: warning popup (user can continue with override)
- HIGH: block-first response with explicit user protection message

## Why User-Side
Banks generally act after authorization signals are finalized. This system intervenes at intent time, before PIN entry, to stop high-risk transfers while the user can still cancel safely.
