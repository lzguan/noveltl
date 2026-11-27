import { data, Form, Link, redirect } from "react-router";
import {
	AdminApiError,
	adminLogin,
	clearAdminCookie,
	listAdminPartners,
	readAdminToken,
	serializeAdminCookie,
} from "../lib/admin.server";
import type { Route } from "./+types/admin.login";

const NO_STORE_HEADERS = { "Cache-Control": "no-store" };

export async function loader({ request }: Route.LoaderArgs) {
	const token = readAdminToken(request.headers.get("Cookie"));
	if (!token) {
		return data({ error: null }, { headers: NO_STORE_HEADERS });
	}
	try {
		await listAdminPartners(token);
		return redirect("/admin/dashboard", { headers: NO_STORE_HEADERS });
	} catch (error) {
		if (error instanceof AdminApiError && error.status === 503) {
			return data(
				{ error: "Reader admin is not configured on the server." },
				{ headers: { ...NO_STORE_HEADERS, "Set-Cookie": clearAdminCookie() } },
			);
		}
		return data(
			{ error: null },
			{ headers: { ...NO_STORE_HEADERS, "Set-Cookie": clearAdminCookie() } },
		);
	}
}

export async function action({ request }: Route.ActionArgs) {
	const formData = await request.formData();
	const usernameRaw = formData.get("username");
	const passwordRaw = formData.get("password");
	const username = typeof usernameRaw === "string" ? usernameRaw.trim() : "";
	const password = typeof passwordRaw === "string" ? passwordRaw : "";

	if (!username || !password) {
		return data(
			{ error: "Enter both username and password." },
			{ status: 400, headers: NO_STORE_HEADERS },
		);
	}

	try {
		const result = await adminLogin(username, password);
		const expiresMs = Date.parse(result.expiresAt);
		const maxAgeSeconds = Number.isNaN(expiresMs)
			? undefined
			: Math.max(0, Math.floor((expiresMs - Date.now()) / 1000));
		return redirect("/admin/dashboard", {
			headers: {
				...NO_STORE_HEADERS,
				"Set-Cookie": serializeAdminCookie(result.accessToken, maxAgeSeconds),
			},
		});
	} catch (error) {
		if (error instanceof AdminApiError) {
			if (error.status === 401) {
				return data(
					{ error: "Invalid username or password." },
					{ status: 401, headers: NO_STORE_HEADERS },
				);
			}
			if (error.status === 503) {
				return data(
					{ error: "Reader admin is not configured on the server." },
					{ status: 503, headers: NO_STORE_HEADERS },
				);
			}
			return data(
				{ error: error.detail },
				{ status: error.status >= 400 ? error.status : 502, headers: NO_STORE_HEADERS },
			);
		}
		return data(
			{ error: "Unable to sign in right now. Please try again." },
			{ status: 502, headers: NO_STORE_HEADERS },
		);
	}
}

export function headers() {
	return NO_STORE_HEADERS;
}

export function meta() {
	return [{ title: "Admin Sign In · Reader" }];
}

export default function AdminLoginPage({ loaderData, actionData }: Route.ComponentProps) {
	const errorMessage = actionData?.error ?? loaderData.error;
	return (
		<main className="mx-auto max-w-sm px-4 py-12">
			<div className="mb-6 flex items-baseline justify-between">
				<h1 className="text-xl font-semibold">Reader Admin</h1>
				<Link to="/" className="text-sm">
					Back to library
				</Link>
			</div>

			{errorMessage ? (
				<p
					role="alert"
					className="mb-4 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300"
				>
					{errorMessage}
				</p>
			) : null}

			<Form method="post" className="space-y-4 rounded border border-line p-5">
				<div>
					<label htmlFor="admin-username" className="mb-1 block text-sm font-medium">
						Username
					</label>
					<input
						id="admin-username"
						name="username"
						type="text"
						required
						autoComplete="username"
						className="w-full rounded border border-line bg-page px-3 py-2 text-sm text-ink"
					/>
				</div>

				<div>
					<label htmlFor="admin-password" className="mb-1 block text-sm font-medium">
						Password
					</label>
					<input
						id="admin-password"
						name="password"
						type="password"
						required
						autoComplete="current-password"
						className="w-full rounded border border-line bg-page px-3 py-2 text-sm text-ink"
					/>
				</div>

				<button
					type="submit"
					className="w-full cursor-pointer rounded border border-line px-4 py-2 text-sm font-medium hover:bg-hover"
				>
					Sign in
				</button>
			</Form>
		</main>
	);
}
