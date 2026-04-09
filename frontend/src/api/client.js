import axios from 'axios';

const configuredApiUrl = String(process.env.REACT_APP_API_URL || '').trim().replace(/\/+$/, '');

if (!configuredApiUrl) {
  throw new Error('Missing REACT_APP_API_URL. Set it to your deployed backend URL.');
}

export const API_URL = configuredApiUrl;

export const api = axios.create({
  baseURL: API_URL,
  timeout: 8000,
});
