import type { MouseEvent } from "react";
import {
	type ShouldRevalidateFunctionArgs,
	useFetcher,
	useLocation,
	useRouteLoaderData,
} from "react-router";
import {
	applySettingsOp,
	DEFAULT_SETTINGS,
	FONT_SIZES,
	isSettingsOp,
	LINE_HEIGHTS,
	type ReaderSettings,
	type SettingsOp,
} from "../lib/settings";
import type { loader as rootLoader } from "../root";

const SETTINGS_FETCHER_KEY = "reader-settings";

export function useReaderSettings(): ReaderSettings {
	const rootData = useRouteLoaderData<typeof rootLoader>("root");
	const fetcher = useFetcher({ key: SETTINGS_FETCHER_KEY });
	const settings = rootData?.settings ?? DEFAULT_SETTINGS;
	const pendingOp = fetcher.formData?.get("op");
	return isSettingsOp(pendingOp) ? applySettingsOp(settings, pendingOp) : settings;
}

export function revalidateUnlessSettings({
	formAction,
	defaultShouldRevalidate,
}: ShouldRevalidateFunctionArgs): boolean {
	return formAction === "/settings" ? false : defaultShouldRevalidate;
}

const buttonClass =
	"min-w-10 rounded border border-line px-2.5 py-1 text-sm hover:bg-hover disabled:opacity-40";

export function SettingsBar() {
	const settings = useReaderSettings();
	const fetcher = useFetcher({ key: SETTINGS_FETCHER_KEY });
	const location = useLocation();

	function submit(event: MouseEvent<HTMLButtonElement>) {
		event.preventDefault();
		fetcher.submit(
			{ op: event.currentTarget.value, js: "1" },
			{ method: "post", action: "/settings" },
		);
	}

	const button = (op: SettingsOp, label: string, title: string, disabled = false) => (
		<button
			type="submit"
			name="op"
			value={op}
			title={title}
			aria-label={title}
			disabled={disabled}
			onClick={submit}
			className={buttonClass}
		>
			{label}
		</button>
	);

	return (
		<form
			method="post"
			action="/settings"
			className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-muted"
		>
			<input type="hidden" name="returnTo" value={location.pathname + location.search} />
			<span className="flex items-center gap-1">
				{button(
					"font-smaller",
					"A−",
					"Smaller text",
					settings.fontSize <= Math.min(...FONT_SIZES),
				)}
				<span className="w-10 text-center text-sm tabular-nums">{settings.fontSize}px</span>
				{button(
					"font-larger",
					"A+",
					"Larger text",
					settings.fontSize >= Math.max(...FONT_SIZES),
				)}
			</span>
			<span className="flex items-center gap-1">
				{button(
					"spacing-tighter",
					"≡−",
					"Tighter line spacing",
					settings.lineHeight <= Math.min(...LINE_HEIGHTS),
				)}
				<span className="w-10 text-center text-sm tabular-nums">{settings.lineHeight}</span>
				{button(
					"spacing-looser",
					"≡+",
					"Looser line spacing",
					settings.lineHeight >= Math.max(...LINE_HEIGHTS),
				)}
			</span>
			{settings.theme === "dark"
				? button("theme-light", "Light", "Switch to light theme")
				: button("theme-dark", "Dark", "Switch to dark theme")}
		</form>
	);
}
