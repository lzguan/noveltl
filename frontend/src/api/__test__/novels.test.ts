import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getSourceWorks,
    getSourceWorkById,
    getNovelsBySourceWork,
    createSourceWork,
    updateSourceWork,
    getNovels,
    getNovelsMine,
    getNovelById,
    createNovel,
    updateNovel,
    getChaptersByNovel,
    getChapterById,
    createChapterForNovel,
    updateChapter,
    deleteChapter,
    publishChapter,
    getChapterContent,
    getChapterContentById,
    getChapterContentVersions,
    getChapterContentStatus,
    updateChapterContent
} from '../novels'
import * as NovelType from '../../types/novel'

vi.mock('../client')

describe('Novels API', () => {
    afterEach(() => {
        vi.clearAllMocks()
    })

    describe('source works', () => {
        it('should call GET /source-works with title-contains and ret-novels', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getSourceWorks('xianxia', true)

            expect(client.get).toHaveBeenCalledWith('/source-works', {
                params: { 'title-contains': 'xianxia', 'ret-novels': true }
            })
        })

        it('should map SourceWorkData responses', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [{
                    source_work: {
                        source_work_id: 'uuid-sw-1',
                        source_work_title: 'Source Work',
                        source_work_description: 'desc'
                    },
                    novels: [{
                        novel_id: 'uuid-novel-1',
                        novel_title: 'Nested Novel',
                        novel_description: null,
                        novel_author: 'Jane Doe',
                        novel_visibility: 3,
                        novel_type: 'original',
                        language_code: 'zh',
                        source_work_id: 'uuid-sw-1'
                    }]
                }]
            })

            const result = await getSourceWorks('xianxia', true)

            expectTypeOf(result).toEqualTypeOf<NovelType.SourceWorkData[]>()
            expect(result).toEqual([{
                sourceWork: {
                    sourceWorkId: 'uuid-sw-1',
                    sourceWorkTitle: 'Source Work',
                    sourceWorkDescription: 'desc'
                },
                novels: [{
                    novelId: 'uuid-novel-1',
                    novelTitle: 'Nested Novel',
                    novelDescription: null,
                    novelAuthor: 'Jane Doe',
                    novelVisibility: 3,
                    novelType: 'original',
                    languageCode: 'zh',
                    sourceWorkId: 'uuid-sw-1'
                }]
            }] satisfies NovelType.SourceWorkData[])
        })

        it('should map SourceWork responses', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    source_work_id: 'uuid-sw-1',
                    source_work_title: 'Source Work',
                    source_work_description: 'desc'
                }
            })

            const result = await getSourceWorkById('uuid-sw-1')

            expectTypeOf(result).toEqualTypeOf<NovelType.SourceWork>()
            expect(result).toEqual({
                sourceWorkId: 'uuid-sw-1',
                sourceWorkTitle: 'Source Work',
                sourceWorkDescription: 'desc'
            } satisfies NovelType.SourceWork)
        })

        it('should call POST/PATCH source-work endpoints with snake_case', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    source_work_id: 'uuid-sw-2',
                    source_work_title: 'Created',
                    source_work_description: null
                }
            })
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    source_work_id: 'uuid-sw-2',
                    source_work_title: 'Updated',
                    source_work_description: 'new desc'
                }
            })

            await createSourceWork({ sourceWorkTitle: 'Created' })
            await updateSourceWork('uuid-sw-2', { sourceWorkTitle: 'Updated', sourceWorkDescription: 'new desc' })

            expect(client.post).toHaveBeenCalledWith('/source-works', {
                source_work_title: 'Created',
                source_work_description: undefined
            })
            expect(client.patch).toHaveBeenCalledWith('/source-works/uuid-sw-2', {
                source_work_title: 'Updated',
                source_work_description: 'new desc'
            })
        })

        it('should read novels by source work', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [{
                    novel_id: 'uuid-novel-1',
                    novel_title: 'Novel',
                    novel_description: null,
                    novel_author: null,
                    novel_visibility: 3,
                    novel_type: 'original',
                    language_code: 'zh',
                    source_work_id: 'uuid-sw-1'
                }]
            })

            const result = await getNovelsBySourceWork('uuid-sw-1')

            expect(client.get).toHaveBeenCalledWith('/source-works/uuid-sw-1/novels')
            expect(result[0]?.novelId).toBe('uuid-novel-1')
            expect(result[0]?.sourceWorkId).toBe('uuid-sw-1')
        })
    })

    describe('novels', () => {
        it('should map novel responses without novelParentId', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    novel_id: 'uuid-novel-10',
                    novel_title: 'Full Novel',
                    novel_description: 'Description here',
                    novel_author: 'John Doe',
                    novel_visibility: 3,
                    novel_type: 'other',
                    language_code: 'jp',
                    source_work_id: 'uuid-sw-10'
                }
            })

            const result = await getNovelById('uuid-novel-10')

            expectTypeOf(result).toEqualTypeOf<NovelType.Novel>()
            expect(result).toEqual({
                novelId: 'uuid-novel-10',
                novelTitle: 'Full Novel',
                novelDescription: 'Description here',
                novelAuthor: 'John Doe',
                novelVisibility: 3,
                novelType: 'other',
                languageCode: 'jp',
                sourceWorkId: 'uuid-sw-10'
            } satisfies NovelType.Novel)
        })

        it('should call list endpoints with expected params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getNovels('test')
            await getNovelsMine(true, 'mine')

            expect(client.get).toHaveBeenNthCalledWith(1, '/novels', {
                params: { 'title-contains': 'test' }
            })
            expect(client.get).toHaveBeenNthCalledWith(2, '/novels/mine', {
                params: { editable: true, 'title-contains': 'mine' }
            })
        })

        it('should map create/update novel requests to snake_case', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: {} })
            vi.mocked(client.patch).mockResolvedValue({ data: {} })

            await createNovel({
                novelTitle: 'Created',
                novelVisibility: 3,
                novelType: 'translation',
                languageCode: 'en',
                sourceWorkId: 'uuid-sw-9'
            })

            await updateNovel('uuid-novel-3', {
                novelTitle: 'Updated',
                novelAuthor: 'A'
            })

            expect(client.post).toHaveBeenCalledWith('/novels', {
                novel_title: 'Created',
                novel_description: undefined,
                novel_author: undefined,
                novel_visibility: 3,
                novel_type: 'translation',
                language_code: 'en',
                source_work_id: 'uuid-sw-9'
            })

            expect(client.patch).toHaveBeenCalledWith('/novels/uuid-novel-3', {
                novel_title: 'Updated',
                novel_description: undefined,
                novel_author: 'A',
                novel_visibility: undefined,
                novel_type: undefined
            })
        })

        it('should propagate backend errors', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getNovelById('uuid-novel-404')).rejects.toThrow()
        })
    })

    describe('chapters', () => {
        it('should map chapter fields from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    chapter_id: 'uuid-ch-75',
                    chapter_num: 10,
                    chapter_title: 'Arrival',
                    chapter_is_public: true,
                    novel_id: 'uuid-novel-3'
                }
            })

            const result = await getChapterById('uuid-ch-75')

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter>()
            expect(result).toEqual({
                chapterId: 'uuid-ch-75',
                chapterNum: 10,
                chapterTitle: 'Arrival',
                chapterIsPublic: true,
                novelId: 'uuid-novel-3'
            } satisfies NovelType.Chapter)
        })

        it('should request chapters by novel with range params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChaptersByNovel('uuid-novel-3', 10, 20)

            expect(client.get).toHaveBeenCalledWith('/chapters', {
                params: { 'novel-id': 'uuid-novel-3', start: 10, end: 20 }
            })
        })

        it('should return ChapterData when creating a chapter', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    metadata: {
                        chapter_id: 'uuid-ch-1',
                        chapter_num: 1,
                        chapter_title: '',
                        chapter_is_public: false,
                        novel_id: 'uuid-novel-1'
                    },
                    content: {
                        chapter_content_text: '',
                        chapter_content_version: 1,
                        chapter_content_id: 'uuid-cc-1'
                    }
                }
            })

            const result = await createChapterForNovel('uuid-novel-1', { chapterNum: 1 })

            expectTypeOf(result).toEqualTypeOf<NovelType.ChapterData>()
            expect(client.post).toHaveBeenCalledWith('/novels/uuid-novel-1/chapters', {
                chapter_num: 1,
                chapter_title: undefined,
                chapter_is_public: undefined
            })
            expect(result.content.chapterContentId).toBe('uuid-cc-1')
        })

        it('should update, publish, and delete chapters against the new endpoints', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    chapter_id: 'uuid-ch-9',
                    chapter_num: 9,
                    chapter_title: 'Updated',
                    chapter_is_public: true,
                    novel_id: 'uuid-novel-3'
                }
            })
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    chapter_id: 'uuid-ch-9',
                    chapter_num: 9,
                    chapter_title: 'Updated',
                    chapter_is_public: true,
                    novel_id: 'uuid-novel-3'
                }
            })
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'success', detail: null }
            })

            await updateChapter('uuid-ch-9', { chapterTitle: 'Updated' })
            await publishChapter('uuid-ch-9')
            const result = await deleteChapter('uuid-ch-9')

            expect(client.patch).toHaveBeenCalledWith('/chapters/uuid-ch-9', {
                chapter_title: 'Updated'
            })
            expect(client.post).toHaveBeenCalledWith('/chapters/uuid-ch-9/publish')
            expect(result).toEqual({ status: 'success', detail: null } satisfies NovelType.OperationStatus)
        })
    })

    describe('chapter content', () => {
        it('should map chapter content payloads', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    chapter_content_text: 'Full text content',
                    chapter_content_version: 2,
                    chapter_content_id: 'uuid-cc-5'
                }
            })

            const byChapter = await getChapterContent('uuid-ch-5')
            const byId = await getChapterContentById('uuid-cc-5')

            expect(client.get).toHaveBeenNthCalledWith(1, '/chapters/uuid-ch-5/content')
            expect(client.get).toHaveBeenNthCalledWith(2, '/chapter-contents/uuid-cc-5')
            expectTypeOf(byChapter).toEqualTypeOf<NovelType.ChapterContent>()
            expect(byId.chapterContentId).toBe('uuid-cc-5')
        })

        it('should map content version metadata', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { chapter_content_id: 'uuid-cc-1', chapter_content_version: 1 },
                    { chapter_content_id: 'uuid-cc-2', chapter_content_version: 2 }
                ]
            })

            const result = await getChapterContentVersions('uuid-ch-1')

            expect(client.get).toHaveBeenCalledWith('/chapters/uuid-ch-1/content-versions')
            expect(result).toEqual([
                { chapterContentId: 'uuid-cc-1', chapterContentVersion: 1 },
                { chapterContentId: 'uuid-cc-2', chapterContentVersion: 2 }
            ] satisfies NovelType.ChapterContentMeta[])
        })

        it('should read content status and update content with chapter_content_id', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { status: 'success', detail: null }
            })
            vi.mocked(client.patch).mockResolvedValue({
                data: { status: 'success', detail: null }
            })

            await getChapterContentStatus('uuid-ch-1', 'uuid-cc-2')
            const result = await updateChapterContent('uuid-ch-1', {
                textOps: [{ op: 'insert', start: 0, text: 'Hello' }],
                chapterContentId: 'uuid-cc-2'
            })

            expect(client.get).toHaveBeenCalledWith('/chapters/uuid-ch-1/content-status/uuid-cc-2')
            expect(client.patch).toHaveBeenCalledWith('/chapters/uuid-ch-1/content', {
                text_ops: [{ op: 'insert', start: 0, text: 'Hello' }],
                chapter_content_id: 'uuid-cc-2'
            })
            expect(result.status).toBe('success')
        })
    })
})
