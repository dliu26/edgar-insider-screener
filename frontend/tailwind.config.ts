import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          900: "#0f1117",
          800: "#161b27",
          700: "#1e2535",
          600: "#252d40",
        },
        accent: {
          green: "#22c55e",
          red: "#f87171",
          orange: "#fb923c",
          yellow: "#facc15",
        },
      },
    },
  },
  plugins: [],
};
export default config;
