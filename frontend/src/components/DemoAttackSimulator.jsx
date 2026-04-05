import React, { useState, useCallback } from 'react';
import { api } from '../api/client';

const SCENARIOS = [
  {
    id: 'sim_swap_takeover',
    name: 'SIM Swap Takeover',
    icon: '📱',
    description: 'Attacker swaps SIM, changes device, initiates high-value transfers',
    steps: [
      { desc: 'Victim\'s SIM swapped — new device ID registered', txn: { sender_upi: 'victim_sim@upi', receiver_upi: 'attacker_001@ybl', amount: 500, transaction_type: 'transfer', sender_device_id: 'DEV_NEW_SWAP_001' } },
      { desc: 'Small test transaction to verify account access', txn: { sender_upi: 'victim_sim@upi', receiver_upi: 'test_recv@paytm', amount: 100, transaction_type: 'transfer', sender_device_id: 'DEV_NEW_SWAP_001' } },
      { desc: 'First large transfer — Rs.45,000 to mule account', txn: { sender_upi: 'victim_sim@upi', receiver_upi: 'mule_layer1@ybl', amount: 45000, transaction_type: 'transfer', sender_device_id: 'DEV_NEW_SWAP_001' } },
      { desc: 'Second wave — Rs.82,000 to different mule', txn: { sender_upi: 'victim_sim@upi', receiver_upi: 'mule_layer2@oksbi', amount: 82000, transaction_type: 'transfer', sender_device_id: 'DEV_NEW_SWAP_001' } },
      { desc: 'Final extraction — Rs.1,20,000 to offshore account', txn: { sender_upi: 'victim_sim@upi', receiver_upi: 'offshore_xk9f2@ybl', amount: 120000, transaction_type: 'transfer', sender_device_id: 'DEV_NEW_SWAP_001' } },
    ],
  },
  {
    id: 'money_mule_chain',
    name: 'Money Mule Chain',
    icon: '🔗',
    description: 'Layered transfers through 4 mule accounts to obfuscate origin',
    steps: [
      { desc: 'Origin — stolen funds enter the chain at Rs.95,000', txn: { sender_upi: 'stolen_acct@upi', receiver_upi: 'mule_a@ybl', amount: 95000, transaction_type: 'transfer' } },
      { desc: 'Layer 1 — mule_a splits and forwards Rs.47,000', txn: { sender_upi: 'mule_a@ybl', receiver_upi: 'mule_b@paytm', amount: 47000, transaction_type: 'transfer' } },
      { desc: 'Layer 1 — other half Rs.46,000 to mule_c', txn: { sender_upi: 'mule_a@ybl', receiver_upi: 'mule_c@oksbi', amount: 46000, transaction_type: 'transfer' } },
      { desc: 'Layer 2 — mule_b consolidates to final drop', txn: { sender_upi: 'mule_b@paytm', receiver_upi: 'cash_out@ybl', amount: 45000, transaction_type: 'transfer' } },
      { desc: 'Layer 2 — mule_c also routes to final drop', txn: { sender_upi: 'mule_c@oksbi', receiver_upi: 'cash_out@ybl', amount: 44000, transaction_type: 'transfer' } },
    ],
  },
  {
    id: 'velocity_attack',
    name: 'Rapid Velocity Attack',
    icon: '⚡',
    description: '10 transactions in 60 seconds — draining account via micro-transfers',
    steps: [
      { desc: 'Burst 1 — Rs.4,999 (just under monitoring threshold)', txn: { sender_upi: 'velocity_victim@upi', receiver_upi: 'drop_01@ybl', amount: 4999, transaction_type: 'transfer' } },
      { desc: 'Burst 2 — Rs.4,998 to different receiver', txn: { sender_upi: 'velocity_victim@upi', receiver_upi: 'drop_02@paytm', amount: 4998, transaction_type: 'transfer' } },
      { desc: 'Burst 3 — Rs.4,997 escalating pattern', txn: { sender_upi: 'velocity_victim@upi', receiver_upi: 'drop_03@oksbi', amount: 4997, transaction_type: 'transfer' } },
      { desc: 'Burst 4 — Rs.4,996 system should flag by now', txn: { sender_upi: 'velocity_victim@upi', receiver_upi: 'drop_04@ybl', amount: 4996, transaction_type: 'transfer' } },
      { desc: 'Burst 5 — Rs.4,995 SHOULD BE BLOCKED', txn: { sender_upi: 'velocity_victim@upi', receiver_upi: 'drop_05@paytm', amount: 4995, transaction_type: 'transfer' } },
    ],
  },
  {
    id: 'impossible_travel',
    name: 'Geographic Anomaly',
    icon: '🌍',
    description: 'Transaction from Mumbai, then Delhi 4 minutes later — impossible travel',
    steps: [
      { desc: 'Transaction from Mumbai at 2:00 PM', txn: { sender_upi: 'traveler@upi', receiver_upi: 'shop_mumbai@upi', amount: 2500, transaction_type: 'purchase', sender_location_lat: 19.076, sender_location_lon: 72.877 } },
      { desc: '4 mins later — transaction from Delhi (1,400km away)', txn: { sender_upi: 'traveler@upi', receiver_upi: 'shop_delhi@upi', amount: 15000, transaction_type: 'purchase', sender_location_lat: 28.614, sender_location_lon: 77.209, sender_device_id: 'DEV_CLONED_002' } },
      { desc: 'Another purchase in Delhi — Rs.35,000', txn: { sender_upi: 'traveler@upi', receiver_upi: 'electronics_delhi@upi', amount: 35000, transaction_type: 'purchase', sender_location_lat: 28.620, sender_location_lon: 77.215, sender_device_id: 'DEV_CLONED_002' } },
    ],
  },
  {
    id: 'merchant_collusion',
    name: 'Merchant Collusion Ring',
    icon: '🏪',
    description: 'Fake merchant processes refund-purchase cycles for cash extraction',
    steps: [
      { desc: 'Fake purchase at colluding merchant — Rs.25,000', txn: { sender_upi: 'colluder_customer@upi', receiver_upi: 'fake_merchant_001@upi', amount: 25000, transaction_type: 'purchase' } },
      { desc: 'Merchant "refunds" to a different account — Rs.24,500', txn: { sender_upi: 'fake_merchant_001@upi', receiver_upi: 'cash_extract@ybl', amount: 24500, transaction_type: 'transfer' } },
      { desc: 'Another fake purchase cycle — Rs.30,000', txn: { sender_upi: 'colluder_customer2@upi', receiver_upi: 'fake_merchant_001@upi', amount: 30000, transaction_type: 'purchase' } },
      { desc: 'Merchant routes to cash extraction — Rs.29,000', txn: { sender_upi: 'fake_merchant_001@upi', receiver_upi: 'cash_extract@ybl', amount: 29000, transaction_type: 'transfer' } },
    ],
  },
];

