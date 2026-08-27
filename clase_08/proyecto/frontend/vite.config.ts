import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react-swc"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({ plugins: [react(), tailwindcss() as never], server: { proxy: { "/api": "http://localhost:8000" } }, test: { environment: "jsdom", setupFiles: "./src/test/setup.ts" } })
