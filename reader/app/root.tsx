import type { ReactNode } from "react";
import {
	isRouteErrorResponse,
	Link,
	Links,
	Meta,
	Outlet,
	Scripts,
	ScrollRestoration,
} from "react-router";
import { useReaderSettings } from "./components/SettingsBar";
import { parseSettings } from "./lib/settings";
import type { Route } from "./+types/root";
import "./app.css";

export function loader({ request }: Route.LoaderArgs) {
	return { settings: parseSettings(request.headers.get("Cookie")) };
}

export function Layout({ children }: { children: ReactNode }) {
	const settings = useReaderSettings();
	return (
		<html
			lang="en"
			data-theme={settings.theme}
			style={{
				colorScheme: settings.theme,
				"--reader-font-size": `${settings.fontSize}px`,
				"--reader-line-height": String(settings.lineHeight),
			}}
		>
			<head>
				<meta charSet="utf-8" />
				<meta name="viewport" content="width=device-width, initial-scale=1" />
				<link rel="icon" href="data:," />
				<Meta />
				<Links />
			</head>
			<body>
				{children}
				<ScrollRestoration />
				<Scripts />
			</body>
		</html>
	);
}

export default function App() {
	return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
	let title = "Something went wrong";
	let message = "An unexpected error occurred while loading this page.";

	if (isRouteErrorResponse(error)) {
		if (error.status === 404) {
			title = "Not found";
			message = "This page does not exist, or it is not available to read.";
		} else if (error.status === 503 || error.status === 502) {
			title = "Library unavailable";
			message = "The library server could not be reached. Please try again in a moment.";
		}
	} else if (import.meta.env.DEV && error instanceof Error) {
		message = error.message;
	}

	return (
		<main className="mx-auto max-w-prose px-4 py-16 text-center">
			<title>{`${title} · Reader`}</title>
			<h1 className="mb-3 text-2xl font-semibold">{title}</h1>
			<p className="mb-6 text-muted">{message}</p>
			<Link to="/" className="underline">
				Back to the library
			</Link>
		</main>
	);
}
