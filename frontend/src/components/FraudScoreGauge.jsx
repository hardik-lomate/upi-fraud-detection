import React, { useEffect, useRef } from 'react';

function getColor(score) {
  if (score >= 0.7) return '#E24B4A';
  if (score >= 0.4) return '#EF9F27';
  return '#00C9A7';
}

function getLabel(score) {
  if (score >= 0.7) return 'HIGH RISK';
  if (score >= 0.4) return 'MEDIUM';
  return 'LOW RISK';
}

export default function FraudScoreGauge({ score = 0, size = 140, animated = true }) {
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference - (score * circumference);
  const center = size / 2;
  const color = getColor(score);
  const arcRef = useRef(null);

  useEffect(() => {
    if (animated && arcRef.current) {
      arcRef.current.style.setProperty('--gauge-circumference', String(circumference));
      arcRef.current.style.setProperty('--gauge-offset', String(offset));
    }
  }, [score, circumference, offset, animated]);

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${center} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${center}`}
          fill="none"
          stroke="rgba(37, 42, 64, 0.6)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Foreground arc */}
        <path
          ref={arcRef}
          d={`M ${strokeWidth / 2} ${center} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${center}`}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={animated ? circumference : offset}
          className={animated ? 'gauge-arc-animated' : ''}
          style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
        />
        {/* Score text */}
        <text
          x={center}
          y={center - 8}
          textAnchor="middle"
          fill={color}
          fontSize="24"
          fontWeight="600"
          fontFamily="JetBrains Mono, monospace"
        >
          {(score * 100).toFixed(0)}%
        </text>
        <text
          x={center}
          y={center + 12}
          textAnchor="middle"
          fill="rgb(139, 143, 173)"
          fontSize="10"
          fontWeight="500"
          letterSpacing="0.1em"
        >
          {getLabel(score)}
        </text>
      </svg>
    </div>
  );
}
