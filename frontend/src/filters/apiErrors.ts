function isErrorDetail(value: unknown): value is { loc: (string | number)[]; msg: string } {
	return (
		typeof value === "object" &&
		value !== null &&
		"loc" in value &&
		Array.isArray(value.loc) &&
		"msg" in value &&
		typeof value.msg === "string"
	);
}

export function apiErrorMessage(error: unknown, fallback: string) {
	if (typeof error !== "object" || error === null || !("detail" in error)) return fallback;
	if (typeof error.detail === "string") return error.detail;
	if (!Array.isArray(error.detail)) return fallback;
	const details = error.detail.filter(isErrorDetail);
	if (details.length === 0) return fallback;
	return details.map((detail) => `${detail.loc.join(".")}: ${detail.msg}`).join("; ");
}

export function requestErrorMessage(error: unknown) {
	return error instanceof Error ? error.message : "The request could not be completed.";
}
