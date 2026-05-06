import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        /* App-specific brand (Chat = Blue) */
        brand: {
          DEFAULT: "#3B82F6",
          light: "#60A5FA",
          deep: "#1D4ED8",
          wash: "rgba(59, 130, 246, 0.08)",
        },
        /* DKube Design System */
        dk: {
          purple: {
            DEFAULT: "#6B53A3",
            light: "#9985BF",
            deep: "#4A3A7A",
            wash: "rgba(107, 83, 163, 0.08)",
          },
          surface: {
            DEFAULT: "#0E0E10",
            raised: "#1F1F23",
            elevated: "#2A2A30",
          },
          border: "rgba(255, 255, 255, 0.08)",
          body: "#F4F2F8",
          muted: {
            DEFAULT: "#9E9AAB",
            darker: "#6E6E76",
          },
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-manrope)", "Manrope", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        "dk-sm": "0 1px 2px rgba(0, 0, 0, 0.25)",
        "dk-md": "0 4px 12px rgba(0, 0, 0, 0.35)",
        "dk-lg": "0 8px 24px rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};

export default config;
