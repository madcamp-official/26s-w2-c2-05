import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#FAF9F5",
        orange: {
          DEFAULT: "#D97757",
          dark: "#C15F3C",
          light: "#F0DCD9",
        },
        ink: "#1F1E1D",
      },
    },
  },
  plugins: [],
};

export default config;
