export const AppRoutes = {
	ROOT: "/",
	LOGIN: "/login",
	SETTINGS: "/settings",
	EDIT: {
		DASHBOARD: "/edit",
		NOVELS: "/edit/novels",
		NOVEL: "/edit/novels/:novelId",
	},
	TEST: "/test",
} as const;

export const routeTo = {
	settings: () => "/settings",
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
	edit: {
		novel: (searchParams: URLSearchParams) => ({
			chapterId: searchParams.get("chapter-id") || undefined,
		}),
	},
};
