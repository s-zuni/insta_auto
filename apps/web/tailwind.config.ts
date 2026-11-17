import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { brand: { DEFAULT: "#4f46e5", dark: "#3730a3", soft: "#eef2ff" } },
      fontFamily: { sans: ["Pretendard", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
