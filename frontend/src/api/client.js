import axios from 'axios';

const DEFAULT_LOCAL_API_URL = 'http://localhost:8000';
const DEFAULT_CLOUD_API_URL = 'https://upi-fraud-detection-qu72.onrender.com';

const configuredApiUrl = String(process.env.REACT_APP_API_URL || '').trim().replace(/\/+$/, '');

function resolveApiUrl() {
  const isPlaceholder = configuredApiUrl.includes('your-railway-backend');
  if (configuredApiUrl && !isPlaceholder) {
    return configuredApiUrl;
  }

  // If env is missing on hosted builds, use deployed backend; keep local default for dev.
  return process.env.NODE_ENV === 'production' ? DEFAULT_CLOUD_API_URL : DEFAULT_LOCAL_API_URL;
}

export const API_URL = resolveApiUrl();

export const api = axios.create({
  baseURL: API_URL,
  timeout: 8000,
});
