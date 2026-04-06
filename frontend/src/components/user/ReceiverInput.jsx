import React, { useEffect } from 'react';

const FREQUENT_CONTACTS = [
  { name: 'Amazon', upi: 'amazon@apl', color: '#FF9900' },
  { name: 'Swiggy', upi: 'swiggy@icici', color: '#FC8019' },
  { name: 'Electricity', upi: 'msedcl@upi', color: '#2563EB' },
  { name: 'Zomato', upi: 'zomato@axl', color: '#E23744' },
  { name: 'Mom', upi: 'priya.mother@sbi', color: '#6C47FF' },
  { name: 'Office Rent', upi: 'landlord@ybl', color: '#059669' },
];

const DEMO_FRAUD_CONTACTS = [
  { name: 'Test Fraud', upi: 'mule_a_collect@ybl', color: '#E24B4A', note: 'Triggers BLOCK' },
  { name: 'KYC Scam', upi: 'npci.helpdesk.kyc@paytm', color: '#E24B4A', note: 'Govt impersonation block' },
  { name: 'Verify Test', upi: 'offshore_xk9f2@ybl', color: '#F39C12', note: 'Triggers VERIFY/BLOCK' },
];

function ContactChip({ contact, danger = false, onSelect }) {
  return (
    <button
      type="button"
      className={`contact-chip ${danger ? 'danger' : ''}`}
      onClick={() => onSelect(contact.upi)}
    >
      <span className="contact-icon" style={{ backgroundColor: contact.color }}>
        {contact.name.slice(0, 1)}
      </span>
      <span className="contact-text">
        <span>{danger ? `⚠ ${contact.name}` : contact.name}</span>
        <small>{contact.note || contact.upi}</small>
      </span>
    </button>
  );
}

export default function ReceiverInput({ value, onChange, receiverInfo, onLookup }) {
  useEffect(() => {
    if (!value || value.length < 3) return undefined;
    const timer = setTimeout(() => {
      onLookup(value);
    }, 300);
    return () => clearTimeout(timer);
  }, [value, onLookup]);

  return (
    <section className="user-card">
      <label className="field-label" htmlFor="receiver-upi">Pay To</label>
      <input
        id="receiver-upi"
        className="text-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Enter receiver UPI ID (name@bank)"
        autoCapitalize="none"
        spellCheck={false}
      />

      {receiverInfo ? (
        <div className={`receiver-info risk-${String(receiverInfo.vpa_risk || 'LOW').toLowerCase()}`}>
          <div>
            <strong>{receiverInfo.display_name}</strong>
            <div className="receiver-meta">{receiverInfo.upi_id}</div>
          </div>
          <span className="risk-chip">{receiverInfo.vpa_risk}</span>
        </div>
      ) : null}

      {receiverInfo?.warning ? <p className="risk-warning">{receiverInfo.warning}</p> : null}

      <div className="contacts-block">
        <div className="contacts-title">Frequent Contacts</div>
        <div className="contacts-scroll">
          {FREQUENT_CONTACTS.map((contact) => (
            <ContactChip key={contact.upi} contact={contact} onSelect={onChange} />
          ))}
        </div>
      </div>

      <div className="contacts-block">
        <div className="contacts-title">Demo Fraud Contacts</div>
        <div className="contacts-scroll">
          {DEMO_FRAUD_CONTACTS.map((contact) => (
            <ContactChip key={contact.upi} contact={contact} danger onSelect={onChange} />
          ))}
        </div>
      </div>
    </section>
  );
}
