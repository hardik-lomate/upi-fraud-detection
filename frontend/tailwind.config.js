/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', '"IBM Plex Sans"', '"Segoe UI"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        display: ['"Space Grotesk"', '"IBM Plex Sans"', 'sans-serif'],
      },
      colors: {
        bg: 'rgb(var(--c-bg) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        primary: 'rgb(var(--c-primary) / <alpha-value>)',
        textPrimary: 'rgb(var(--c-text-primary) / <alpha-value>)',
        textSecondary: 'rgb(var(--c-text-secondary) / <alpha-value>)',
        success: 'rgb(var(--c-success) / <alpha-value>)',
        warning: 'rgb(var(--c-warning) / <alpha-value>)',
        danger: 'rgb(var(--c-danger) / <alpha-value>)',
        border: 'rgb(var(--c-border) / <alpha-value>)',
        user_bg: '#F5F7FA',
        user_surface: '#FFFFFF',
        user_border: '#E8EBF0',
        user_text: '#0D0F1A',
        user_muted: '#9EA3BD',
        india_saffron: '#FF9933',
        india_green: '#138808',
        upi_purple: '#5F259F',
      },
      boxShadow: {
        panel: '0 10px 30px rgba(0, 0, 0, 0.22)',
      },
    },
  },
  plugins: [],
};
