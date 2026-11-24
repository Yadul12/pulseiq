/** PulseIQ enterprise visual theme configuration */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"]
      },
      colors: {
        navy: {
          950: "#08101E",
          900: "#0B1628",
          800: "#12223C",
          700: "#1C3254",
          600: "#28436D"
        },
        workspace: "#F4F6F9",
        tone: {
          positive: "#2E7D63",
          neutral: "#5B6B7F",
          mixed: "#A87020",
          negative: "#B4434A"
        }
      }
    }
  },
  plugins: []
};
