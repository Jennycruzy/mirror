import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        mirror: {
          panel: "#0f172a",
          bg: "#020617"
        }
      }
    }
  },
  plugins: []
};

export default config;

