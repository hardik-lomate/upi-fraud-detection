FROM python:3.11-slim

WORKDIR /app

# Install deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ ./backend/
COPY ml/models/ ./ml/models/
COPY monitoring/ ./monitoring/
COPY feature_contract.py .
COPY api_keys.json .

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
