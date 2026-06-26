import type { Renderer } from "./Renderer";
import { type Style, type StyledLabel, type Segmenter } from "../core/types";
import { useRef } from "react";

function StaticLabeledText<S extends Style, L extends StyledLabel<S>>(props: {
	text: string;
	labels: L[];
	segment: Segmenter<S, L>;
	render: Renderer<S, L>;
	containerStyle?: React.CSSProperties;
	overlayStyle?: React.CSSProperties;
}) {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const overlayRef = useRef<HTMLDivElement | null>(null);

	const segments = props.segment(props.text, props.labels);

	const Overlay = props.render.renderOverlay;
	const Text = props.render.renderText;

	return (
		<div>
			<div ref={containerRef} style={{ position: "relative", ...props.containerStyle }}>
				<div
					ref={overlayRef}
					style={{
						position: "absolute",
						inset: 0,
						pointerEvents: "none",
						...props.overlayStyle,
					}}
				>
					{Overlay
						? segments.map((segment) => (
								<Overlay
									key={segment.start}
									segment={segment}
									containerRef={containerRef}
									overlayRef={overlayRef}
								/>
							))
						: null}
				</div>
				{segments.map((segment) => (
					<span
						key={segment.start}
						data-segment-start={segment.start}
						style={{ whiteSpace: "pre-wrap" }}
					>
						{<Text segment={segment} />}
					</span>
				))}
			</div>
		</div>
	);
}

export { StaticLabeledText };
