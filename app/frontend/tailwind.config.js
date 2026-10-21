/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Little Caesars Brand Colors
        lce: {
          orange: '#FF671B',
          'orange-dark': 'rgb(var(--lce-orange-dark) / <alpha-value>)',
          'orange-light': '#FF8F57',
          black: '#1A1A1A',
          cream: 'rgb(var(--lce-cream) / <alpha-value>)',
        },
        // UI Colors: CSS variables so Spooky mode can swap them (light values in index.css)
        surface: {
          DEFAULT: 'rgb(var(--surface-default) / <alpha-value>)',
          secondary: 'rgb(var(--surface-secondary) / <alpha-value>)',
          tertiary: 'rgb(var(--surface-tertiary) / <alpha-value>)',
        },
        text: {
          primary: 'rgb(var(--text-primary) / <alpha-value>)',
          secondary: 'rgb(var(--text-secondary) / <alpha-value>)',
          tertiary: 'rgb(var(--text-tertiary) / <alpha-value>)',
        },
        // Shades the UI uses as tints, borders and text. Mid shades (400, 500) stay Tailwind defaults.
        gray: {
          50: 'rgb(var(--gray-50) / <alpha-value>)',
          100: 'rgb(var(--gray-100) / <alpha-value>)',
          200: 'rgb(var(--gray-200) / <alpha-value>)',
          300: 'rgb(var(--gray-300) / <alpha-value>)',
          600: 'rgb(var(--gray-600) / <alpha-value>)',
          700: 'rgb(var(--gray-700) / <alpha-value>)',
        },
        red: {
          50: 'rgb(var(--red-50) / <alpha-value>)',
          100: 'rgb(var(--red-100) / <alpha-value>)',
          600: 'rgb(var(--red-600) / <alpha-value>)',
          700: 'rgb(var(--red-700) / <alpha-value>)',
        },
        green: {
          50: 'rgb(var(--green-50) / <alpha-value>)',
          100: 'rgb(var(--green-100) / <alpha-value>)',
          600: 'rgb(var(--green-600) / <alpha-value>)',
          700: 'rgb(var(--green-700) / <alpha-value>)',
        },
        amber: {
          50: 'rgb(var(--amber-50) / <alpha-value>)',
          200: 'rgb(var(--amber-200) / <alpha-value>)',
          600: 'rgb(var(--amber-600) / <alpha-value>)',
          700: 'rgb(var(--amber-700) / <alpha-value>)',
          800: 'rgb(var(--amber-800) / <alpha-value>)',
        },
        blue: {
          50: 'rgb(var(--blue-50) / <alpha-value>)',
          600: 'rgb(var(--blue-600) / <alpha-value>)',
          700: 'rgb(var(--blue-700) / <alpha-value>)',
        },
        orange: {
          50: 'rgb(var(--orange-50) / <alpha-value>)',
          100: 'rgb(var(--orange-100) / <alpha-value>)',
          200: 'rgb(var(--orange-200) / <alpha-value>)',
          600: 'rgb(var(--orange-600) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: [
          'SF Pro Display',
          '-apple-system',
          'BlinkMacSystemFont',
          'Inter',
          'system-ui',
          'sans-serif',
        ],
        mono: ['SF Mono', 'Menlo', 'Monaco', 'monospace'],
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      boxShadow: {
        'soft': '0 2px 8px rgba(0, 0, 0, 0.04)',
        'medium': '0 4px 16px rgba(0, 0, 0, 0.08)',
        'strong': '0 8px 32px rgba(0, 0, 0, 0.12)',
        'glow-orange': '0 0 20px rgba(255, 103, 27, 0.18)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
}
