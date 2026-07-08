import type { AutoLabelRunView } from "../../hooks/useAutoLabelState";

export function formatRunLabel(run: AutoLabelRunView): string {
	if (run.run.servId === null) return "Run pending";
	return `Run ${run.run.servId.slice(0, 8)}`;
}
