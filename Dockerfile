FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY feature_contract.py .
COPY ml/ ./ml/
COPY model/ ./model/
COPY monitoring/ ./monitoring/

# Create default api_keys.json (auth.py falls back to built-in dev keys)
RUN echo '{}' > ./api_keys.json

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
