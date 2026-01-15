export const AppRoutes = {
    LOGIN: '/login',
    DASHBOARD: '/dashboard',
    VIEW: {
        NOVELS: '/view/novels',
        NOVEL_DETAILS: '/view/novels/:novel_id',
        // FIX: Match the pattern used in routeTo below
        CHAPTER: '/view/chapters/:chapter_id', 
    },
    EDIT: {
        NOVELS: '/edit/novels',
        NOVEL: '/edit/novels/:novel_id',
    }
} as const;

export const routeTo = {
    view: {
        novels: (options?: { mine?: boolean; search?: string }) => {
            const params = new URLSearchParams();
            if (options?.mine) params.set('mine', 'true');
            if (options?.search) params.set('search', options.search);
            const query = params.toString();
            return query ? `/view/novels?${query}` : '/view/novels';
        },
        novel: (id: number) => `/view/novels/${id}`,
        chapter: (chapterId: number, options?: { revisionId?: number }) => {
            const base = `/view/chapters/${chapterId}`;
            if (options?.revisionId) return `${base}?revision_id=${options.revisionId}`;
            return base;
        }
    },
    edit: {
        novels: () => '/edit/novels',
        novel: (id: number) => `/edit/novels/${id}`,
    }
};