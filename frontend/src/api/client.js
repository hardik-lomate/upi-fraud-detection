import axios from 'axios';

export const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

export const api = axios.create({
  baseURL: API_URL,
  timeout: 8000,
});
