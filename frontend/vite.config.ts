import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // reachable from outside the Docker container
    port: 5173,
  },
  test: {
    environment: "jsdom",
  },
});
