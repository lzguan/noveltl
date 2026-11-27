import { redirect } from "react-router";

const NO_STORE_HEADERS = { "Cache-Control": "no-store" };

export function loader() {
	return redirect("/admin/dashboard", { headers: NO_STORE_HEADERS });
}
