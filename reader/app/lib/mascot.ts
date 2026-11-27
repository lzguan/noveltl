import type { FeedbackEmoji } from "./feedbackAnchor";

export type MascotState = "idle" | "listening" | "happy" | FeedbackEmoji;

export type MascotConfig = {
	name: string;
	prompt: string;
	sprites: Partial<Record<MascotState, string>>;
	animationClasses: Record<MascotState, string>;
};

export const DEFAULT_MASCOT_CONFIG: MascotConfig = {
	name: "Inky",
	prompt: "Give Inky feedback",
	sprites: {},
	animationClasses: {
		idle: "inky-mascot",
		listening: "inky-mascot",
		happy: "inky-mascot-happy",
		love: "inky-react-love",
		funny: "inky-react-funny",
		shocked: "inky-react-shocked",
		sad: "inky-react-sad",
		confused: "inky-react-confused",
	},
};
