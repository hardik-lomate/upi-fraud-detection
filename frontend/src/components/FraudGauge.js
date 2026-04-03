import React, { useEffect, useRef, useState } from 'react';

function FraudGauge({ score, decision }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const rafRef = useRef(null);

  useEffect(() => {
    const start = performance.now();
    const duration = 800;
    const from = 0;
    const to = score;

    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setAnimatedScore(from + (to - from) * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [score]);

  const cx = 140, cy = 130, radius = 100;
  const startAngle = Math.PI;
  const endAngle = 0;
  const scoreAngle = startAngle - animatedScore * Math.PI;

  // Gradient stops
  const getColor = (s) => {
    if (s < 0.3) return '#22c55e';
    if (s < 0.7) return '#f59e0b';
    return '#ef4444';
  };

  // Arc path
  const arcPath = (startA, endA) => {
    const x1 = cx + radius * Math.cos(startA);
    const y1 = cy - radius * Math.sin(startA);
    const x2 = cx + radius * Math.cos(endA);
    const y2 = cy - radius * Math.sin(endA);
    const largeArc = (startA - endA) > Math.PI ? 1 : 0;
    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;
  };

  // Needle
  const needleLen = radius - 15;
  const nx = cx + needleLen * Math.cos(scoreAngle);
  const ny = cy - needleLen * Math.sin(scoreAngle);

  const decisionColors = { ALLOW: '#22c55e', FLAG: '#f59e0b', BLOCK: '#ef4444' };
  const decisionEmoji = { ALLOW: '✅', FLAG: '⚠️', BLOCK: '🚫' };

  return (
    <div style={{ textAlign: 'center', margin: '10px 0' }}>
      <svg width="280" height="170" viewBox="0 0 280 170">
        {/* Background arc */}
        <path d={arcPath(Math.PI, 0)} fill="none" stroke="#2a2a3a" strokeWidth="18" strokeLinecap="round" />

        {/* Green segment */}
        <path d={arcPath(Math.PI, Math.PI * 0.7)} fill="none" stroke="#22c55e" strokeWidth="18" strokeLinecap="round" opacity="0.3" />
        {/* Yellow segment */}
        <path d={arcPath(Math.PI * 0.7, Math.PI * 0.3)} fill="none" stroke="#f59e0b" strokeWidth="18" strokeLinecap="round" opacity="0.3" />
        {/* Red segment */}
        <path d={arcPath(Math.PI * 0.3, 0)} fill="none" stroke="#ef4444" strokeWidth="18" strokeLinecap="round" opacity="0.3" />

        {/* Active arc */}
        <path d={arcPath(Math.PI, scoreAngle)} fill="none" stroke={getColor(animatedScore)} strokeWidth="18" strokeLinecap="round" />

        {/* Needle */}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#fff" strokeWidth="3" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="6" fill="#fff" />

        {/* Score text */}
        <text x={cx} y={cy + 35} textAnchor="middle" fill="#fff" fontSize="28" fontWeight="bold">
          {(animatedScore * 100).toFixed(1)}%
        </text>
      </svg>

      <div style={{
        display: 'inline-block', padding: '6px 20px', borderRadius: '20px', fontWeight: 'bold',
        fontSize: '14px', color: '#fff', backgroundColor: decisionColors[decision] || '#666',
        marginTop: '-10px',
      }}>
        {decisionEmoji[decision]} {decision}
      </div>
    </div>
  );
}

export default FraudGauge;
