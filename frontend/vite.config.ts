import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
	plugins: [react(), tailwindcss()],
	server: {
		watch: {
			ignored: ["**/.git/**", "**/node_modules/**", "**/.pnpm-store/**"],
			usePolling: true,
		},
		host: "0.0.0.0",
		strictPort: true,
		proxy: {
			"/api": {
				target: "http://backend:8000",
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, ""),
			},
		},
		allowedHosts: ["localhost", "frontend"],
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
	},
});
