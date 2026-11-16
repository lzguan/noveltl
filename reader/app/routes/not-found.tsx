import { notFound } from "../lib/api.server";

export function loader(): never {
	notFound();
}

export default function NotFoundRoute() {
	return null;
}
