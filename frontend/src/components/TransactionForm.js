import React, { useState } from 'react';

function TransactionForm({ onSubmit, loading, disabled }) {
  const [form, setForm] = useState({
    sender_upi: '',
    receiver_upi: '',
    amount: '',
    transaction_type: 'purchase',
    sender_device_id: '',
    sender_ip: '',
  });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      ...form,
      amount: parseFloat(form.amount),
      timestamp: new Date().toISOString(),
    });
  };

  return (
    <div className="card">
      <h2>📝 New Transaction</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Sender UPI ID</label>
          <input
            name="sender_upi"
            value={form.sender_upi}
            onChange={handleChange}
            placeholder="user123@upi"
            required
          />
        </div>
        <div className="form-group">
          <label>Receiver UPI ID</label>
          <input
            name="receiver_upi"
            value={form.receiver_upi}
            onChange={handleChange}
            placeholder="merchant456@upi"
            required
          />
        </div>
        <div className="form-group">
          <label>Amount (₹)</label>
          <input
            name="amount"
            type="number"
            step="0.01"
            value={form.amount}
            onChange={handleChange}
            placeholder="1500.00"
            required
          />
        </div>
        <div className="form-group">
          <label>Transaction Type</label>
          <select
            name="transaction_type"
            value={form.transaction_type}
            onChange={handleChange}
          >
            <option value="purchase">Purchase</option>
            <option value="transfer">Transfer</option>
            <option value="bill_payment">Bill Payment</option>
            <option value="recharge">Recharge</option>
          </select>
        </div>
        <div className="form-group">
          <label>Device ID</label>
          <input
            name="sender_device_id"
            value={form.sender_device_id}
            onChange={handleChange}
            placeholder="DEV_ABC123"
            required
          />
        </div>
        <div className="form-group">
          <label>IP Address (optional)</label>
          <input
            name="sender_ip"
            value={form.sender_ip}
            onChange={handleChange}
            placeholder="192.168.1.1"
          />
        </div>
        <button type="submit" disabled={loading || disabled} className="submit-btn">
          {loading ? '⏳ Analyzing...' : disabled ? '🔌 Backend Offline' : '🔍 Check for Fraud'}
        </button>
      </form>
    </div>
  );
}

export default TransactionForm;
