import React from 'react';

function ShieldGlyph({ state }) {
  return (
    <svg viewBox="0 0 48 52" className={`shield-glyph shield-${state}`} aria-hidden="true">
      <path
        className="shield-body"
        d="M24 2l19 7v14c0 12.8-7.6 22.4-19 27C12.6 45.4 5 35.8 5 23V9l19-7z"
      />
      {state === 'blocked' ? (
        <path className="shield-mark" d="M17 18l14 14M31 18L17 32" />
      ) : state === 'warn' || state === 'scanning' ? (
        <path
          className="shield-mark"
          d="M24 33c4 0 7-3.5 7-8s-3.5-9-7-9-7 4-7 9 3 8 7 8zm0-15v15"
        />
      ) : (
        <path className="shield-mark" d="M15 25l7 7 11-12" />
      )}
    </svg>
  );
}

export default function ShieldAnimation({ state = 'idle', size = 56, className = '' }) {
  return (
    <div
      className={`shield-wrap state-${state} ${className}`.trim()}
      style={{ width: size, height: size }}
      role="img"
      aria-label="Shield status"
    >
      <ShieldGlyph state={state} />
      {state === 'scanning' ? <span className="shield-scan-ring" aria-hidden="true" /> : null}
    </div>
  );
}
