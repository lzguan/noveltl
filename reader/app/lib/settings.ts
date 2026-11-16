export const SETTINGS_COOKIE = "reader_settings";

export const FONT_SIZES = [15, 16, 17, 18, 20, 22, 24, 27, 30] as const;
export const LINE_HEIGHTS = [1.5, 1.65, 1.8, 2, 2.2] as const;
export const THEMES = ["light", "dark"] as const;

export type Theme = (typeof THEMES)[number];

export type ReaderSettings = {
	fontSize: number;
	lineHeight: number;
	theme: Theme;
};

export const DEFAULT_SETTINGS: ReaderSettings = {
	fontSize: 18,
	lineHeight: 1.8,
	theme: "light",
};

export const SETTINGS_OPS = [
	"font-smaller",
	"font-larger",
	"spacing-tighter",
	"spacing-looser",
	"theme-light",
	"theme-dark",
] as const;

export type SettingsOp = (typeof SETTINGS_OPS)[number];

function isTheme(value: string | null): value is Theme {
	return THEMES.some((theme) => theme === value);
}

export function isSettingsOp(value: unknown): value is SettingsOp {
	return SETTINGS_OPS.some((op) => op === value);
}

function pick(options: readonly number[], value: string | null, fallback: number): number {
	if (value === null) return fallback;
	const parsed = Number(value);
	return options.includes(parsed) ? parsed : fallback;
}

function readCookie(cookieHeader: string | null, name: string): string | null {
	if (!cookieHeader) return null;
	for (const part of cookieHeader.split(";")) {
		const index = part.indexOf("=");
		if (index === -1) continue;
		if (part.slice(0, index).trim() !== name) continue;
		try {
			return decodeURIComponent(part.slice(index + 1).trim());
		} catch {
			return null;
		}
	}
	return null;
}

export function parseSettings(cookieHeader: string | null): ReaderSettings {
	const raw = readCookie(cookieHeader, SETTINGS_COOKIE);
	if (!raw) return DEFAULT_SETTINGS;
	const params = new URLSearchParams(raw);
	const theme = params.get("theme");
	return {
		fontSize: pick(FONT_SIZES, params.get("fontSize"), DEFAULT_SETTINGS.fontSize),
		lineHeight: pick(LINE_HEIGHTS, params.get("lineHeight"), DEFAULT_SETTINGS.lineHeight),
		theme: isTheme(theme) ? theme : DEFAULT_SETTINGS.theme,
	};
}

export function serializeSettings(settings: ReaderSettings): string {
	const value = new URLSearchParams({
		fontSize: String(settings.fontSize),
		lineHeight: String(settings.lineHeight),
		theme: settings.theme,
	}).toString();
	const oneYear = 60 * 60 * 24 * 365;
	return `${SETTINGS_COOKIE}=${encodeURIComponent(value)}; Path=/; Max-Age=${oneYear}; SameSite=Lax`;
}

function step(options: readonly number[], current: number, direction: 1 | -1): number {
	const index = options.indexOf(current);
	const fallback = direction === 1 ? 0 : options.length - 1;
	const next = index === -1 ? fallback : index + direction;
	return options[Math.min(Math.max(next, 0), options.length - 1)] ?? current;
}

export function applySettingsOp(settings: ReaderSettings, op: SettingsOp): ReaderSettings {
	switch (op) {
		case "font-smaller":
			return { ...settings, fontSize: step(FONT_SIZES, settings.fontSize, -1) };
		case "font-larger":
			return { ...settings, fontSize: step(FONT_SIZES, settings.fontSize, 1) };
		case "spacing-tighter":
			return { ...settings, lineHeight: step(LINE_HEIGHTS, settings.lineHeight, -1) };
		case "spacing-looser":
			return { ...settings, lineHeight: step(LINE_HEIGHTS, settings.lineHeight, 1) };
		case "theme-light":
			return { ...settings, theme: "light" };
		case "theme-dark":
			return { ...settings, theme: "dark" };
	}
}

export function safeReturnTo(value: unknown): string {
	if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
		return "/";
	}
	if (value.includes("\\")) return "/";
	return value;
}
