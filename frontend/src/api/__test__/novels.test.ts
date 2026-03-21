import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getNovels,
    getNovelsMine,
    getNovelById,
    getChaptersByNovel,
    getChapterById,
    getChapterRevisionById,
    getChapterRevisionsByNovel,
    getChapterRevisionsByChapter,
    createNovel,
    createChapterForNovel,
    createRevisionForChapter
} from '../novels'
import * as NovelType from '../../types/novel'

vi.mock('../client')

describe('Novels API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getNovels', () => {
        it('should call GET /novels with title-contains query param', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: []
            })

            await getNovels('test')

            expect(client.get).toHaveBeenCalledWith('/novels', {
                params: { 'title-contains': 'test' }
            })
        })

        it('should map each novel from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        novel_id: 1,
                        novel_title: 'Test Novel',
                        novel_description: 'A test',
                        novel_author: 'Author',
                        novel_visibility: 3,
                        novel_type: 'original',
                        novel_parent_id: null,
                        language_code: 'en'
                    }
                ]
            })

            const result = await getNovels()

            expectTypeOf(result).toEqualTypeOf<NovelType.Novel[]>()
            expect(result).toEqual([
                {
                    novelId: 1,
                    novelTitle: 'Test Novel',
                    novelDescription: 'A test',
                    novelAuthor: 'Author',
                    novelVisibility: 3,
                    novelType: 'original',
                    novelParentId: null,
                    languageCode: 'en'
                }
            ] satisfies NovelType.Novel[])
        })

        it('should pass title-contains as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getNovels()

            expect(client.get).toHaveBeenCalledWith('/novels', {
                params: { 'title-contains': undefined }
            })
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getNovels()

            expect(result).toEqual([])
        })
    })

    describe('getNovelsMine', () => {
        it('should call GET /novels/mine with editable and title-contains params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getNovelsMine(true, 'search')

            expect(client.get).toHaveBeenCalledWith('/novels/mine', {
                params: { editable: true, 'title-contains': 'search' }
            })
        })

        it('should map each novel from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        novel_id: 2,
                        novel_title: 'My Novel',
                        novel_description: null,
                        novel_author: null,
                        novel_visibility: 0,
                        novel_type: 'translation',
                        novel_parent_id: 1,
                        language_code: 'zh'
                    }
                ]
            })

            const result = await getNovelsMine(false)

            expect(result).toEqual([
                {
                    novelId: 2,
                    novelTitle: 'My Novel',
                    novelDescription: null,
                    novelAuthor: null,
                    novelVisibility: 0,
                    novelType: 'translation',
                    novelParentId: 1,
                    languageCode: 'zh'
                }
            ] satisfies NovelType.Novel[])
        })

        it('should pass title-contains as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getNovelsMine(false)

            expect(client.get).toHaveBeenCalledWith('/novels/mine', {
                params: { editable: false, 'title-contains': undefined }
            })
        })
    })

    describe('getNovelById', () => {
        it('should call GET /novels/{novelId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    novel_id: 5,
                    novel_title: 'Test',
                    novel_description: null,
                    novel_author: null,
                    novel_visibility: 2,
                    novel_type: 'original',
                    novel_parent_id: null,
                    language_code: 'en'
                }
            })

            await getNovelById(5)

            expect(client.get).toHaveBeenCalledWith('/novels/5')
        })

        it('should map all novel fields from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    novel_id: 10,
                    novel_title: 'Full Novel',
                    novel_description: 'Description here',
                    novel_author: 'John Doe',
                    novel_visibility: 3,
                    novel_type: 'other',
                    novel_parent_id: 8,
                    language_code: 'jp'
                }
            })

            const result = await getNovelById(10)

            expectTypeOf(result).toEqualTypeOf<NovelType.Novel>()
            expect(result).toEqual({
                novelId: 10,
                novelTitle: 'Full Novel',
                novelDescription: 'Description here',
                novelAuthor: 'John Doe',
                novelVisibility: 3,
                novelType: 'other',
                novelParentId: 8,
                languageCode: 'jp'
            } satisfies NovelType.Novel)
        })

        it('should handle nullable fields correctly when null', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    novel_id: 7,
                    novel_title: 'Minimal',
                    novel_description: null,
                    novel_author: null,
                    novel_visibility: 1,
                    novel_type: 'original',
                    novel_parent_id: null,
                    language_code: 'en'
                }
            })

            const result = await getNovelById(7)

            expect(result.novelDescription).toBeNull()
            expect(result.novelAuthor).toBeNull()
            expect(result.novelParentId).toBeNull()
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getNovelById(999)).rejects.toThrow()
        })
    })

    describe('getChaptersByNovel', () => {
        it('should call GET /chapters with novel-id, start, end query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChaptersByNovel(3, 10, 20)

            expect(client.get).toHaveBeenCalledWith('/chapters', {
                params: { 'novel-id': 3, start: 10, end: 20 }
            })
        })

        it('should map each chapter from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { chapter_id: 100, chapter_num: 1, novel_id: 5 },
                    { chapter_id: 101, chapter_num: 2, novel_id: 5 }
                ]
            })

            const result = await getChaptersByNovel(5)

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter[]>()
            expect(result).toEqual([
                { chapterId: 100, chapterNum: 1, novelId: 5 },
                { chapterId: 101, chapterNum: 2, novelId: 5 }
            ] satisfies NovelType.Chapter[])
        })

        it('should pass start and end as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChaptersByNovel(1)

            expect(client.get).toHaveBeenCalledWith('/chapters', {
                params: { 'novel-id': 1, start: undefined, end: undefined }
            })
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getChaptersByNovel(999)).rejects.toThrow()
        })
    })

    describe('getChapterById', () => {
        it('should call GET /chapters/{chapterId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { chapter_id: 50, chapter_num: 5, novel_id: 2 }
            })

            await getChapterById(50)

            expect(client.get).toHaveBeenCalledWith('/chapters/50')
        })

        it('should map chapter fields from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { chapter_id: 75, chapter_num: 10, novel_id: 3 }
            })

            const result = await getChapterById(75)

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter>()
            expect(result).toEqual({
                chapterId: 75,
                chapterNum: 10,
                novelId: 3
            } satisfies NovelType.Chapter)
        })

        it('should propagate 404 error when chapter not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Chapter not found' })
            )

            await expect(getChapterById(999)).rejects.toThrow()
        })
    })

    describe('getChapterRevisionById', () => {
        it('should call GET /revisions/{revisionId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_id: 200,
                    revision_title: 'Rev 1',
                    revision_is_primary: true,
                    revision_is_public: true,
                    revision_is_final: false,
                    chapter_id: 50,
                    revision_text: 'Full text here'
                }
            })

            await getChapterRevisionById(200)

            expect(client.get).toHaveBeenCalledWith('/revisions/200')
        })

        it('should map all revision fields including text field', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_id: 300,
                    revision_title: 'Final Draft',
                    revision_is_primary: false,
                    revision_is_public: false,
                    revision_is_final: true,
                    chapter_id: 60,
                    revision_text: 'Chapter content'
                }
            })

            const result = await getChapterRevisionById(300)

            expectTypeOf(result).toEqualTypeOf<NovelType.Revision>()
            expect(result).toEqual({
                revisionId: 300,
                revisionTitle: 'Final Draft',
                revisionIsPrimary: false,
                revisionIsPublic: false,
                revisionIsFinal: true,
                chapterId: 60,
                revisionText: 'Chapter content'
            } satisfies NovelType.Revision)
        })

        it('should return full Revision with text field', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_id: 400,
                    revision_title: 'Test',
                    revision_is_primary: true,
                    revision_is_public: true,
                    revision_is_final: true,
                    chapter_id: 70,
                    revision_text: 'Text content'
                }
            })

            const result = await getChapterRevisionById(400)

            expect(result).toHaveProperty('revisionText')
            expect(result.revisionText).toBe('Text content')
        })

        it('should propagate 404 error when revision not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Revision not found' })
            )

            await expect(getChapterRevisionById(999)).rejects.toThrow()
        })
    })

    describe('getChapterRevisionsByNovel', () => {
        it('should call GET /novels/{novelId}/revisions with all query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByNovel(5, 1, 10, true, false, true)

            expect(client.get).toHaveBeenCalledWith('/novels/5/revisions', {
                params: {
                    start: 1,
                    end: 10,
                    'is-public': true,
                    'is-primary': false,
                    'is-final': true
                }
            })
        })

        it('should map each item as RevisionMeta without text field', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        revision_id: 500,
                        revision_title: 'Meta 1',
                        revision_is_primary: true,
                        revision_is_public: true,
                        revision_is_final: false,
                        chapter_id: 80
                    }
                ]
            })

            const result = await getChapterRevisionsByNovel(5)

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionMeta[]>()
            expect(result).toEqual([
                {
                    revisionId: 500,
                    revisionTitle: 'Meta 1',
                    revisionIsPrimary: true,
                    revisionIsPublic: true,
                    revisionIsFinal: false,
                    chapterId: 80
                }
            ] satisfies NovelType.RevisionMeta[])
            expect(result[0]).not.toHaveProperty('revisionText')
        })

        it('should pass all optional params as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByNovel(10)

            expect(client.get).toHaveBeenCalledWith('/novels/10/revisions', {
                params: {
                    start: undefined,
                    end: undefined,
                    'is-public': undefined,
                    'is-primary': undefined,
                    'is-final': undefined
                }
            })
        })

        it('should serialize boolean query params correctly', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByNovel(3, undefined, undefined, false, true, false)

            expect(client.get).toHaveBeenCalledWith('/novels/3/revisions', {
                params: {
                    start: undefined,
                    end: undefined,
                    'is-public': false,
                    'is-primary': true,
                    'is-final': false
                }
            })
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getChapterRevisionsByNovel(999)).rejects.toThrow()
        })
    })

    describe('getChapterRevisionsByChapter', () => {
        it('should call GET /chapters/{chapterId}/revisions with query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByChapter(50, true, false)

            expect(client.get).toHaveBeenCalledWith('/chapters/50/revisions', {
                params: { 'is-public': true, 'is-primary': false }
            })
        })

        it('should map each item as RevisionMeta', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        revision_id: 600,
                        revision_title: 'Ch Rev',
                        revision_is_primary: false,
                        revision_is_public: false,
                        revision_is_final: true,
                        chapter_id: 90
                    }
                ]
            })

            const result = await getChapterRevisionsByChapter(90)

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionMeta[]>()
            expect(result).toEqual([
                {
                    revisionId: 600,
                    revisionTitle: 'Ch Rev',
                    revisionIsPrimary: false,
                    revisionIsPublic: false,
                    revisionIsFinal: true,
                    chapterId: 90
                }
            ] satisfies NovelType.RevisionMeta[])
        })

        it('should propagate 404 error when chapter not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Chapter not found' })
            )

            await expect(getChapterRevisionsByChapter(999)).rejects.toThrow()
        })
    })

    describe('createNovel', () => {
        it('should call POST /novels', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    novel_id: 1,
                    novel_title: 'New',
                    novel_description: null,
                    novel_author: null,
                    novel_visibility: 0,
                    novel_type: 'original',
                    novel_parent_id: null,
                    language_code: 'en'
                }
            })

            await createNovel({
                novelTitle: 'New',
                novelVisibility: 0,
                novelType: 'original',
                languageCode: 'en'
            })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/novels',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    novel_id: 2,
                    novel_title: 'My Novel',
                    novel_description: 'A great story',
                    novel_author: 'Me',
                    novel_visibility: 3,
                    novel_type: 'translation',
                    novel_parent_id: null,
                    language_code: 'zh'
                }
            })

            await createNovel({
                novelTitle: 'My Novel',
                novelDescription: 'A great story',
                novelAuthor: 'Me',
                novelVisibility: 3,
                novelType: 'translation',
                languageCode: 'zh'
            })

            expect(client.post).toHaveBeenCalledWith('/novels', {
                novel_title: 'My Novel',
                novel_description: 'A great story',
                novel_author: 'Me',
                novel_visibility: 3,
                novel_type: 'translation',
                language_code: 'zh'
            })
        })

        it('should map response novel from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    novel_id: 100,
                    novel_title: 'Created',
                    novel_description: 'Desc',
                    novel_author: 'Auth',
                    novel_visibility: 2,
                    novel_type: 'other',
                    novel_parent_id: 50,
                    language_code: 'jp'
                }
            })

            const result = await createNovel({
                novelTitle: 'Created',
                novelDescription: 'Desc',
                novelAuthor: 'Auth',
                novelVisibility: 2,
                novelType: 'other',
                languageCode: 'jp'
            })

            expectTypeOf(result).toEqualTypeOf<NovelType.Novel>()
            expect(result).toEqual({
                novelId: 100,
                novelTitle: 'Created',
                novelDescription: 'Desc',
                novelAuthor: 'Auth',
                novelVisibility: 2,
                novelType: 'other',
                novelParentId: 50,
                languageCode: 'jp'
            } satisfies NovelType.Novel)
        })

        it('should propagate 404 error when language not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Language not found' })
            )

            await expect(createNovel({
                novelTitle: 'Test',
                novelVisibility: 0,
                novelType: 'original',
                languageCode: 'invalid'
            })).rejects.toThrow()
        })

        it('should propagate 400 error when data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Data too long' })
            )

            await expect(createNovel({
                novelTitle: 'T'.repeat(10000),
                novelVisibility: 0,
                novelType: 'original',
                languageCode: 'en'
            })).rejects.toThrow()
        })
    })

    describe('createChapterForNovel', () => {
        it('should call POST /novels/{novelId}/chapters', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { chapter_id: 1, chapter_num: 1, novel_id: 5 }
            })

            await createChapterForNovel(5, { chapterNum: 1 })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/novels/5/chapters',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { chapter_id: 10, chapter_num: 5, novel_id: 3 }
            })

            await createChapterForNovel(3, { chapterNum: 5 })

            expect(client.post).toHaveBeenCalledWith('/novels/3/chapters', {
                chapter_num: 5
            })
        })

        it('should map chapter response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { chapter_id: 20, chapter_num: 10, novel_id: 7 }
            })

            const result = await createChapterForNovel(7, { chapterNum: 10 })

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter>()
            expect(result).toEqual({
                chapterId: 20,
                chapterNum: 10,
                novelId: 7
            } satisfies NovelType.Chapter)
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(createChapterForNovel(999, { chapterNum: 1 })).rejects.toThrow()
        })

        it('should propagate 409 error when duplicate chapter number', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'Duplicate chapter number' })
            )

            await expect(createChapterForNovel(5, { chapterNum: 1 })).rejects.toThrow()
        })
    })

    describe('createRevisionForChapter', () => {
        it('should call POST /chapters/{chapterId}/revisions', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    revision_id: 1,
                    revision_title: 'Rev 1',
                    revision_is_primary: false,
                    revision_is_public: false,
                    revision_is_final: false,
                    chapter_id: 10,
                    revision_text: 'Text'
                }
            })

            await createRevisionForChapter(10, {
                revisionTitle: 'Rev 1',
                revisionText: 'Text'
            })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/chapters/10/revisions',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    revision_id: 2,
                    revision_title: 'Draft',
                    revision_is_primary: false,
                    revision_is_public: false,
                    revision_is_final: false,
                    chapter_id: 15,
                    revision_text: 'Content here'
                }
            })

            await createRevisionForChapter(15, {
                revisionTitle: 'Draft',
                revisionText: 'Content here'
            })

            expect(client.post).toHaveBeenCalledWith('/chapters/15/revisions', {
                revision_title: 'Draft',
                revision_text: 'Content here'
            })
        })

        it('should map full revision response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    revision_id: 100,
                    revision_title: 'Final',
                    revision_is_primary: true,
                    revision_is_public: true,
                    revision_is_final: true,
                    chapter_id: 50,
                    revision_text: 'Final text'
                }
            })

            const result = await createRevisionForChapter(50, {
                revisionTitle: 'Final',
                revisionText: 'Final text'
            })

            expectTypeOf(result).toEqualTypeOf<NovelType.Revision>()
            expect(result).toEqual({
                revisionId: 100,
                revisionTitle: 'Final',
                revisionIsPrimary: true,
                revisionIsPublic: true,
                revisionIsFinal: true,
                chapterId: 50,
                revisionText: 'Final text'
            } satisfies NovelType.Revision)
        })

        it('should propagate 404 error when chapter not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Chapter not found' })
            )

            await expect(createRevisionForChapter(999, {
                revisionTitle: 'Test'
            })).rejects.toThrow()
        })

        it('should propagate 400 error when data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Data too long' })
            )

            await expect(createRevisionForChapter(10, {
                revisionTitle: 'T'.repeat(10000)
            })).rejects.toThrow()
        })
    })
})
