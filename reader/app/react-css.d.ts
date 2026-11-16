import "react";

declare module "react" {
	interface CSSProperties {
		"--reader-font-size"?: string;
		"--reader-line-height"?: string;
	}
}
