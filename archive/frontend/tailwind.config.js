/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0b0d12",
          soft:    "#11141b",
          card:    "#161a23",
          hover:   "#1c212c",
          border:  "#252b38",
        },
        accent: {
          DEFAULT: "#7c5cff",
          dim:     "#5b46c2",
          glow:    "#a18bff",
        },
        ok:    "#10b981",
        warn:  "#f59e0b",
        bad:   "#ef4444",
        muted: "#7d8597",
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(124, 92, 255, 0.25)",
      },
    },
  },
  plugins: [],
};
