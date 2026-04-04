import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Dark theme is the product requirement
document.documentElement.classList.add('dark');

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
