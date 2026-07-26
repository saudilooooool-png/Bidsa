import type { Config } from "tailwindcss";

/**
 * Colors map to CSS custom properties defined in globals.css, where the
 * light/dark values live (validated data-viz reference palette).
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "var(--surface-1)",
        page: "var(--page)",
        ink: "var(--text-primary)",
        "ink-2": "var(--text-secondary)",
        muted: "var(--text-muted)",
        grid: "var(--gridline)",
        accent: "var(--series-1)",
        "accent-soft": "var(--series-1-soft)",
        good: "var(--status-good)",
        warning: "var(--status-warning)",
        serious: "var(--status-serious)",
        critical: "var(--status-critical)",
      },
      borderColor: {
        DEFAULT: "var(--hairline)",
      },
    },
  },
  plugins: [],
};

export default config;
