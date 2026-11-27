const DEFAULT_BACKEND_URL = "http://reader-api:8001";
const TIMEOUT_MS = 10_000;

export const ADMIN_TOKEN_COOKIE = "reader_admin_token";

export type AdminLoginResult = {
	accessToken: string;
	expiresAt: string;
};

export type AdminPartnerKey = {
	keyId: string;
	keyPrefix: string;
	createdAt: string;
	revokedAt: string | null;
};

export type AdminPartner = {
	partnerId: string;
	name: string;
	createdAt: string;
	novelCount: number;
	keys: AdminPartnerKey[];
};

export type AdminPartnerCreated = {
	partnerId: string;
	name: string;
	createdAt: string;
};

export type AdminMintedKey = {
	keyId: string;
	keyPrefix: string;
	apiKey: string;
	createdAt: string;
};

export type AdminNovel = {
	novelId: string;
	title: string;
	author: string | null;
	languageCode: string;
	partnerId: string | null;
	partnerName: string | null;
	chapterCount: number;
	updatedAt: string;
	publicUrl: string;
};

export class AdminApiError extends Error {
	readonly status: number;
	readonly detail: string;

	constructor(status: number, detail: string) {
		super(detail);
		this.name = "AdminApiError";
		this.status = status;
		this.detail = detail;
	}
}

function backendBaseUrl(): string {
	const configured = process.env.READER_BACKEND_URL?.trim();
	return (configured || DEFAULT_BACKEND_URL).replace(/\/+$/, "");
}

function isProduction(): boolean {
	return process.env.NODE_ENV === "production";
}

export function readAdminToken(cookieHeader: string | null): string | null {
	if (!cookieHeader) return null;
	for (const part of cookieHeader.split(";")) {
		const index = part.indexOf("=");
		if (index === -1) continue;
		if (part.slice(0, index).trim() !== ADMIN_TOKEN_COOKIE) continue;
		try {
			const decoded = decodeURIComponent(part.slice(index + 1).trim());
			return decoded.length > 0 ? decoded : null;
		} catch {
			return null;
		}
	}
	return null;
}

export function serializeAdminCookie(token: string, maxAgeSeconds?: number): string {
	const parts = [
		`${ADMIN_TOKEN_COOKIE}=${encodeURIComponent(token)}`,
		"HttpOnly",
		"SameSite=Lax",
		"Path=/admin",
	];
	if (typeof maxAgeSeconds === "number" && Number.isFinite(maxAgeSeconds)) {
		parts.push(`Max-Age=${Math.max(0, Math.floor(maxAgeSeconds))}`);
	}
	if (isProduction()) {
		parts.push("Secure");
	}
	return parts.join("; ");
}

