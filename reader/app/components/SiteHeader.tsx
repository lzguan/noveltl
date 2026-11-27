import type { ReactNode } from "react";
import { Link } from "react-router";
import { SettingsBar } from "./SettingsBar";

export function SiteHeader({ extra }: { extra?: ReactNode }) {
	return (
		<header className="border-b border-line">
			<div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-3">
				<Link to="/" className="font-semibold text-ink no-underline">
					Reader
				</Link>
				<div className="flex flex-wrap items-center justify-center gap-3">
					<SettingsBar />
					{extra}
				</div>
			</div>
		</header>
	);
}
