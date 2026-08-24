export type Loadable<T> =
	| { status: "idle" }
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; data: T };

export interface Page<T> {
	items: readonly T[];
	start: number;
	end: number;
	total?: number;
	hasPrevious: boolean;
	hasNext: boolean;
}
