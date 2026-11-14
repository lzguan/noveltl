import type { TranslationPipelineCheck } from "@/api/models";

export function layout(check: TranslationPipelineCheck) {
	const streams = new Map<string, { stream: string; type: string; x: number }>();
	for (const stage of check.stages) {
		for (const port of [...stage.inputs, ...stage.outputs]) {
			if (!streams.has(port.stream))
				streams.set(port.stream, {
					stream: port.stream,
					type: port.type,
					x: 210 + streams.size * 110,
				});
		}
	}
	for (const end of check.ends) {
		if (!streams.has(end.stream))
			streams.set(end.stream, {
				stream: end.stream,
				type: end.type,
				x: 210 + streams.size * 110,
			});
	}
	const lanes = [...streams.values()];
	const rows = check.stages.map((stage, row) => ({
		row,
		y: 76 + row * 96,
		bottom: 110 + row * 96,
		action: stage.action,
		label: row === 0 ? "Load inputs" : stage.action.replaceAll("_", " "),
		warning: stage.warning,
		hasWarning: stage.warning !== null,
	}));
	const ports = check.stages.flatMap((stage, row) => [
		...stage.inputs.map((port) => ({
			...port,
			kind: "input" as const,
			lane: port.stream,
			row,
			x: streams.get(port.stream)!.x,
			y: rows[row].y,
		})),
		...stage.outputs.map((port) => ({
			...port,
			kind: "output" as const,
			lane: port.stream,
			row,
			x: streams.get(port.stream)!.x,
			y: rows[row].bottom,
		})),
	]);
	const bottom = (rows.at(-1)?.bottom ?? 76) + 48;
	const segments = [
		...ports.flatMap((port) =>
			port.kind === "input" && port.source !== null
				? [
						{
							stream: port.stream,
							source: port.source,
							row: port.row,
							link: port.link,
							kind: "input" as const,
							x: port.x,
							y1: rows[port.source].bottom,
							y2: port.y,
						},
					]
				: [],
		),
		...check.ends.map((end) => ({
			stream: end.stream,
			source: end.source,
			row: end.source,
			link: "end" as const,
			kind: "end" as const,
			x: streams.get(end.stream)!.x,
			y1: rows[end.source].bottom,
			y2: bottom,
		})),
	];
	const stubs = ports.flatMap((port) =>
		port.kind === "input" && port.link === "broken"
			? [{ stream: port.stream, row: port.row, x: port.x, y1: port.y - 20, y2: port.y }]
			: [],
	);
	return {
		lanes,
		rows,
		ports,
		segments,
		stubs,
		width: 170 + lanes.length * 110,
		height: bottom + 32,
	};
}
