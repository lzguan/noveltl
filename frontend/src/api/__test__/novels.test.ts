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
    createRevisionForChapter,
    getRevisionText,
    getRevisionTextById,
    getRevisionTextVersions,
    updateRevisionText,
    deleteRevision,
    getNovelAssociations,
    createNovelAssociation,
    deleteNovelAssociation,
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
                        novel_id: 'uuid-novel-1',
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
                    novelId: 'uuid-novel-1',
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
                        novel_id: 'uuid-novel-2',
                        novel_title: 'My Novel',
                        novel_description: null,
                        novel_author: null,
                        novel_visibility: 0,
                        novel_type: 'translation',
                        novel_parent_id: 'uuid-novel-1',
                        language_code: 'zh'
                    }
                ]
            })

            const result = await getNovelsMine(false)

            expect(result).toEqual([
                {
                    novelId: 'uuid-novel-2',
                    novelTitle: 'My Novel',
                    novelDescription: null,
                    novelAuthor: null,
                    novelVisibility: 0,
                    novelType: 'translation',
                    novelParentId: 'uuid-novel-1',
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
                    novel_id: 'uuid-novel-5',
                    novel_title: 'Test',
                    novel_description: null,
                    novel_author: null,
                    novel_visibility: 2,
                    novel_type: 'original',
                    novel_parent_id: null,
                    language_code: 'en'
                }
            })

            await getNovelById('uuid-novel-5')

            expect(client.get).toHaveBeenCalledWith('/novels/uuid-novel-5')
        })

        it('should map all novel fields from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    novel_id: 'uuid-novel-10',
                    novel_title: 'Full Novel',
                    novel_description: 'Description here',
                    novel_author: 'John Doe',
                    novel_visibility: 3,
                    novel_type: 'other',
                    novel_parent_id: 'uuid-novel-8',
                    language_code: 'jp'
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
                novelParentId: 'uuid-novel-8',
                languageCode: 'jp'
            } satisfies NovelType.Novel)
        })

        it('should handle nullable fields correctly when null', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    novel_id: 'uuid-novel-7',
                    novel_title: 'Minimal',
                    novel_description: null,
                    novel_author: null,
                    novel_visibility: 1,
                    novel_type: 'original',
                    novel_parent_id: null,
                    language_code: 'en'
                }
            })

            const result = await getNovelById('uuid-novel-7')

            expect(result.novelDescription).toBeNull()
            expect(result.novelAuthor).toBeNull()
            expect(result.novelParentId).toBeNull()
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getNovelById('uuid-novel-999')).rejects.toThrow()
        })
    })

    describe('getChaptersByNovel', () => {
        it('should call GET /chapters with novel-id, start, end query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChaptersByNovel('uuid-novel-3', 10, 20)

            expect(client.get).toHaveBeenCalledWith('/chapters', {
                params: { 'novel-id': 'uuid-novel-3', start: 10, end: 20 }
            })
        })

        it('should map each chapter from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { chapter_id: 'uuid-ch-100', chapter_num: 1, novel_id: 'uuid-novel-5' },
                    { chapter_id: 'uuid-ch-101', chapter_num: 2, novel_id: 'uuid-novel-5' }
                ]
            })

            const result = await getChaptersByNovel('uuid-novel-5')

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter[]>()
            expect(result).toEqual([
                { chapterId: 'uuid-ch-100', chapterNum: 1, novelId: 'uuid-novel-5' },
                { chapterId: 'uuid-ch-101', chapterNum: 2, novelId: 'uuid-novel-5' }
            ] satisfies NovelType.Chapter[])
        })

        it('should pass start and end as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChaptersByNovel('uuid-novel-1')

            expect(client.get).toHaveBeenCalledWith('/chapters', {
                params: { 'novel-id': 'uuid-novel-1', start: undefined, end: undefined }
            })
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getChaptersByNovel('uuid-novel-999')).rejects.toThrow()
        })
    })

    describe('getChapterById', () => {
        it('should call GET /chapters/{chapterId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { chapter_id: 'uuid-ch-50', chapter_num: 5, novel_id: 'uuid-novel-2' }
            })

            await getChapterById('uuid-ch-50')

            expect(client.get).toHaveBeenCalledWith('/chapters/uuid-ch-50')
        })

        it('should map chapter fields from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { chapter_id: 'uuid-ch-75', chapter_num: 10, novel_id: 'uuid-novel-3' }
            })

            const result = await getChapterById('uuid-ch-75')

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter>()
            expect(result).toEqual({
                chapterId: 'uuid-ch-75',
                chapterNum: 10,
                novelId: 'uuid-novel-3'
            } satisfies NovelType.Chapter)
        })

        it('should propagate 404 error when chapter not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Chapter not found' })
            )

            await expect(getChapterById('uuid-ch-999')).rejects.toThrow()
        })
    })

    describe('getChapterRevisionById', () => {
        it('should call GET /revisions/{revisionId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_id: 'uuid-rev-200',
                    revision_title: 'Rev 1',
                    revision_is_primary: true,
                    revision_is_public: true,
                    chapter_id: 'uuid-ch-50'
                }
            })

            await getChapterRevisionById('uuid-rev-200')

            expect(client.get).toHaveBeenCalledWith('/revisions/uuid-rev-200')
        })

        it('should map revision fields from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_id: 'uuid-rev-300',
                    revision_title: 'Final Draft',
                    revision_is_primary: false,
                    revision_is_public: false,
                    chapter_id: 'uuid-ch-60'
                }
            })

            const result = await getChapterRevisionById('uuid-rev-300')

            expectTypeOf(result).toEqualTypeOf<NovelType.Revision>()
            expect(result).toEqual({
                revisionId: 'uuid-rev-300',
                revisionTitle: 'Final Draft',
                revisionIsPrimary: false,
                revisionIsPublic: false,
                chapterId: 'uuid-ch-60'
            } satisfies NovelType.Revision)
        })

        it('should propagate 404 error when revision not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Revision not found' })
            )

            await expect(getChapterRevisionById('uuid-rev-999')).rejects.toThrow()
        })
    })

    describe('getChapterRevisionsByNovel', () => {
        it('should call GET /novels/{novelId}/revisions with all query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByNovel('uuid-novel-5', 1, 10, true, false)

            expect(client.get).toHaveBeenCalledWith('/novels/uuid-novel-5/revisions', {
                params: {
                    start: 1,
                    end: 10,
                    'is-public': true,
                    'is-primary': false
                }
            })
        })

        it('should map each item as RevisionMeta', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        revision_id: 'uuid-rev-500',
                        revision_title: 'Meta 1',
                        revision_is_primary: true,
                        revision_is_public: true,
                        chapter_id: 'uuid-ch-80'
                    }
                ]
            })

            const result = await getChapterRevisionsByNovel('uuid-novel-5')

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionMeta[]>()
            expect(result).toEqual([
                {
                    revisionId: 'uuid-rev-500',
                    revisionTitle: 'Meta 1',
                    revisionIsPrimary: true,
                    revisionIsPublic: true,
                    chapterId: 'uuid-ch-80'
                }
            ] satisfies NovelType.RevisionMeta[])
        })

        it('should pass all optional params as undefined when omitted', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByNovel('uuid-novel-10')

            expect(client.get).toHaveBeenCalledWith('/novels/uuid-novel-10/revisions', {
                params: {
                    start: undefined,
                    end: undefined,
                    'is-public': undefined,
                    'is-primary': undefined
                }
            })
        })

        it('should serialize boolean query params correctly', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByNovel('uuid-novel-3', undefined, undefined, false, true)

            expect(client.get).toHaveBeenCalledWith('/novels/uuid-novel-3/revisions', {
                params: {
                    start: undefined,
                    end: undefined,
                    'is-public': false,
                    'is-primary': true
                }
            })
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getChapterRevisionsByNovel('uuid-novel-999')).rejects.toThrow()
        })
    })

    describe('getChapterRevisionsByChapter', () => {
        it('should call GET /chapters/{chapterId}/revisions with query params', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getChapterRevisionsByChapter('uuid-ch-50', true, false)

            expect(client.get).toHaveBeenCalledWith('/chapters/uuid-ch-50/revisions', {
                params: { 'is-public': true, 'is-primary': false }
            })
        })

        it('should map each item as RevisionMeta', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        revision_id: 'uuid-rev-600',
                        revision_title: 'Ch Rev',
                        revision_is_primary: false,
                        revision_is_public: false,
                        chapter_id: 'uuid-ch-90'
                    }
                ]
            })

            const result = await getChapterRevisionsByChapter('uuid-ch-90')

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionMeta[]>()
            expect(result).toEqual([
                {
                    revisionId: 'uuid-rev-600',
                    revisionTitle: 'Ch Rev',
                    revisionIsPrimary: false,
                    revisionIsPublic: false,
                    chapterId: 'uuid-ch-90'
                }
            ] satisfies NovelType.RevisionMeta[])
        })

        it('should propagate 404 error when chapter not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Chapter not found' })
            )

            await expect(getChapterRevisionsByChapter('uuid-ch-999')).rejects.toThrow()
        })
    })

    describe('createNovel', () => {
        it('should call POST /novels', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    novel_id: 'uuid-novel-1',
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
                    novel_id: 'uuid-novel-2',
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
                    novel_id: 'uuid-novel-100',
                    novel_title: 'Created',
                    novel_description: 'Desc',
                    novel_author: 'Auth',
                    novel_visibility: 2,
                    novel_type: 'other',
                    novel_parent_id: 'uuid-novel-50',
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
                novelId: 'uuid-novel-100',
                novelTitle: 'Created',
                novelDescription: 'Desc',
                novelAuthor: 'Auth',
                novelVisibility: 2,
                novelType: 'other',
                novelParentId: 'uuid-novel-50',
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
                data: { chapter_id: 'uuid-ch-1', chapter_num: 1, novel_id: 'uuid-novel-5' }
            })

            await createChapterForNovel('uuid-novel-5', { chapterNum: 1 })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/novels/uuid-novel-5/chapters',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { chapter_id: 'uuid-ch-10', chapter_num: 5, novel_id: 'uuid-novel-3' }
            })

            await createChapterForNovel('uuid-novel-3', { chapterNum: 5 })

            expect(client.post).toHaveBeenCalledWith('/novels/uuid-novel-3/chapters', {
                chapter_num: 5
            })
        })

        it('should map chapter response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { chapter_id: 'uuid-ch-20', chapter_num: 10, novel_id: 'uuid-novel-7' }
            })

            const result = await createChapterForNovel('uuid-novel-7', { chapterNum: 10 })

            expectTypeOf(result).toEqualTypeOf<NovelType.Chapter>()
            expect(result).toEqual({
                chapterId: 'uuid-ch-20',
                chapterNum: 10,
                novelId: 'uuid-novel-7'
            } satisfies NovelType.Chapter)
        })

        it('should propagate 404 error when novel not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(createChapterForNovel('uuid-novel-999', { chapterNum: 1 })).rejects.toThrow()
        })

        it('should propagate 409 error when duplicate chapter number', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'Duplicate chapter number' })
            )

            await expect(createChapterForNovel('uuid-novel-5', { chapterNum: 1 })).rejects.toThrow()
        })
    })

    describe('createRevisionForChapter', () => {
        it('should call POST /chapters/{chapterId}/revisions', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    metadata: {
                        revision_id: 'uuid-rev-1',
                        revision_title: 'Rev 1',
                        revision_is_primary: false,
                        revision_is_public: false,
                        chapter_id: 'uuid-ch-10'
                    },
                    content: {
                        revision_text_id: 'uuid-rt-1',
                        revision_text_content: '',
                        revision_text_version: 1
                    }
                }
            })

            await createRevisionForChapter('uuid-ch-10', {
                revisionTitle: 'Rev 1'
            })

            expect(client.post).toHaveBeenCalled()
            expect(client.post).toHaveBeenCalledWith(
                '/chapters/uuid-ch-10/revisions',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    metadata: {
                        revision_id: 'uuid-rev-2',
                        revision_title: 'Draft',
                        revision_is_primary: false,
                        revision_is_public: false,
                        chapter_id: 'uuid-ch-15'
                    },
                    content: {
                        revision_text_id: 'uuid-rt-2',
                        revision_text_content: '',
                        revision_text_version: 1
                    }
                }
            })

            await createRevisionForChapter('uuid-ch-15', {
                revisionTitle: 'Draft'
            })

            expect(client.post).toHaveBeenCalledWith('/chapters/uuid-ch-15/revisions', {
                revision_title: 'Draft'
            })
        })

        it('should map RevisionData response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    metadata: {
                        revision_id: 'uuid-rev-100',
                        revision_title: 'Final',
                        revision_is_primary: false,
                        revision_is_public: false,
                        chapter_id: 'uuid-ch-50'
                    },
                    content: {
                        revision_text_id: 'uuid-rt-100',
                        revision_text_content: '',
                        revision_text_version: 1
                    }
                }
            })

            const result = await createRevisionForChapter('uuid-ch-50', {
                revisionTitle: 'Final'
            })

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionData>()
            expect(result).toEqual({
                metadata: {
                    revisionId: 'uuid-rev-100',
                    revisionTitle: 'Final',
                    revisionIsPrimary: false,
                    revisionIsPublic: false,
                    chapterId: 'uuid-ch-50'
                },
                content: {
                    revisionTextId: 'uuid-rt-100',
                    revisionTextContent: '',
                    revisionTextVersion: 1
                }
            } satisfies NovelType.RevisionData)
        })

        it('should propagate 404 error when chapter not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Chapter not found' })
            )

            await expect(createRevisionForChapter('uuid-ch-999', {
                revisionTitle: 'Test'
            })).rejects.toThrow()
        })

        it('should propagate 400 error when data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'Data too long' })
            )

            await expect(createRevisionForChapter('uuid-ch-10', {
                revisionTitle: 'T'.repeat(10000)
            })).rejects.toThrow()
        })
    })

    describe('getRevisionText', () => {
        it('should call GET /revisions/{revisionId}/text', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_text_id: 'uuid-rt-1',
                    revision_text_content: 'Chapter text here',
                    revision_text_version: 3
                }
            })

            await getRevisionText('uuid-rev-1')

            expect(client.get).toHaveBeenCalledWith('/revisions/uuid-rev-1/text')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_text_id: 'uuid-rt-5',
                    revision_text_content: 'Full text content',
                    revision_text_version: 2
                }
            })

            const result = await getRevisionText('uuid-rev-5')

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionText>()
            expect(result).toEqual({
                revisionTextId: 'uuid-rt-5',
                revisionTextContent: 'Full text content',
                revisionTextVersion: 2
            } satisfies NovelType.RevisionText)
        })
    })

    describe('getRevisionTextById', () => {
        it('should call GET /revision-texts/{revisionTextId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_text_id: 'uuid-rt-10',
                    revision_text_content: 'Specific version',
                    revision_text_version: 1
                }
            })

            await getRevisionTextById('uuid-rt-10')

            expect(client.get).toHaveBeenCalledWith('/revision-texts/uuid-rt-10')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    revision_text_id: 'uuid-rt-10',
                    revision_text_content: 'Specific version',
                    revision_text_version: 1
                }
            })

            const result = await getRevisionTextById('uuid-rt-10')

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionText>()
            expect(result).toEqual({
                revisionTextId: 'uuid-rt-10',
                revisionTextContent: 'Specific version',
                revisionTextVersion: 1
            } satisfies NovelType.RevisionText)
        })
    })

    describe('getRevisionTextVersions', () => {
        it('should call GET /revisions/{revisionId}/text-versions', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getRevisionTextVersions('uuid-rev-1')

            expect(client.get).toHaveBeenCalledWith('/revisions/uuid-rev-1/text-versions')
        })

        it('should map response array from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { revision_text_id: 'uuid-rt-1', revision_text_version: 1 },
                    { revision_text_id: 'uuid-rt-2', revision_text_version: 2 }
                ]
            })

            const result = await getRevisionTextVersions('uuid-rev-1')

            expectTypeOf(result).toEqualTypeOf<NovelType.RevisionTextMeta[]>()
            expect(result).toEqual([
                { revisionTextId: 'uuid-rt-1', revisionTextVersion: 1 },
                { revisionTextId: 'uuid-rt-2', revisionTextVersion: 2 }
            ] satisfies NovelType.RevisionTextMeta[])
        })
    })

    describe('updateRevisionText', () => {
        it('should call PATCH /revisions/{revisionId}/text with mapped body', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: { status: 'success', detail: null }
            })

            await updateRevisionText('uuid-rev-1', {
                textOps: [{ op: 'insert', start: 0, text: 'Hello' }],
                revisionTextId: 'uuid-rt-1'
            })

            expect(client.patch).toHaveBeenCalledWith('/revisions/uuid-rev-1/text', {
                text_ops: [{ op: 'insert', start: 0, text: 'Hello' }],
                revision_text_id: 'uuid-rt-1'
            })
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: { status: 'success', detail: null }
            })

            const result = await updateRevisionText('uuid-rev-1', {
                textOps: [{ op: 'delete', start: 5, text: 'world' }],
                revisionTextId: 'uuid-rt-1'
            })

            expectTypeOf(result).toEqualTypeOf<NovelType.OperationStatus>()
            expect(result).toEqual({
                status: 'success',
                detail: null
            } satisfies NovelType.OperationStatus)
        })
    })

    describe('deleteRevision', () => {
        it('should call DELETE /revisions/{revisionId}', async () => {
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'success', detail: null }
            })

            await deleteRevision('uuid-rev-1')

            expect(client.delete).toHaveBeenCalledWith('/revisions/uuid-rev-1')
        })

        it('should map response to OperationStatus', async () => {
            vi.mocked(client.delete).mockResolvedValue({
                data: { status: 'success', detail: 'Deleted' }
            })

            const result = await deleteRevision('uuid-rev-1')

            expectTypeOf(result).toEqualTypeOf<NovelType.OperationStatus>()
            expect(result).toEqual({
                status: 'success',
                detail: 'Deleted'
            } satisfies NovelType.OperationStatus)
        })
    })

    // --- Novel Associations ---

    describe('getNovelAssociations', () => {
        it('should call GET /novel-associations with source-novel-id query param', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getNovelAssociations('uuid-novel-1')

            expect(client.get).toHaveBeenCalledWith('/novel-associations', {
                params: { 'source-novel-id': 'uuid-novel-1' }
            })
        })

        it('should map each association from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        association_id: 'uuid-assoc-1',
                        source_novel_id: 'uuid-novel-1',
                        target_novel_id: 'uuid-novel-2',
                        association_type: 'translation',
                    },
                ]
            })

            const result = await getNovelAssociations('uuid-novel-1')

            expectTypeOf(result).toEqualTypeOf<NovelType.NovelAssociation[]>()
            expect(result).toEqual([
                {
                    associationId: 'uuid-assoc-1',
                    sourceNovelId: 'uuid-novel-1',
                    targetNovelId: 'uuid-novel-2',
                    associationType: 'translation',
                },
            ] satisfies NovelType.NovelAssociation[])
        })

        it('should return empty array when novel has no associations', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getNovelAssociations('uuid-novel-1')

            expect(result).toEqual([])
        })

        it('should propagate 404 when novel not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(getNovelAssociations('uuid-novel-999')).rejects.toThrow()
        })
    })

    describe('createNovelAssociation', () => {
        it('should call POST /novel-associations', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    association_id: 'uuid-assoc-1',
                    source_novel_id: 'uuid-novel-1',
                    target_novel_id: 'uuid-novel-2',
                    association_type: 'translation',
                }
            })

            await createNovelAssociation({
                sourceNovelId: 'uuid-novel-1',
                targetNovelId: 'uuid-novel-2',
                associationType: 'translation',
            })

            expect(client.post).toHaveBeenCalledWith(
                '/novel-associations',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    association_id: 'uuid-assoc-2',
                    source_novel_id: 'uuid-novel-3',
                    target_novel_id: 'uuid-novel-4',
                    association_type: 'translation',
                }
            })

            await createNovelAssociation({
                sourceNovelId: 'uuid-novel-3',
                targetNovelId: 'uuid-novel-4',
                associationType: 'translation',
            })

            expect(client.post).toHaveBeenCalledWith('/novel-associations', {
                source_novel_id: 'uuid-novel-3',
                target_novel_id: 'uuid-novel-4',
                association_type: 'translation',
            })
        })

        it('should map snake_case response to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    association_id: 'uuid-assoc-10',
                    source_novel_id: 'uuid-novel-5',
                    target_novel_id: 'uuid-novel-6',
                    association_type: 'translation',
                }
            })

            const result = await createNovelAssociation({
                sourceNovelId: 'uuid-novel-5',
                targetNovelId: 'uuid-novel-6',
                associationType: 'translation',
            })

            expectTypeOf(result).toEqualTypeOf<NovelType.NovelAssociation>()
            expect(result).toEqual({
                associationId: 'uuid-assoc-10',
                sourceNovelId: 'uuid-novel-5',
                targetNovelId: 'uuid-novel-6',
                associationType: 'translation',
            } satisfies NovelType.NovelAssociation)
        })

        it('should propagate 409 when duplicate association exists', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'An association of this type between these novels already exists.' })
            )

            await expect(createNovelAssociation({
                sourceNovelId: 'uuid-novel-1',
                targetNovelId: 'uuid-novel-2',
                associationType: 'translation',
            })).rejects.toThrow()
        })

        it('should propagate 401 when user lacks permission', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(401, { detail: 'Insufficient permissions to perform this action.' })
            )

            await expect(createNovelAssociation({
                sourceNovelId: 'uuid-novel-1',
                targetNovelId: 'uuid-novel-2',
                associationType: 'translation',
            })).rejects.toThrow()
        })
    })

    describe('deleteNovelAssociation', () => {
        it('should call DELETE /novel-associations/{associationId}', async () => {
            vi.mocked(client.delete).mockResolvedValue({ data: null })

            await deleteNovelAssociation('uuid-assoc-1')

            expect(client.delete).toHaveBeenCalledWith('/novel-associations/uuid-assoc-1')
        })

        it('should propagate 404 when association not found', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel association not found.' })
            )

            await expect(deleteNovelAssociation('uuid-assoc-999')).rejects.toThrow()
        })
    })
})
