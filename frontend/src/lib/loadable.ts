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

export function pageFromOffset<T>(
	data: { count: number; rows: readonly T[] },
	skip: number,
	limit: number,
): Page<T> {
	return {
		items: data.rows,
		start: data.rows.length === 0 ? 0 : skip + 1,
		end: skip + data.rows.length,
		total: data.count,
		hasPrevious: skip > 0,
		hasNext: skip + limit < data.count,
	};
}
