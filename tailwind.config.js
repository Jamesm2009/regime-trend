/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0B0E11",
        panel: "#14181D",
        hairline: "#262B31",
        text: "#E8EAED",
        subtext: "#8A9099",
        crisis: "#C4362C",
        transitional: "#D9A441",
        calm: "#3FA796",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
        sans: ["IBM Plex Sans", "ui-sans-serif", "sans-serif"],
      },
    },
  },
  plugins: [],
};
