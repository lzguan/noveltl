import type { TranslationPipelineCheck } from "@/api/models";
import { layout } from "./layout";

export function PipelineDiagram({ check }: { check: TranslationPipelineCheck }) {
	const drawing = layout(check);
	const summary = drawing.rows
		.map((row) => `${row.label}${row.hasWarning ? ` (warning: ${row.warning})` : ""}`)
		.join(" → ");
	return (
		<div className="min-w-0 overflow-x-auto rounded-lg border p-2">
			<svg
				role="img"
				aria-label={`Translation pipeline: ${summary}`}
				viewBox={`0 0 ${drawing.width} ${drawing.height}`}
				width={drawing.width}
				height={drawing.height}
				className="text-foreground"
			>
				{drawing.lanes.map((lane) => (
					<text
						key={lane.stream}
						x={lane.x}
						y={22}
						textAnchor="middle"
						fill="currentColor"
						fontSize={12}
					>
						{lane.stream}
						<tspan x={lane.x} dy={18} className="text-muted-foreground">
							{lane.type}
						</tspan>
					</text>
				))}
				{drawing.rows.map((row) => (
					<rect
						key={row.row}
						x={8}
						y={row.y}
						width={drawing.width - 16}
						height={row.bottom - row.y}
						rx={4}
						className="fill-muted/50 text-muted-foreground"
						stroke="currentColor"
						strokeDasharray={row.hasWarning ? "5 4" : undefined}
					>
						{row.hasWarning && <title>{row.warning}</title>}
					</rect>
				))}
				{drawing.segments.map((segment) => (
					<g key={`${segment.kind}-${segment.row}-${segment.stream}`}>
						<line
							data-stream={segment.stream}
							data-stage={segment.row}
							data-source={segment.source}
							data-link={segment.link}
							x1={segment.x}
							x2={segment.x}
							y1={segment.y1}
							y2={segment.y2}
							stroke="currentColor"
							strokeWidth={2}
						/>
						{segment.kind === "end" && (
							<text
								x={segment.x}
								y={segment.y2 + 20}
								textAnchor="middle"
								fill="currentColor"
								fontSize={12}
							>
								{segment.stream}
							</text>
						)}
					</g>
				))}
				{drawing.rows.map((row) => (
					<text
						key={row.row}
						x={18}
						y={row.y + 21}
						fill="currentColor"
						fontSize={12}
						className={row.hasWarning ? "text-muted-foreground" : undefined}
					>
						{row.label}
					</text>
				))}
				{drawing.stubs.map((stub) => (
					<path
						key={`${stub.row}-${stub.stream}`}
						data-stream={stub.stream}
						data-stage={stub.row}
						data-link="broken"
						d={`M ${stub.x} ${stub.y2} V ${stub.y1} m -4 -4 l 8 8 m -8 0 l 8 -8`}
						className="text-destructive"
						stroke="currentColor"
						strokeWidth={2}
						fill="none"
					/>
				))}
				{drawing.ports.map((port) => (
					<g key={`${port.kind}-${port.row}-${port.stream}`}>
						<circle
							data-stream={port.stream}
							data-stage={port.row}
							data-port={port.kind}
							data-link={port.kind === "input" ? port.link : "output"}
							cx={port.x}
							cy={port.y}
							r={4}
							stroke="currentColor"
							strokeWidth={2}
							className={
								port.kind === "input" &&
								(port.link === "broken" || port.link === "incompatible")
									? "text-destructive"
									: port.kind === "input" && port.link === "absent"
										? "text-muted-foreground fill-background"
										: undefined
							}
							fill={
								port.kind === "input" && port.link === "absent"
									? undefined
									: "currentColor"
							}
						>
							<title>{`${port.stream}: ${port.type}${port.kind === "input" ? `, ${port.link}${port.optional ? ", optional" : ""}${port.drops ? ", ends here" : ""}` : ", output"}`}</title>
						</circle>
						{port.kind === "input" && port.drops && (
							<line
								x1={port.x - 8}
								x2={port.x + 8}
								y1={port.y}
								y2={port.y}
								stroke="currentColor"
								strokeWidth={3}
							/>
						)}
					</g>
				))}
			</svg>
		</div>
	);
}
