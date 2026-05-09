/** @type {import('tailwindcss').Config} */
export default {
    content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
    theme: {
        extend: {
            colors: {
                bg: "#0b1220",
                card: "rgba(255,255,255,0.06)",
                stroke: "rgba(255,255,255,0.12)",
                primary: "#00e0ff",
                accent: "#ffd369",
                success: "#00ffa3",
                danger: "#ff5c7a",
                text: "#e6edf3",
                muted: "#94a3b8",
            },
            backdropBlur: { xl: "20px" },
            borderRadius: { xl: "14px", "2xl": "18px" },
            boxShadow: {
                glow: "0 0 0 1px rgba(255,255,255,0.08), 0 10px 30px rgba(0,0,0,0.4)",
            },
        },
    },
    plugins: [],
};