export default function DemoAttackSimulator({ onTransactionResult }) {
  const [running, setRunning] = useState(false);
  const [activeScenario, setActiveScenario] = useState(null);
  const [stepIndex, setStepIndex] = useState(-1);
  const [log, setLog] = useState([]);
  const [expanded, setExpanded] = useState(false);

  const runScenario = useCallback(async (scenario) => {
    if (running) return;
    setRunning(true);
    setActiveScenario(scenario.id);
    setStepIndex(0);
    setLog([{ type: 'info', text: `🚨 Starting scenario: ${scenario.name}` }]);

    for (let i = 0; i < scenario.steps.length; i++) {
      setStepIndex(i);
      const step = scenario.steps[i];
      setLog((prev) => [...prev, { type: 'step', text: `Step ${i + 1}: ${step.desc}` }]);

      try {
        const res = await api.post('/predict', step.txn);
        const decision = res.data?.decision || 'UNKNOWN';
        const score = res.data?.fraud_score || 0;
        const emoji = decision === 'BLOCK' ? '🛑' : decision === 'VERIFY' ? '⚠️' : '✅';
        setLog((prev) => [...prev, {
          type: decision === 'BLOCK' ? 'danger' : decision === 'VERIFY' ? 'warn' : 'safe',
          text: `${emoji} ${decision} — Risk: ${(score * 100).toFixed(1)}%`,
        }]);
        onTransactionResult?.(res.data, step.txn);
      } catch {
        // Simulate fallback
        const simulatedDecision = i >= 3 ? 'BLOCK' : i >= 1 ? 'VERIFY' : 'ALLOW';
        const simulatedScore = 0.2 + i * 0.18;
        const emoji = simulatedDecision === 'BLOCK' ? '🛑' : simulatedDecision === 'VERIFY' ? '⚠️' : '✅';
        setLog((prev) => [...prev, {
          type: simulatedDecision === 'BLOCK' ? 'danger' : simulatedDecision === 'VERIFY' ? 'warn' : 'safe',
          text: `${emoji} ${simulatedDecision} (sim) — Risk: ${(simulatedScore * 100).toFixed(1)}%`,
        }]);
      }

      // Wait between steps for dramatic effect
      if (i < scenario.steps.length - 1) {
        await new Promise((r) => setTimeout(r, 1500));
      }
    }

    setLog((prev) => [...prev, { type: 'info', text: `✅ Scenario "${scenario.name}" complete` }]);
    setRunning(false);
    setActiveScenario(null);
    setStepIndex(-1);
  }, [running, onTransactionResult]);

  return (
    <div className="panel fade-in">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
        <div>
          <div className="panel-title flex items-center gap-2">
            <span className="text-lg">🎯</span>
            Live Attack Simulator
          </div>
          <div className="mt-1 text-xs text-textSecondary">Watch the system catch real fraud patterns in real-time</div>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-accent hover:text-accent-light transition"
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      </div>

      {expanded && (
        <div className="px-5 py-4 space-y-3">
          {/* Scenario buttons */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                disabled={running}
                onClick={() => runScenario(s)}
                className={`text-left rounded-xl border p-3 transition ${
                  activeScenario === s.id
                    ? 'border-accent/50 bg-accent/10'
                    : 'border-border/50 bg-bg-card/50 hover:border-accent/30 hover:bg-bg-elevated/50'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <div className="flex items-center gap-2 text-sm font-semibold text-textPrimary">
                  <span>{s.icon}</span>
                  {s.name}
                </div>
                <div className="mt-1 text-[11px] text-textSecondary leading-tight">{s.description}</div>
                <div className="mt-1.5 text-[10px] text-textMuted">{s.steps.length} steps</div>
              </button>
            ))}
          </div>

          {/* Log output */}
          {log.length > 0 && (
            <div className="rounded-xl border border-border/50 bg-bg/50 p-3 max-h-48 overflow-auto font-mono text-xs space-y-1">
              {log.map((entry, i) => (
                <div key={i} className={
                  entry.type === 'danger' ? 'text-danger' :
                  entry.type === 'warn' ? 'text-warn' :
                  entry.type === 'safe' ? 'text-safe' :
                  'text-textSecondary'
                }>
                  {entry.text}
                </div>
              ))}
              {running && (
                <div className="text-accent animate-pulse">Processing step {stepIndex + 1}...</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
