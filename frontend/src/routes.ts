export const AppRoutes = {
    LOGIN: '/login',
    DASHBOARD: '/dashboard',
    VIEW: {
        NOVELS: '/view/novels',
        NOVEL_DETAILS: '/view/novels/:novel_id',
        CHAPTER: '/view/chapters/:chapter_id',
    },
    EDIT: {
        NOVELS: '/edit/novels',
        NOVEL: '/edit/novels/:novel_id',
    },
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
        novel: (id: string) => `/view/novels/${id}`,
        chapter: (chapterId: string, options?: { revisionId?: string }) => {
            const base = `/view/chapters/${chapterId}`;
            if (options?.revisionId) return `${base}?revision_id=${options.revisionId}`;
            return base;
        }
    },
    edit: {
        novels: () => '/edit/novels',
        novel: (novelId: string, params?: { chapter?: string; revision?: string; labelsGroup?: string; nerGroup?: string }) => {
            const base = `/edit/novels/${novelId}`;
            const qs = new URLSearchParams();
            if (params?.chapter) qs.set('chapter', params.chapter);
            if (params?.revision) qs.set('revision', params.revision);
            if (params?.labelsGroup) qs.set('labelsGroup', params.labelsGroup);
            if (params?.nerGroup) qs.set('nerGroup', params.nerGroup);
            const query = qs.toString();
            return query ? `${base}?${query}` : base;
        },
    }
};
