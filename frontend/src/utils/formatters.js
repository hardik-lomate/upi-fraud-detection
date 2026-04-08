export function clamp01(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 0;
  return Math.max(0, Math.min(1, num));
}

export function formatCurrency(value) {
  const amount = Number(value);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number.isFinite(amount) ? amount : 0);
}

export function formatCompactNumber(value) {
  const num = Number(value);
  return new Intl.NumberFormat('en-IN', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number.isFinite(num) ? num : 0);
}

export function formatDateTime(value) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function riskBand(risk) {
  const score = clamp01(risk);
  if (score < 0.3) return 'low';
  if (score <= 0.6) return 'medium';
  return 'high';
}
