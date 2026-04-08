import React from 'react';

function StatCard({ title, value, caption, tone = 'slate' }) {
  const toneClass =
    tone === 'success'
      ? 'from-emerald-500/20 to-emerald-500/5 border-emerald-400/25'
      : tone === 'danger'
        ? 'from-rose-500/20 to-rose-500/5 border-rose-400/25'
        : tone === 'warning'
          ? 'from-amber-500/20 to-amber-500/5 border-amber-300/25'
          : 'from-sky-500/20 to-sky-500/5 border-sky-400/25';

  return (
    <div className={`rounded-2xl border bg-gradient-to-br p-4 ${toneClass}`}>
      <p className="text-xs uppercase tracking-[0.14em] text-slate-300">{title}</p>
      <p className="mt-2 text-2xl font-bold tracking-tight text-slate-100">{value}</p>
      {caption ? <p className="mt-1 text-xs text-slate-400">{caption}</p> : null}
    </div>
  );
}

export default React.memo(StatCard);
