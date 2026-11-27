import { DEFAULT_MASCOT_CONFIG, type MascotConfig, type MascotState } from "../lib/mascot";

export type { MascotConfig, MascotState };

type FeedbackMascotProps = {
	state?: MascotState;
	size?: "sm" | "md";
	config?: MascotConfig;
};

function MascotFace({ state }: { state: MascotState }) {
	if (state === "happy" || state === "love") {
		return (
			<>
				<g className="inky-mascot-eyes">
					<path
						d="M16.5 27.5C17.6 25.4 20.4 25.4 21.5 27.5"
						stroke="var(--rd-page)"
						strokeWidth="2.4"
						strokeLinecap="round"
					/>
					<path
						d="M26.5 27.5C27.6 25.4 30.4 25.4 31.5 27.5"
						stroke="var(--rd-page)"
						strokeWidth="2.4"
						strokeLinecap="round"
					/>
				</g>
				<path
					d="M20 32.5C21.8 35 26.2 35 28 32.5"
					stroke="var(--rd-page)"
					strokeWidth="2"
					strokeLinecap="round"
				/>
			</>
		);
	}

	if (state === "funny") {
		return (
			<>
				<g className="inky-mascot-eyes">
					<path
						d="M16.5 26L21 27.5L16.5 29"
						stroke="var(--rd-page)"
						strokeWidth="2.2"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
					<path
						d="M31.5 26L27 27.5L31.5 29"
						stroke="var(--rd-page)"
						strokeWidth="2.2"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
				</g>
				<path d="M19.5 32.5Q24 37 28.5 32.5Z" fill="var(--rd-page)" />
			</>
		);
	}

	if (state === "shocked") {
		return (
			<>
				<g>
					<circle cx="19" cy="27" r="3.1" fill="var(--rd-page)" />
					<circle cx="29" cy="27" r="3.1" fill="var(--rd-page)" />
				</g>
				<ellipse cx="24" cy="34" rx="2.6" ry="3.2" fill="var(--rd-page)" />
			</>
		);
	}

	if (state === "sad") {
		return (
			<>
				<g className="inky-mascot-eyes">
					<circle cx="19" cy="28" r="2.2" fill="var(--rd-page)" />
					<circle cx="29" cy="28" r="2.2" fill="var(--rd-page)" />
					<circle cx="31.5" cy="31.5" r="1.4" fill="var(--rd-link-ink)" />
				</g>
				<path
					d="M20.5 35C22 33 26 33 27.5 35"
					stroke="var(--rd-page)"
					strokeWidth="2"
					strokeLinecap="round"
				/>
			</>
		);
	}

	if (state === "confused") {
		return (
			<>
				<g className="inky-mascot-eyes">
					<circle cx="19" cy="27" r="2.8" fill="var(--rd-page)" />
					<circle cx="29" cy="28" r="1.8" fill="var(--rd-page)" />
				</g>
				<path
					d="M20.5 34L27.5 32.5"
					stroke="var(--rd-page)"
					strokeWidth="2"
					strokeLinecap="round"
				/>
			</>
		);
	}

	return (
		<>
			<g className="inky-mascot-eyes">
				<circle cx="19" cy="27.5" r="2.4" fill="var(--rd-page)" />
				<circle cx="29" cy="27.5" r="2.4" fill="var(--rd-page)" />
			</g>
			{state === "listening" ? (
				<circle cx="24" cy="33.5" r="2" fill="var(--rd-page)" />
			) : (
				<path
					d="M20.5 33C22 35 26 35 27.5 33"
					stroke="var(--rd-page)"
					strokeWidth="2"
					strokeLinecap="round"
				/>
			)}
		</>
	);
}

export function FeedbackMascot({
	state = "idle",
	size = "md",
	config = DEFAULT_MASCOT_CONFIG,
}: FeedbackMascotProps) {
	const dimensions = size === "sm" ? "h-8 w-8" : "h-11 w-11";
	const animationClass = config.animationClasses[state];
	const spriteSrc = config.sprites[state] ?? config.sprites.idle;

	return (
		<span
			data-mascot-state={state}
			className={`${animationClass} inline-flex shrink-0 items-center justify-center ${dimensions}`}
			aria-hidden="true"
		>
			{spriteSrc ? (
				<img src={spriteSrc} alt="" className="h-full w-full object-contain" />
			) : (
				<svg viewBox="0 0 48 48" className="h-full w-full" fill="none">
					<path
						d="M24 5C19 13 11 19.5 11 28.5C11 36.2 16.8 42 24 42C31.2 42 37 36.2 37 28.5C37 19.5 29 13 24 5Z"
						fill="var(--rd-ink)"
					/>
					<path
						d="M17 18C18.5 15.2 21 12.2 23.5 9.2"
						stroke="var(--rd-page)"
						strokeWidth="2"
						strokeLinecap="round"
						opacity="0.35"
					/>
					<MascotFace state={state} />
				</svg>
			)}
		</span>
	);
}
