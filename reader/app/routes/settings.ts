import { data, redirect } from "react-router";
import {
	applySettingsOp,
	isSettingsOp,
	parseSettings,
	safeReturnTo,
	serializeSettings,
} from "../lib/settings";
import type { Route } from "./+types/settings";

export function loader() {
	return redirect("/");
}

export async function action({ request }: Route.ActionArgs) {
	const form = await request.formData();
	const op = form.get("op");
	const current = parseSettings(request.headers.get("Cookie"));
	const next = isSettingsOp(op) ? applySettingsOp(current, op) : current;
	const headers = { "Set-Cookie": serializeSettings(next) };

	if (form.get("js") === "1") {
		return data({ settings: next }, { headers });
	}
	return redirect(safeReturnTo(form.get("returnTo")), { headers });
}
