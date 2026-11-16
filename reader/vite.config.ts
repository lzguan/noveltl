import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
	plugins: [tailwindcss(), reactRouter()],
	server: {
		host: "0.0.0.0",
		port: 5174,
		strictPort: true,
		allowedHosts: ["localhost", "reader"],
		watch: {
			ignored: ["**/.git/**", "**/node_modules/**", "**/.pnpm-store/**"],
			usePolling: true,
		},
	},
});
