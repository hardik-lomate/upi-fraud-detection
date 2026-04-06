export function formatIndianCurrency(amount, withSymbol = true) {
  const value = Number(amount) || 0;
  const formatted = new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 2,
    minimumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
  return withSymbol ? `₹${formatted}` : formatted;
}

export function firstName(fullName = '') {
  return String(fullName).trim().split(' ')[0] || 'there';
}

export function formatTime(value) {
  if (!value) return '--:--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--:--';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function formatDateLabel(value) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());

  if (target.getTime() === today.getTime()) return 'Today';
  if (target.getTime() === yesterday.getTime()) return 'Yesterday';

  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000);
  if (diffDays <= 7) return 'This Week';
  if (today.getMonth() === target.getMonth() && today.getFullYear() === target.getFullYear()) {
    return 'This Month';
  }

  return new Intl.DateTimeFormat('en-IN', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

export function greetingByTime() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}
