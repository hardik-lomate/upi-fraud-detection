import React, { useState } from 'react';

const SIGNAL_ICONS = {
  new_device: '📱',
  impossible_travel: '✈️',
  velocity: '⚡',
  vpa_suspicious: '🎭',
  geo_risk: '🌍',
  ip_vpn: '🛡️',
  night_high_amount: '🌙',
  mule_network: '🕸️',
  high_amount: '💰',
  new_receiver: '👤',
  amount_deviation: '📊',
  default: '⚠️',
};

const SIGNAL_DETAILS = {
  'Transaction from unrecognized device': {
    signal: 'new_device',
    title: 'Unrecognized Device',
    detail: 'This transaction was initiated from a device we have not seen before. If you did not recently change your phone, this may indicate account compromise.',
    color: '#E24B4A',
  },
  'Impossible travel detected': {
    signal: 'impossible_travel',
    title: 'Impossible Travel',
    detail: 'Your previous transaction was from a different location — physically impossible to reach in the elapsed time.',
    color: '#E24B4A',
  },
  'Very high velocity': {
    signal: 'velocity',
    title: 'High Transaction Velocity',
    detail: 'This many transactions in such a short time matches automated fraud patterns. Legitimate users rarely transact this quickly.',
    color: '#E24B4A',
  },
  'Rapid transactions': {
    signal: 'velocity',
    title: 'Elevated Velocity',
    detail: 'Multiple rapid transactions detected. This rate is unusual for typical user behavior.',
    color: '#EF9F27',
  },
  'Suspicious receiver UPI': {
    signal: 'vpa_suspicious',
    title: 'Suspicious Receiver UPI',
    detail: 'The receiver UPI ID shows patterns common in mule accounts or auto-generated identifiers.',
    color: '#EF9F27',
  },
  'High-fraud zone': {
    signal: 'geo_risk',
    title: 'High-Risk Location',
    detail: 'Transaction originates from a region with elevated fraud rates based on NPCI data.',
    color: '#EF9F27',
  },
  'Unusual transaction time': {
    signal: 'night_high_amount',
    title: 'Late Night Activity',
    detail: 'Transfers during late night hours (12 AM - 5 AM) are statistically more likely to be fraudulent.',
    color: '#EF9F27',
  },
  'High-value transaction': {
    signal: 'high_amount',
    title: 'High-Value Transfer',
    detail: 'This amount is significantly above the typical threshold. High-value transfers undergo additional scrutiny.',
    color: '#EF9F27',
  },
  'First-time payment': {
    signal: 'new_receiver',
    title: 'New Receiver',
    detail: 'This is the first time you are sending money to this recipient. New receiver transactions are monitored more closely.',
    color: '#EF9F27',
  },
  'above your average': {
    signal: 'amount_deviation',
    title: 'Unusual Amount',
    detail: 'This transaction amount deviates significantly from your typical spending patterns.',
    color: '#EF9F27',
  },
  'Unrecognized device with high-value': {
    signal: 'new_device',
    title: 'New Device + High Amount',
    detail: 'A high-value transfer from an unrecognized device is a strong indicator of SIM swap or device theft.',
    color: '#E24B4A',
  },
  'First-time receiver with large amount': {
    signal: 'new_receiver',
    title: 'New Receiver + Large Amount',
    detail: 'Sending a large sum to a first-time recipient is a common fraud vector. Please verify the recipient.',
    color: '#E24B4A',
  },
};

function matchReason(reason) {
  for (const [key, config] of Object.entries(SIGNAL_DETAILS)) {
    if (reason.toLowerCase().includes(key.toLowerCase())) {
      return config;
    }
  }
  return null;
}

function ReasonCard({ reason, index }) {
  const [expanded, setExpanded] = useState(false);
  const config = matchReason(reason);
  const icon = config ? SIGNAL_ICONS[config.signal] : SIGNAL_ICONS.default;
  const title = config?.title || reason;
  const detail = config?.detail || 'This risk signal contributed to the fraud score calculation.';
  const color = config?.color || '#8B8FA3';

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        padding: '12px 14px',
        marginBottom: 8,
        borderRadius: 8,
        background: '#0D0E14',
        borderLeft: `3px solid ${color}`,
        cursor: 'pointer',
        transition: 'all 0.2s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#E0E0E6' }}>{title}</div>
          <div style={{ fontSize: 11, color: '#8B8FA3', marginTop: 2 }}>{reason}</div>
        </div>
        <span
          style={{
            width: 6, height: 6, borderRadius: '50%',
            background: color,
            boxShadow: `0 0 6px ${color}`,
          }}
        />
        <span style={{ fontSize: 11, color: '#6B7094', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>▼</span>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid #1A1D2E', fontSize: 12, color: '#8B8FA3', lineHeight: 1.5 }}>
          {detail}
        </div>
      )}
    </div>
  );
}

export default function ReasonCards({ reasons = [], message = '' }) {
  if (!reasons.length && !message) return null;

  return (
    <div>
      {/* Decision message callout */}
      {message && message !== 'Approved.' && (
        <div style={{
          padding: '12px 14px',
          marginBottom: 12,
          borderRadius: 8,
          background: message.includes('blocked') ? '#E24B4A11' : message.includes('Verification') ? '#EF9F2711' : '#34D39911',
          borderLeft: `3px solid ${message.includes('blocked') ? '#E24B4A' : message.includes('Verification') ? '#EF9F27' : '#34D399'}`,
          fontSize: 12,
          color: '#E0E0E6',
          lineHeight: 1.6,
        }}>
          {message}
        </div>
      )}

      {/* Individual reason cards */}
      {reasons.map((r, i) => (
        <ReasonCard key={i} reason={r} index={i} />
      ))}
    </div>
  );
}
