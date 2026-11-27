type FeedbackMascotProps = {
	mood?: "idle" | "listening" | "happy";
	size?: "sm" | "md";
};

export function FeedbackMascot({ mood = "idle", size = "md" }: FeedbackMascotProps) {
	const dimensions = size === "sm" ? "h-8 w-8" : "h-11 w-11";

	return (
		<span
			className={`inky-mascot inline-flex shrink-0 items-center justify-center ${dimensions}`}
			aria-hidden="true"
		>
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
				<g className="inky-mascot-eyes">
					{mood === "happy" ? (
						<>
							<path
								d="M17 27.5C18 25.7 20.4 25.7 21.4 27.5"
								stroke="var(--rd-page)"
								strokeWidth="2.4"
								strokeLinecap="round"
							/>
							<path
								d="M26.6 27.5C27.6 25.7 30 25.7 31 27.5"
								stroke="var(--rd-page)"
								strokeWidth="2.4"
								strokeLinecap="round"
							/>
						</>
					) : (
						<>
							<circle cx="19" cy="27.5" r="2.4" fill="var(--rd-page)" />
							<circle cx="29" cy="27.5" r="2.4" fill="var(--rd-page)" />
						</>
					)}
				</g>
				{mood === "listening" ? (
					<circle cx="24" cy="33.5" r="2" fill="var(--rd-page)" />
				) : (
					<path
						d="M20.5 33C22 35 26 35 27.5 33"
						stroke="var(--rd-page)"
						strokeWidth="2"
						strokeLinecap="round"
					/>
				)}
			</svg>
		</span>
	);
}
