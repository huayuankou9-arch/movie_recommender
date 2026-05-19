import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070B14",
        panel: "#101827",
        neon: "#00E0FF",
        coral: "#FF5D73",
        gold: "#FFCA56"
      },
      boxShadow: {
        glow: "0 12px 40px rgba(0,224,255,0.18)"
      }
    }
  },
  plugins: []
} satisfies Config;
