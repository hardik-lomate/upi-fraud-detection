# Pitch Script — UPI Fraud Detection (User-Side)

## Opening Line
We are not competing with banks. We are solving the last-mile problem: protecting users before they make a mistake.

## Problem Statement
Bank-side systems often react after a payment is authorized. In social-engineering fraud, that delay is costly because once UPI funds move out, recovery odds drop sharply.

## Our Solution
We intercept before the UPI PIN screen using `/api/v1/pre-check`.
Users see:
- A real-time risk score
- Plain-English reasons (SHAP-based)
- Clear choices: Proceed Anyway or Cancel Payment

## Technical Depth Points
- 32-feature behavioral + contextual model
- Ensemble inference: LightGBM + XGBoost
- SHAP explainability for transparent risk rationale
- Pre-payment interception flow with confirm/cancel hooks
- Geo-impossibility checks (distance vs time)
- Adaptive thresholding based on user profile history

## Demo Script
1. Start with a normal payment and show smooth pass-through.
2. Trigger a medium-risk transaction (new receiver + higher amount) and show warning modal.
3. Trigger impossible travel and show block decision with reason.
4. Open admin console and show metrics panel + confusion matrix.
5. Run scripted `demo_scenarios.py` transactions and show summary accuracy.

## Judge Memory Point
The defining moment is the warning popup that stops a bad transfer before PIN entry. That is the user-protection story judges remember.
