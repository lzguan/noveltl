export const AppRoutes = {
	ROOT: "/",
	LOGIN: "/login",
	DASHBOARD: "/dashboard",
	VIEW: {
		SOURCEWORKS: "/view/source-works",
		SOURCEWORK_DETAILS: "/view/source-works/:sourceWorkId",
		NOVELS: "/view/novels",
		NOVEL_DETAILS: "/view/novels/:novelId",
		CHAPTER: "/view/chapters/:chapterId",
	},
	EDIT: {
		DASHBOARD: "/edit",
		NOVELS: "/edit/novels",
		NOVEL: "/edit/novels/:novelId",
	},
	TEST: "/test",
} as const;

export const routeTo = {
	view: {
		sourceworks: (options?: { search?: string }) => {
			const params = new URLSearchParams();
			if (options?.search) params.set("search", options.search);
			const query = params.toString();
			return query ? `/view/source-works?${query}` : "/view/source-works";
		},
		sourcework: (id: string) => `/view/source-works/${id}`,

		novels: (options?: { mine?: boolean; search?: string }) => {
			const params = new URLSearchParams();
			if (options?.mine) params.set("mine", "true");
			if (options?.search) params.set("search", options.search);
			const query = params.toString();
			return query ? `/view/novels?${query}` : "/view/novels";
		},
		novel: (id: string, start?: number, end?: number) => {
			const base = `/view/novels/${id}`;
			if (start !== undefined && end !== undefined) {
				return `${base}?start=${start}&end=${end}`;
			} else if (start !== undefined) {
				return `${base}?start=${start}`;
			} else if (end !== undefined) {
				return `${base}?end=${end}`;
			}
			return base;
		},
		chapter: (chapterId: string, options?: { chapterContentId?: string }) => {
			const base = `/view/chapters/${chapterId}`;
			if (options?.chapterContentId)
				return `${base}?chapter-content-id=${options.chapterContentId}`;
			return base;
		},
	},
	edit: {
		dashboard: () => "/edit",
		novels: () => "/edit/novels",
		novel: (novelId: string, params?: { chapterId?: string }) => {
			const base = `/edit/novels/${novelId}`;
			const qs = new URLSearchParams();
			if (params?.chapterId) qs.set("chapter-id", params.chapterId);
			const query = qs.toString();
			return query ? `${base}?${query}` : base;
		},
	},
};

export const extractParams = {
	view: {
		sourceworks: (searchParams: URLSearchParams) => ({
			search: searchParams.get("search") || undefined,
		}),
		novels: (searchParams: URLSearchParams) => ({
			mine: searchParams.get("mine") === "true",
			search: searchParams.get("search") || undefined,
		}),
		novel: (searchParams: URLSearchParams) => ({
			start: searchParams.get("start") ? parseInt(searchParams.get("start")!) : undefined,
			end: searchParams.get("end") ? parseInt(searchParams.get("end")!) : undefined,
		}),
		chapter: (searchParams: URLSearchParams) => ({
			chapterContentId: searchParams.get("chapter-content-id") || undefined,
		}),
	},
	edit: {
		novel: (searchParams: URLSearchParams) => ({
			chapterId: searchParams.get("chapter-id") || undefined,
		}),
	},
};
