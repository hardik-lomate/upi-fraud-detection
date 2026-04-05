/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', '"IBM Plex Sans"', '"Segoe UI"', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        display: ['"Space Grotesk"', '"Inter"', 'sans-serif'],
      },
      colors: {
        bg: {
          DEFAULT: 'rgb(var(--c-bg) / <alpha-value>)',
          surface: 'rgb(var(--c-surface) / <alpha-value>)',
          card: 'rgb(var(--c-card) / <alpha-value>)',
          elevated: 'rgb(var(--c-elevated) / <alpha-value>)',
          hover: 'rgb(var(--c-hover) / <alpha-value>)',
        },
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        accent: {
          DEFAULT: 'rgb(var(--c-accent) / <alpha-value>)',
          light: 'rgb(var(--c-accent-light) / <alpha-value>)',
          dark: 'rgb(var(--c-accent-dark) / <alpha-value>)',
          bg: 'rgb(var(--c-accent-bg) / <alpha-value>)',
        },
        primary: 'rgb(var(--c-accent) / <alpha-value>)',
        textPrimary: 'rgb(var(--c-text-primary) / <alpha-value>)',
        textSecondary: 'rgb(var(--c-text-secondary) / <alpha-value>)',
        textMuted: 'rgb(var(--c-text-muted) / <alpha-value>)',
        safe: 'rgb(var(--c-safe) / <alpha-value>)',
        success: 'rgb(var(--c-safe) / <alpha-value>)',
        warn: 'rgb(var(--c-warn) / <alpha-value>)',
        warning: 'rgb(var(--c-warn) / <alpha-value>)',
        danger: 'rgb(var(--c-danger) / <alpha-value>)',
        info: 'rgb(var(--c-info) / <alpha-value>)',
        verify: 'rgb(var(--c-verify) / <alpha-value>)',
        border: 'rgb(var(--c-border) / <alpha-value>)',
      },
      boxShadow: {
        panel: '0 10px 30px rgba(0, 0, 0, 0.25)',
        glow: '0 0 20px rgba(108, 71, 255, 0.15)',
      },
      borderRadius: {
        sm: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
    },
  },
  plugins: [],
};