export function clearAdminCookie(): string {
	const parts = [
		`${ADMIN_TOKEN_COOKIE}=`,
		"HttpOnly",
		"SameSite=Lax",
		"Path=/admin",
		"Max-Age=0",
	];
	if (isProduction()) {
		parts.push("Secure");
	}
	return parts.join("; ");
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function expectString(record: Record<string, unknown>, key: string): string {
	const value = record[key];
	if (typeof value !== "string") {
		throw new AdminApiError(502, `Unexpected admin response: missing string field "${key}"`);
	}
	return value;
}

function expectNullableString(record: Record<string, unknown>, key: string): string | null {
	const value = record[key];
	if (value === null || value === undefined) return null;
	if (typeof value !== "string") {
		throw new AdminApiError(502, `Unexpected admin response: invalid string field "${key}"`);
	}
	return value;
}

function expectNumber(record: Record<string, unknown>, key: string): number {
	const value = record[key];
	if (typeof value !== "number") {
		throw new AdminApiError(502, `Unexpected admin response: missing number field "${key}"`);
	}
	return value;
}

function parseAdminKey(value: unknown): AdminPartnerKey {
	if (!isRecord(value)) {
		throw new AdminApiError(502, "Unexpected admin key payload");
	}
	return {
		keyId: expectString(value, "keyId"),
		keyPrefix: expectString(value, "keyPrefix"),
		createdAt: expectString(value, "createdAt"),
		revokedAt: expectNullableString(value, "revokedAt"),
	};
}

function parseAdminPartner(value: unknown): AdminPartner {
	if (!isRecord(value) || !Array.isArray(value.keys)) {
		throw new AdminApiError(502, "Unexpected admin partner payload");
	}
	return {
		partnerId: expectString(value, "partnerId"),
		name: expectString(value, "name"),
		createdAt: expectString(value, "createdAt"),
		novelCount: expectNumber(value, "novelCount"),
		keys: value.keys.map(parseAdminKey),
	};
}

function parseAdminNovel(value: unknown): AdminNovel {
	if (!isRecord(value)) {
		throw new AdminApiError(502, "Unexpected admin novel payload");
	}
	return {
		novelId: expectString(value, "novelId"),
		title: expectString(value, "title"),
		author: expectNullableString(value, "author"),
		languageCode: expectString(value, "languageCode"),
		partnerId: expectNullableString(value, "partnerId"),
		partnerName: expectNullableString(value, "partnerName"),
		chapterCount: expectNumber(value, "chapterCount"),
		updatedAt: expectString(value, "updatedAt"),
		publicUrl: expectString(value, "publicUrl"),
	};
}

async function extractErrorDetail(res: Response): Promise<string> {
	try {
		const payload: unknown = await res.json();
		if (isRecord(payload) && typeof payload.detail === "string" && payload.detail.trim()) {
			return payload.detail;
		}
	} catch {
		// Fall through to status text.
	}
	return `Reader API returned ${res.status}`;
}

async function adminRequest(
	path: string,
	options: { method: string; token?: string; body?: unknown },
): Promise<unknown> {
	const headers: Record<string, string> = { Accept: "application/json" };
	if (options.token) {
		headers.Authorization = `Bearer ${options.token}`;
	}
	let serializedBody: string | undefined;
	if (options.body !== undefined) {
		headers["Content-Type"] = "application/json";
		serializedBody = JSON.stringify(options.body);
	}

	let res: Response;
	try {
		res = await fetch(`${backendBaseUrl()}${path}`, {
			method: options.method,
			headers,
			body: serializedBody,
			signal: AbortSignal.timeout(TIMEOUT_MS),
		});
	} catch {
		throw new AdminApiError(503, "Reader API is unavailable.");
	}

	if (!res.ok) {
		const detail = await extractErrorDetail(res);
		throw new AdminApiError(res.status, detail);
	}

	if (res.status === 204) {
		await res.body?.cancel();
		return undefined;
	}

	try {
		return await res.json();
	} catch {
		throw new AdminApiError(502, "Reader API returned invalid JSON.");
	}
}

export async function adminLogin(username: string, password: string): Promise<AdminLoginResult> {
	const raw = await adminRequest("/admin/login", {
		method: "POST",
		body: { username, password },
	});
	if (!isRecord(raw)) {
		throw new AdminApiError(502, "Unexpected login response");
	}
	return {
		accessToken: expectString(raw, "accessToken"),
		expiresAt: expectString(raw, "expiresAt"),
	};
}

export async function listAdminPartners(token: string): Promise<AdminPartner[]> {
	const raw = await adminRequest("/admin/partners", { method: "GET", token });
	if (!Array.isArray(raw)) {
		throw new AdminApiError(502, "Unexpected partners response");
	}
	return raw.map(parseAdminPartner);
}

export async function createAdminPartner(
	token: string,
	name: string,
): Promise<AdminPartnerCreated> {
	const raw = await adminRequest("/admin/partners", {
		method: "POST",
		token,
		body: { name },
	});
	if (!isRecord(raw)) {
		throw new AdminApiError(502, "Unexpected create partner response");
	}
	return {
		partnerId: expectString(raw, "partnerId"),
		name: expectString(raw, "name"),
		createdAt: expectString(raw, "createdAt"),
	};
}

export async function mintAdminPartnerKey(
	token: string,
	partnerId: string,
): Promise<AdminMintedKey> {
	const raw = await adminRequest(`/admin/partners/${encodeURIComponent(partnerId)}/keys`, {
		method: "POST",
		token,
	});
	if (!isRecord(raw)) {
		throw new AdminApiError(502, "Unexpected mint key response");
	}
	return {
		keyId: expectString(raw, "keyId"),
		keyPrefix: expectString(raw, "keyPrefix"),
		apiKey: expectString(raw, "apiKey"),
		createdAt: expectString(raw, "createdAt"),
	};
}

export async function revokeAdminKey(token: string, keyId: string): Promise<void> {
	await adminRequest(`/admin/keys/${encodeURIComponent(keyId)}`, {
		method: "DELETE",
		token,
	});
}

export async function listAdminNovels(token: string): Promise<AdminNovel[]> {
	const raw = await adminRequest("/admin/novels", { method: "GET", token });
	if (!Array.isArray(raw)) {
		throw new AdminApiError(502, "Unexpected novels response");
	}
	return raw.map(parseAdminNovel);
}

export async function deleteAdminNovel(token: string, novelId: string): Promise<void> {
	await adminRequest(`/admin/novels/${encodeURIComponent(novelId)}`, {
		method: "DELETE",
		token,
	});
}
