import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
	index("routes/home.tsx"),
	route("settings", "routes/settings.ts"),
	route("admin", "routes/admin.ts"),
	route("admin/login", "routes/admin.login.tsx"),
	route("admin/dashboard", "routes/admin.dashboard.tsx"),
	route("novel/:novelId", "routes/novel.tsx"),
	route("novel/:novelId/:chapterNum", "routes/chapter.tsx"),
	route("*", "routes/not-found.tsx"),
] satisfies RouteConfig;
