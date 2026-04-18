export const AppRoutes = {
    LOGIN: '/login',
    DASHBOARD: '/dashboard',
    VIEW: {
        SOURCEWORKS: '/view/sourceworks',
        SOURCEWORK_DETAILS: '/view/sourceworks/:sourcework_id',
        NOVELS: '/view/novels',
        NOVEL_DETAILS: '/view/novels/:novel_id',
        CHAPTER: '/view/chapters/:chapter_id',
    },
    EDIT: {
        NOVELS: '/edit/novels',
        NOVEL: '/edit/novels/:novel_id',
    },
    TEST: "/test"
} as const;

export const routeTo = {
    view: {
        sourceworks: (options?: { search?: string }) => {
            const params = new URLSearchParams();
            if (options?.search) params.set('search', options.search);
            const query = params.toString();
            return query ? `/view/sourceworks?${query}` : '/view/sourceworks';
        },
        sourcework: (id: string) => `/view/sourceworks/${id}`,

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
        novel: (novelId: string, params?: { chapter?: string; labelsGroup?: string; nerGroup?: string }) => {
            const base = `/edit/novels/${novelId}`;
            const qs = new URLSearchParams();
            if (params?.chapter) qs.set('chapter', params.chapter);
            if (params?.labelsGroup) qs.set('labelsGroup', params.labelsGroup);
            if (params?.nerGroup) qs.set('nerGroup', params.nerGroup);
            const query = qs.toString();
            return query ? `${base}?${query}` : base;
        },
    }
};

export const extractParams = {
    view: {
        sourceworks: (searchParams: URLSearchParams) => ({
            search: searchParams.get('search') || undefined,
        }),
        novels: (searchParams: URLSearchParams) => ({
            mine: searchParams.get('mine') === 'true',
            search: searchParams.get('search') || undefined,
        }),
        chapter: (searchParams: URLSearchParams) => ({
            revisionId: searchParams.get('revision_id') || undefined,
        }),
    },
    edit: {
        novel: (searchParams: URLSearchParams) => ({
            chapter: searchParams.get('chapter') || undefined,
            labelsGroup: searchParams.get('labelsGroup') || undefined,
            nerGroup: searchParams.get('nerGroup') || undefined,
        })

    }
}
