import { createTextPositionMap } from "@/lib/textPositions";

export function labelsToUtf16<T extends { labelStart: number; labelEnd: number }>(
	text: string,
	labels: readonly T[],
): T[] {
	const positions = createTextPositionMap(text);
	return labels.map((label) => ({
		...label,
		labelStart: positions.toUtf16(label.labelStart),
		labelEnd: positions.toUtf16(label.labelEnd),
	}));
}
