import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const STATUS_COLORS = {
  OPEN: { bg: 'bg-info/10', border: 'border-info/30', text: 'text-info' },
  UNDER_REVIEW: { bg: 'bg-warn/10', border: 'border-warn/30', text: 'text-warn' },
  CLOSED_FRAUD: { bg: 'bg-danger/10', border: 'border-danger/30', text: 'text-danger' },
  CLOSED_LEGITIMATE: { bg: 'bg-safe/10', border: 'border-safe/30', text: 'text-safe' },
};

export default function CasesPanel({ onCaseClick }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/cases', { params: { limit: 100 } });
      setCases(res.data?.cases || []);
    } catch {
      // Demo data
      setCases([
        { id: 1, txn_id: 'TXN_demo_001', status: 'OPEN', assigned_to: 'Analyst A', notes: 'Suspicious velocity pattern', created_at: new Date().toISOString(), resolved_at: null },
        { id: 2, txn_id: 'TXN_demo_002', status: 'UNDER_REVIEW', assigned_to: 'Analyst B', notes: 'Mule account flagged', created_at: new Date().toISOString(), resolved_at: null },
        { id: 3, txn_id: 'TXN_demo_003', status: 'CLOSED_FRAUD', assigned_to: 'Analyst A', notes: 'Confirmed fraud, account frozen', created_at: new Date().toISOString(), resolved_at: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCases(); }, [fetchCases]);

  const updateStatus = async (caseId, newStatus) => {
    try {
      await api.patch(`/cases/${caseId}`, { status: newStatus });
      fetchCases();
    } catch {
      setCases((prev) => prev.map((c) => c.id === caseId ? { ...c, status: newStatus } : c));
    }
  };

  const columns = ['OPEN', 'UNDER_REVIEW', 'CLOSED_FRAUD', 'CLOSED_LEGITIMATE'];
  const columnLabels = { OPEN: 'Open', UNDER_REVIEW: 'Under Review', CLOSED_FRAUD: 'Closed (Fraud)', CLOSED_LEGITIMATE: 'Closed (Legit)' };

  const filteredCases = filter
    ? cases.filter((c) => c.txn_id?.toLowerCase().includes(filter.toLowerCase()) || c.assigned_to?.toLowerCase().includes(filter.toLowerCase()))
    : cases;

  return (
    <div className="panel fade-in">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
        <div>
          <div className="panel-title">Case Management</div>
          <div className="mt-1 text-xs text-textSecondary">{cases.length} total cases</div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search cases..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-40 rounded-lg border border-border/60 bg-bg/40 px-3 py-1.5 text-xs text-textPrimary outline-none placeholder:text-textMuted focus:border-accent/40"
          />
          <button
            onClick={fetchCases}
            className="rounded-lg border border-border/60 bg-bg/40 px-3 py-1.5 text-xs text-textSecondary hover:text-textPrimary transition"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Kanban Board */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4" style={{ minHeight: '400px' }}>
        {columns.map((status) => {
          const col = STATUS_COLORS[status] || STATUS_COLORS.OPEN;
          const items = filteredCases.filter((c) => c.status === status);

          return (
            <div key={status} className="flex flex-col">
              <div className={`flex items-center justify-between rounded-t-lg ${col.bg} border ${col.border} px-3 py-2`}>
                <span className={`text-xs font-semibold uppercase tracking-wider ${col.text}`}>
                  {columnLabels[status]}
                </span>
                <span className={`text-xs font-mono ${col.text}`}>{items.length}</span>
              </div>
              <div className="flex-1 rounded-b-lg border border-t-0 border-border/40 bg-bg-card/30 p-2 space-y-2 min-h-[200px]">
                {items.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => onCaseClick?.(c)}
                    className="rounded-lg border border-border/40 bg-bg-elevated/50 p-3 cursor-pointer hover:border-accent/30 transition group"
                  >
                    <div className="font-mono text-[11px] text-accent truncate">{c.txn_id}</div>
                    <div className="mt-1 text-xs text-textSecondary truncate">{c.notes || 'No notes'}</div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-[10px] text-textMuted">{c.assigned_to || 'Unassigned'}</span>
                      {/* Quick status change dropdown */}
                      <select
                        value={c.status}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => { e.stopPropagation(); updateStatus(c.id, e.target.value); }}
                        className="text-[10px] bg-transparent border-none text-textMuted outline-none cursor-pointer opacity-0 group-hover:opacity-100 transition"
                      >
                        {columns.map((s) => (
                          <option key={s} value={s}>{columnLabels[s]}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))}
                {items.length === 0 && (
                  <div className="text-xs text-textMuted text-center py-4">No cases</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
