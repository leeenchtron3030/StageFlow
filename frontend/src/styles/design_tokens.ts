export const designTokens = {
  typography: {
    fontFamily: {
      sans: "Arial, Helvetica, sans-serif",
      mono: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    },
    fontSize: {
      body: "1rem",
      label: "0.875rem",
      display: "3rem",
    },
  },
  spacing: {
    xs: "0.25rem",
    sm: "0.5rem",
    md: "1rem",
    lg: "1.5rem",
    xl: "2rem",
  },
  borderRadius: {
    none: "0",
    sm: "0.25rem",
    md: "0.5rem",
    lg: "0.75rem",
  },
  elevation: {
    none: "none",
    low: "0 1px 2px rgb(15 23 42 / 0.08)",
    medium: "0 8px 24px rgb(15 23 42 / 0.12)",
  },
  animationDurations: {
    fast: "120ms",
    base: "180ms",
    slow: "240ms",
  },
  breakpoints: {
    sm: "40rem",
    md: "48rem",
    lg: "64rem",
    xl: "80rem",
  },
  semanticColors: {
    background: "var(--background)",
    foreground: "var(--foreground)",
    surface: "var(--surface)",
    muted: "var(--muted)",
    mutedForeground: "var(--muted-foreground)",
    border: "var(--border)",
    accent: "var(--accent)",
    accentForeground: "var(--accent-foreground)",
  },
} as const;

export type DesignTokens = typeof designTokens;
