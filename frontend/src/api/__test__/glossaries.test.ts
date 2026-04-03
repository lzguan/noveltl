import { makeAxiosError } from './testUtils'
import { vi } from 'vitest'
import client from '../client'
import {
    getGlossariesByNovel,
    getGlossaryById,
    createGlossary,
    updateGlossary,
    deleteGlossary,
    getGlossaryEntriesByGlossary,
    getGlossaryEntryById,
    createGlossaryEntry,
    updateGlossaryEntry,
    deleteGlossaryEntry,
    getGlossaryContributors,
    addGlossaryContributor,
    updateGlossaryContributor,
    deleteGlossaryContributor,
    importGlossaryFromLabels,
    searchTermOccurrences,
    triggerTranslation,
    getTranslationJobs,
    getTranslationJob,
} from '../glossaries'
import {
    type Glossary,
    type GlossaryEntry,
    type GlossaryContributor,
    type ImportResult,
    type SearchTermResponse,
    type GlossaryTranslationJob,
} from '../../types/glossary'

vi.mock('../client')

describe('Glossary API', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    // --- Glossary CRUD ---

    describe('getGlossariesByNovel', () => {
        it('should call GET /glossaries with novel-id query param', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getGlossariesByNovel('uuid-novel-1')

            expect(client.get).toHaveBeenCalledWith('/glossaries', {
                params: { 'novel-id': 'uuid-novel-1' }
            })
        })

        it('should map each glossary from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        glossary_id: 'uuid-g-1',
                        glossary_name: 'Main Glossary',
                        glossary_description: 'A description',
                        novel_id: 'uuid-novel-1',
                        source_language_code: 'zh',
                        target_language_code: 'en',
                    },
                    {
                        glossary_id: 'uuid-g-2',
                        glossary_name: 'Secondary',
                        glossary_description: null,
                        novel_id: 'uuid-novel-1',
                        source_language_code: 'zh',
                        target_language_code: 'en',
                    },
                ]
            })

            const result = await getGlossariesByNovel('uuid-novel-1')

            expectTypeOf(result).toEqualTypeOf<Glossary[]>()
            expect(result).toEqual([
                {
                    glossaryId: 'uuid-g-1',
                    glossaryName: 'Main Glossary',
                    glossaryDescription: 'A description',
                    novelId: 'uuid-novel-1',
                    sourceLanguageCode: 'zh',
                    targetLanguageCode: 'en',
                },
                {
                    glossaryId: 'uuid-g-2',
                    glossaryName: 'Secondary',
                    glossaryDescription: null,
                    novelId: 'uuid-novel-1',
                    sourceLanguageCode: 'zh',
                    targetLanguageCode: 'en',
                },
            ] satisfies Glossary[])
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getGlossariesByNovel('uuid-novel-99')

            expect(result).toEqual([])
        })
    })

    describe('getGlossaryById', () => {
        it('should call GET /glossaries/{glossaryId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    glossary_name: 'Main Glossary',
                    glossary_description: null,
                    novel_id: 'uuid-novel-1',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            await getGlossaryById('uuid-g-1')

            expect(client.get).toHaveBeenCalledWith('/glossaries/uuid-g-1')
        })

        it('should map glossary from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-5',
                    glossary_name: 'Novel Terms',
                    glossary_description: 'Terms used in this novel',
                    novel_id: 'uuid-novel-3',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            const result = await getGlossaryById('uuid-g-5')

            expectTypeOf(result).toEqualTypeOf<Glossary>()
            expect(result).toEqual({
                glossaryId: 'uuid-g-5',
                glossaryName: 'Novel Terms',
                glossaryDescription: 'Terms used in this novel',
                novelId: 'uuid-novel-3',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            } satisfies Glossary)
        })

        it('should handle nullable glossary_description', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-6',
                    glossary_name: 'No Desc',
                    glossary_description: null,
                    novel_id: 'uuid-novel-4',
                    source_language_code: 'jp',
                    target_language_code: 'en',
                }
            })

            const result = await getGlossaryById('uuid-g-6')

            expect(result.glossaryDescription).toBeNull()
        })

        it('should propagate 404 error when glossary not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(getGlossaryById('uuid-g-999')).rejects.toThrow()
        })
    })

    describe('createGlossary', () => {
        it('should call POST /glossaries', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-new',
                    glossary_name: 'New Glossary',
                    glossary_description: null,
                    novel_id: 'uuid-novel-1',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            await createGlossary({
                glossaryName: 'New Glossary',
                novelId: 'uuid-novel-1',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            })

            expect(client.post).toHaveBeenCalledWith(
                '/glossaries',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-new',
                    glossary_name: 'My Glossary',
                    glossary_description: 'Some notes',
                    novel_id: 'uuid-novel-2',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            await createGlossary({
                glossaryName: 'My Glossary',
                glossaryDescription: 'Some notes',
                novelId: 'uuid-novel-2',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            })

            expect(client.post).toHaveBeenCalledWith('/glossaries', {
                glossary_name: 'My Glossary',
                glossary_description: 'Some notes',
                novel_id: 'uuid-novel-2',
                source_language_code: 'zh',
                target_language_code: 'en',
            })
        })

        it('should map response to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-10',
                    glossary_name: 'Created Glossary',
                    glossary_description: null,
                    novel_id: 'uuid-novel-5',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            const result = await createGlossary({
                glossaryName: 'Created Glossary',
                novelId: 'uuid-novel-5',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            })

            expectTypeOf(result).toEqualTypeOf<Glossary>()
            expect(result).toEqual({
                glossaryId: 'uuid-g-10',
                glossaryName: 'Created Glossary',
                glossaryDescription: null,
                novelId: 'uuid-novel-5',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            } satisfies Glossary)
        })

        it('should propagate 404 when novel not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Novel not found' })
            )

            await expect(createGlossary({
                glossaryName: 'G',
                novelId: 'uuid-novel-999',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            })).rejects.toThrow()
        })

        it('should propagate 400 when data too long', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'A field value is too long' })
            )

            await expect(createGlossary({
                glossaryName: 'G'.repeat(10000),
                novelId: 'uuid-novel-1',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            })).rejects.toThrow()
        })
    })

    describe('updateGlossary', () => {
        it('should call PATCH /glossaries/{glossaryId}', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    glossary_name: 'Updated Name',
                    glossary_description: null,
                    novel_id: 'uuid-novel-1',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            await updateGlossary('uuid-g-1', { glossaryName: 'Updated Name' })

            expect(client.patch).toHaveBeenCalledWith(
                '/glossaries/uuid-g-1',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    glossary_name: 'Renamed',
                    glossary_description: 'New desc',
                    novel_id: 'uuid-novel-1',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            await updateGlossary('uuid-g-1', {
                glossaryName: 'Renamed',
                glossaryDescription: 'New desc',
            })

            expect(client.patch).toHaveBeenCalledWith('/glossaries/uuid-g-1', {
                glossary_name: 'Renamed',
                glossary_description: 'New desc',
            })
        })

        it('should map response to camelCase', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-3',
                    glossary_name: 'Patched',
                    glossary_description: null,
                    novel_id: 'uuid-novel-7',
                    source_language_code: 'zh',
                    target_language_code: 'en',
                }
            })

            const result = await updateGlossary('uuid-g-3', { glossaryName: 'Patched' })

            expectTypeOf(result).toEqualTypeOf<Glossary>()
            expect(result).toEqual({
                glossaryId: 'uuid-g-3',
                glossaryName: 'Patched',
                glossaryDescription: null,
                novelId: 'uuid-novel-7',
                sourceLanguageCode: 'zh',
                targetLanguageCode: 'en',
            } satisfies Glossary)
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.patch).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(updateGlossary('uuid-g-999', { glossaryName: 'X' })).rejects.toThrow()
        })
    })

    describe('deleteGlossary', () => {
        it('should call DELETE /glossaries/{glossaryId}', async () => {
            vi.mocked(client.delete).mockResolvedValue({ data: null })

            await deleteGlossary('uuid-g-1')

            expect(client.delete).toHaveBeenCalledWith('/glossaries/uuid-g-1')
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(deleteGlossary('uuid-g-999')).rejects.toThrow()
        })
    })

    // --- Glossary Entry CRUD ---

    describe('getGlossaryEntriesByGlossary', () => {
        it('should call GET /glossary-entries with glossary-id query param', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getGlossaryEntriesByGlossary('uuid-g-1')

            expect(client.get).toHaveBeenCalledWith('/glossary-entries', {
                params: { 'glossary-id': 'uuid-g-1' }
            })
        })

        it('should map each entry from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        glossary_entry_id: 'uuid-ge-1',
                        glossary_id: 'uuid-g-1',
                        source_term: '龙',
                        translated_term: 'Dragon',
                        context_notes: 'A mythical creature',
                        entity_type: 'MISC',
                    },
                    {
                        glossary_entry_id: 'uuid-ge-2',
                        glossary_id: 'uuid-g-1',
                        source_term: '李明',
                        translated_term: null,
                        context_notes: null,
                        entity_type: 'PER',
                    },
                ]
            })

            const result = await getGlossaryEntriesByGlossary('uuid-g-1')

            expectTypeOf(result).toEqualTypeOf<GlossaryEntry[]>()
            expect(result).toEqual([
                {
                    glossaryEntryId: 'uuid-ge-1',
                    glossaryId: 'uuid-g-1',
                    sourceTerm: '龙',
                    translatedTerm: 'Dragon',
                    contextNotes: 'A mythical creature',
                    entityType: 'MISC',
                },
                {
                    glossaryEntryId: 'uuid-ge-2',
                    glossaryId: 'uuid-g-1',
                    sourceTerm: '李明',
                    translatedTerm: null,
                    contextNotes: null,
                    entityType: 'PER',
                },
            ] satisfies GlossaryEntry[])
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getGlossaryEntriesByGlossary('uuid-g-99')

            expect(result).toEqual([])
        })
    })

    describe('getGlossaryEntryById', () => {
        it('should call GET /glossary-entries/{glossaryEntryId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-5',
                    glossary_id: 'uuid-g-1',
                    source_term: '天',
                    translated_term: 'Sky',
                    context_notes: null,
                    entity_type: 'MISC',
                }
            })

            await getGlossaryEntryById('uuid-ge-5')

            expect(client.get).toHaveBeenCalledWith('/glossary-entries/uuid-ge-5')
        })

        it('should map entry from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-7',
                    glossary_id: 'uuid-g-2',
                    source_term: '山',
                    translated_term: 'Mountain',
                    context_notes: 'Used as a surname',
                    entity_type: 'LOC',
                }
            })

            const result = await getGlossaryEntryById('uuid-ge-7')

            expectTypeOf(result).toEqualTypeOf<GlossaryEntry>()
            expect(result).toEqual({
                glossaryEntryId: 'uuid-ge-7',
                glossaryId: 'uuid-g-2',
                sourceTerm: '山',
                translatedTerm: 'Mountain',
                contextNotes: 'Used as a surname',
                entityType: 'LOC',
            } satisfies GlossaryEntry)
        })

        it('should propagate 404 when entry not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary entry not found' })
            )

            await expect(getGlossaryEntryById('uuid-ge-999')).rejects.toThrow()
        })
    })

    describe('createGlossaryEntry', () => {
        it('should call POST /glossary-entries', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-new',
                    glossary_id: 'uuid-g-1',
                    source_term: '水',
                    translated_term: 'Water',
                    context_notes: null,
                    entity_type: 'MISC',
                }
            })

            await createGlossaryEntry({
                glossaryId: 'uuid-g-1',
                sourceTerm: '水',
                translatedTerm: 'Water',
            })

            expect(client.post).toHaveBeenCalledWith(
                '/glossary-entries',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-new',
                    glossary_id: 'uuid-g-1',
                    source_term: '火',
                    translated_term: 'Fire',
                    context_notes: 'Elemental term',
                    entity_type: 'MISC',
                }
            })

            await createGlossaryEntry({
                glossaryId: 'uuid-g-1',
                sourceTerm: '火',
                translatedTerm: 'Fire',
                contextNotes: 'Elemental term',
                entityType: 'MISC',
            })

            expect(client.post).toHaveBeenCalledWith('/glossary-entries', {
                glossary_id: 'uuid-g-1',
                source_term: '火',
                translated_term: 'Fire',
                context_notes: 'Elemental term',
                entity_type: 'MISC',
            })
        })

        it('should map response to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-20',
                    glossary_id: 'uuid-g-5',
                    source_term: '风',
                    translated_term: null,
                    context_notes: null,
                    entity_type: 'MISC',
                }
            })

            const result = await createGlossaryEntry({
                glossaryId: 'uuid-g-5',
                sourceTerm: '风',
            })

            expectTypeOf(result).toEqualTypeOf<GlossaryEntry>()
            expect(result).toEqual({
                glossaryEntryId: 'uuid-ge-20',
                glossaryId: 'uuid-g-5',
                sourceTerm: '风',
                translatedTerm: null,
                contextNotes: null,
                entityType: 'MISC',
            } satisfies GlossaryEntry)
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(createGlossaryEntry({
                glossaryId: 'uuid-g-999',
                sourceTerm: '土',
            })).rejects.toThrow()
        })

        it('should propagate 409 when duplicate entry', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'An entry with this source term and entity type already exists' })
            )

            await expect(createGlossaryEntry({
                glossaryId: 'uuid-g-1',
                sourceTerm: '水',
                entityType: 'MISC',
            })).rejects.toThrow()
        })
    })

    describe('updateGlossaryEntry', () => {
        it('should call PATCH /glossary-entries/{glossaryEntryId}', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-1',
                    glossary_id: 'uuid-g-1',
                    source_term: '龙',
                    translated_term: 'Long Dragon',
                    context_notes: null,
                    entity_type: 'MISC',
                }
            })

            await updateGlossaryEntry('uuid-ge-1', { translatedTerm: 'Long Dragon' })

            expect(client.patch).toHaveBeenCalledWith(
                '/glossary-entries/uuid-ge-1',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-1',
                    glossary_id: 'uuid-g-1',
                    source_term: '龙',
                    translated_term: 'Dragon Lord',
                    context_notes: 'A powerful creature',
                    entity_type: 'MISC',
                }
            })

            await updateGlossaryEntry('uuid-ge-1', {
                translatedTerm: 'Dragon Lord',
                contextNotes: 'A powerful creature',
                entityType: 'MISC',
            })

            expect(client.patch).toHaveBeenCalledWith('/glossary-entries/uuid-ge-1', {
                translated_term: 'Dragon Lord',
                context_notes: 'A powerful creature',
                entity_type: 'MISC',
            })
        })

        it('should map response to camelCase', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_entry_id: 'uuid-ge-3',
                    glossary_id: 'uuid-g-2',
                    source_term: '剑',
                    translated_term: 'Sword',
                    context_notes: 'A weapon',
                    entity_type: 'MISC',
                }
            })

            const result = await updateGlossaryEntry('uuid-ge-3', { translatedTerm: 'Sword' })

            expectTypeOf(result).toEqualTypeOf<GlossaryEntry>()
            expect(result).toEqual({
                glossaryEntryId: 'uuid-ge-3',
                glossaryId: 'uuid-g-2',
                sourceTerm: '剑',
                translatedTerm: 'Sword',
                contextNotes: 'A weapon',
                entityType: 'MISC',
            } satisfies GlossaryEntry)
        })

        it('should propagate 404 when entry not found', async () => {
            vi.mocked(client.patch).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary entry not found' })
            )

            await expect(updateGlossaryEntry('uuid-ge-999', { translatedTerm: 'X' })).rejects.toThrow()
        })
    })

    describe('deleteGlossaryEntry', () => {
        it('should call DELETE /glossary-entries/{glossaryEntryId}', async () => {
            vi.mocked(client.delete).mockResolvedValue({ data: null })

            await deleteGlossaryEntry('uuid-ge-1')

            expect(client.delete).toHaveBeenCalledWith('/glossary-entries/uuid-ge-1')
        })

        it('should propagate 404 when entry not found', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary entry not found' })
            )

            await expect(deleteGlossaryEntry('uuid-ge-999')).rejects.toThrow()
        })
    })

    // --- Glossary Contributors ---

    describe('getGlossaryContributors', () => {
        it('should call GET /glossaries/{glossaryId}/contributors', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getGlossaryContributors('uuid-g-1')

            expect(client.get).toHaveBeenCalledWith('/glossaries/uuid-g-1/contributors')
        })

        it('should map each contributor from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        glossary_id: 'uuid-g-1',
                        user_id: 'uuid-u-1',
                        glossary_contributor_role: 'owner',
                    },
                    {
                        glossary_id: 'uuid-g-1',
                        user_id: 'uuid-u-2',
                        glossary_contributor_role: 'editor',
                    },
                ]
            })

            const result = await getGlossaryContributors('uuid-g-1')

            expectTypeOf(result).toEqualTypeOf<GlossaryContributor[]>()
            expect(result).toEqual([
                {
                    glossaryId: 'uuid-g-1',
                    userId: 'uuid-u-1',
                    glossaryContributorRole: 'owner',
                },
                {
                    glossaryId: 'uuid-g-1',
                    userId: 'uuid-u-2',
                    glossaryContributorRole: 'editor',
                },
            ] satisfies GlossaryContributor[])
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(getGlossaryContributors('uuid-g-999')).rejects.toThrow()
        })
    })

    describe('addGlossaryContributor', () => {
        it('should call POST /glossaries/{glossaryId}/contributors', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    user_id: 'uuid-u-3',
                    glossary_contributor_role: 'viewer',
                }
            })

            await addGlossaryContributor('uuid-g-1', {
                userId: 'uuid-u-3',
                glossaryContributorRole: 'viewer',
            })

            expect(client.post).toHaveBeenCalledWith(
                '/glossaries/uuid-g-1/contributors',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    user_id: 'uuid-u-4',
                    glossary_contributor_role: 'editor',
                }
            })

            await addGlossaryContributor('uuid-g-1', {
                userId: 'uuid-u-4',
                glossaryContributorRole: 'editor',
            })

            expect(client.post).toHaveBeenCalledWith('/glossaries/uuid-g-1/contributors', {
                user_id: 'uuid-u-4',
                glossary_contributor_role: 'editor',
            })
        })

        it('should map response to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-2',
                    user_id: 'uuid-u-5',
                    glossary_contributor_role: 'viewer',
                }
            })

            const result = await addGlossaryContributor('uuid-g-2', {
                userId: 'uuid-u-5',
                glossaryContributorRole: 'viewer',
            })

            expectTypeOf(result).toEqualTypeOf<GlossaryContributor>()
            expect(result).toEqual({
                glossaryId: 'uuid-g-2',
                userId: 'uuid-u-5',
                glossaryContributorRole: 'viewer',
            } satisfies GlossaryContributor)
        })

        it('should propagate 409 when contributor already exists', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(409, { detail: 'User is already a contributor' })
            )

            await expect(addGlossaryContributor('uuid-g-1', {
                userId: 'uuid-u-1',
                glossaryContributorRole: 'viewer',
            })).rejects.toThrow()
        })
    })

    describe('updateGlossaryContributor', () => {
        it('should call PATCH /glossaries/{glossaryId}/contributors/{userId}', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    user_id: 'uuid-u-2',
                    glossary_contributor_role: 'editor',
                }
            })

            await updateGlossaryContributor('uuid-g-1', 'uuid-u-2', {
                glossaryContributorRole: 'editor',
            })

            expect(client.patch).toHaveBeenCalledWith(
                '/glossaries/uuid-g-1/contributors/uuid-u-2',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-1',
                    user_id: 'uuid-u-2',
                    glossary_contributor_role: 'owner',
                }
            })

            await updateGlossaryContributor('uuid-g-1', 'uuid-u-2', {
                glossaryContributorRole: 'owner',
            })

            expect(client.patch).toHaveBeenCalledWith('/glossaries/uuid-g-1/contributors/uuid-u-2', {
                glossary_contributor_role: 'owner',
            })
        })

        it('should map response to camelCase', async () => {
            vi.mocked(client.patch).mockResolvedValue({
                data: {
                    glossary_id: 'uuid-g-3',
                    user_id: 'uuid-u-6',
                    glossary_contributor_role: 'editor',
                }
            })

            const result = await updateGlossaryContributor('uuid-g-3', 'uuid-u-6', {
                glossaryContributorRole: 'editor',
            })

            expectTypeOf(result).toEqualTypeOf<GlossaryContributor>()
            expect(result).toEqual({
                glossaryId: 'uuid-g-3',
                userId: 'uuid-u-6',
                glossaryContributorRole: 'editor',
            } satisfies GlossaryContributor)
        })

        it('should propagate 404 when contributor not found', async () => {
            vi.mocked(client.patch).mockRejectedValue(
                makeAxiosError(404, { detail: 'Contributor not found' })
            )

            await expect(updateGlossaryContributor('uuid-g-1', 'uuid-u-999', {
                glossaryContributorRole: 'editor',
            })).rejects.toThrow()
        })
    })

    describe('deleteGlossaryContributor', () => {
        it('should call DELETE /glossaries/{glossaryId}/contributors/{userId}', async () => {
            vi.mocked(client.delete).mockResolvedValue({ data: null })

            await deleteGlossaryContributor('uuid-g-1', 'uuid-u-2')

            expect(client.delete).toHaveBeenCalledWith('/glossaries/uuid-g-1/contributors/uuid-u-2')
        })

        it('should propagate 404 when contributor not found', async () => {
            vi.mocked(client.delete).mockRejectedValue(
                makeAxiosError(404, { detail: 'Contributor not found' })
            )

            await expect(deleteGlossaryContributor('uuid-g-1', 'uuid-u-999')).rejects.toThrow()
        })
    })

    // --- Import from Labels ---

    describe('importGlossaryFromLabels', () => {
        it('should call POST /glossaries/{glossaryId}/import-from-labels', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    entries_created: 5,
                    entries_updated: 0,
                    entries_skipped: 2,
                }
            })

            await importGlossaryFromLabels('uuid-g-1', {
                labelGroupId: 'uuid-lg-1',
                overwriteExisting: false,
            })

            expect(client.post).toHaveBeenCalledWith(
                '/glossaries/uuid-g-1/import-from-labels',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    entries_created: 3,
                    entries_updated: 2,
                    entries_skipped: 0,
                }
            })

            await importGlossaryFromLabels('uuid-g-1', {
                labelGroupId: 'uuid-lg-2',
                entityTypes: ['PER', 'LOC'],
                overwriteExisting: true,
            })

            expect(client.post).toHaveBeenCalledWith('/glossaries/uuid-g-1/import-from-labels', {
                label_group_id: 'uuid-lg-2',
                entity_types: ['PER', 'LOC'],
                overwrite_existing: true,
            })
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    entries_created: 10,
                    entries_updated: 3,
                    entries_skipped: 1,
                }
            })

            const result = await importGlossaryFromLabels('uuid-g-1', {
                labelGroupId: 'uuid-lg-1',
                overwriteExisting: false,
            })

            expectTypeOf(result).toEqualTypeOf<ImportResult>()
            expect(result).toEqual({
                entriesCreated: 10,
                entriesUpdated: 3,
                entriesSkipped: 1,
            } satisfies ImportResult)
        })

        it('should pass null entity_types when not provided', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    entries_created: 0,
                    entries_updated: 0,
                    entries_skipped: 0,
                }
            })

            await importGlossaryFromLabels('uuid-g-1', {
                labelGroupId: 'uuid-lg-3',
                overwriteExisting: false,
            })

            expect(client.post).toHaveBeenCalledWith('/glossaries/uuid-g-1/import-from-labels', {
                label_group_id: 'uuid-lg-3',
                entity_types: undefined,
                overwrite_existing: false,
            })
        })

        it('should propagate 404 when glossary or label group not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(importGlossaryFromLabels('uuid-g-999', {
                labelGroupId: 'uuid-lg-1',
                overwriteExisting: false,
            })).rejects.toThrow()
        })
    })

    // --- Term Search ---

    describe('searchTermOccurrences', () => {
        it('should call POST /glossary-entries/{glossaryEntryId}/search-occurrences', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { occurrences: [], total_count: 0 }
            })

            await searchTermOccurrences('uuid-ge-1', { mode: 'string' })

            expect(client.post).toHaveBeenCalledWith(
                '/glossary-entries/uuid-ge-1/search-occurrences',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body for string mode', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { occurrences: [], total_count: 0 }
            })

            await searchTermOccurrences('uuid-ge-1', { mode: 'string' })

            expect(client.post).toHaveBeenCalledWith(
                '/glossary-entries/uuid-ge-1/search-occurrences',
                { mode: 'string', label_group_id: null }
            )
        })

        it('should map camelCase request to snake_case body for label mode with labelGroupId', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { occurrences: [], total_count: 0 }
            })

            await searchTermOccurrences('uuid-ge-2', {
                mode: 'label',
                labelGroupId: 'uuid-lg-1',
            })

            expect(client.post).toHaveBeenCalledWith(
                '/glossary-entries/uuid-ge-2/search-occurrences',
                { mode: 'label', label_group_id: 'uuid-lg-1' }
            )
        })

        it('should map snake_case response to camelCase with occurrences', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    occurrences: [
                        {
                            chapter_id: 'uuid-ch-1',
                            chapter_num: 1,
                            revision_text_id: 'uuid-rt-1',
                            positions: [
                                { start: 5, end: 7 },
                                { start: 20, end: 22 },
                            ],
                        },
                    ],
                    total_count: 2,
                }
            })

            const result = await searchTermOccurrences('uuid-ge-1', { mode: 'string' })

            expectTypeOf(result).toEqualTypeOf<SearchTermResponse>()
            expect(result).toEqual({
                occurrences: [
                    {
                        chapterId: 'uuid-ch-1',
                        chapterNum: 1,
                        revisionTextId: 'uuid-rt-1',
                        positions: [
                            { start: 5, end: 7 },
                            { start: 20, end: 22 },
                        ],
                    },
                ],
                totalCount: 2,
            } satisfies SearchTermResponse)
        })

        it('should return empty occurrences when no matches found', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: { occurrences: [], total_count: 0 }
            })

            const result = await searchTermOccurrences('uuid-ge-1', { mode: 'string' })

            expectTypeOf(result).toEqualTypeOf<SearchTermResponse>()
            expect(result).toEqual({
                occurrences: [],
                totalCount: 0,
            } satisfies SearchTermResponse)
        })

        it('should propagate 404 when glossary entry not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary entry not found' })
            )

            await expect(
                searchTermOccurrences('uuid-ge-999', { mode: 'string' })
            ).rejects.toThrow()
        })

        it('should propagate 400 when label mode is missing label_group_id', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(400, { detail: 'label_group_id is required for label mode.' })
            )

            await expect(
                searchTermOccurrences('uuid-ge-1', { mode: 'label' })
            ).rejects.toThrow()
        })
    })

    // --- Translation Jobs ---

    describe('triggerTranslation', () => {
        const mockJobResponse = {
            job_id: 'uuid-job-1',
            glossary_id: 'uuid-g-1',
            status: 'pending',
            job_model_name: null,
            job_last_job_id: null,
            job_message: null,
            entries_translated: 0,
            entries_total: 3,
            created_at: '2026-04-01T00:00:00Z',
            updated_at: '2026-04-01T00:00:00Z',
        }

        it('should call POST /glossaries/{glossaryId}/translate', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: mockJobResponse })

            await triggerTranslation('uuid-g-1', {})

            expect(client.post).toHaveBeenCalledWith(
                '/glossaries/uuid-g-1/translate',
                expect.any(Object)
            )
        })

        it('should map camelCase request to snake_case body (modelName → model_name)', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: mockJobResponse })

            await triggerTranslation('uuid-g-1', { modelName: 'openai' })

            expect(client.post).toHaveBeenCalledWith('/glossaries/uuid-g-1/translate', {
                model_name: 'openai',
            })
        })

        it('should send model_name as null when modelName is not provided', async () => {
            vi.mocked(client.post).mockResolvedValue({ data: mockJobResponse })

            await triggerTranslation('uuid-g-1', {})

            expect(client.post).toHaveBeenCalledWith('/glossaries/uuid-g-1/translate', {
                model_name: null,
            })
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.post).mockResolvedValue({
                data: {
                    job_id: 'uuid-job-2',
                    glossary_id: 'uuid-g-1',
                    status: 'pending',
                    job_model_name: 'openai',
                    job_last_job_id: 'uuid-job-2',
                    job_message: null,
                    entries_translated: 0,
                    entries_total: 5,
                    created_at: '2026-04-01T12:00:00Z',
                    updated_at: '2026-04-01T12:00:00Z',
                }
            })

            const result = await triggerTranslation('uuid-g-1', { modelName: 'openai' })

            expectTypeOf(result).toEqualTypeOf<GlossaryTranslationJob>()
            expect(result).toEqual({
                jobId: 'uuid-job-2',
                glossaryId: 'uuid-g-1',
                status: 'pending',
                jobModelName: 'openai',
                jobLastJobId: 'uuid-job-2',
                jobMessage: null,
                entriesTranslated: 0,
                entriesTotal: 5,
                createdAt: '2026-04-01T12:00:00Z',
                updatedAt: '2026-04-01T12:00:00Z',
            } satisfies GlossaryTranslationJob)
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.post).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(triggerTranslation('uuid-g-999', {})).rejects.toThrow()
        })
    })

    describe('getTranslationJobs', () => {
        it('should call GET /glossaries/{glossaryId}/translation-jobs', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            await getTranslationJobs('uuid-g-1')

            expect(client.get).toHaveBeenCalledWith('/glossaries/uuid-g-1/translation-jobs')
        })

        it('should map array of jobs from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    {
                        job_id: 'uuid-job-10',
                        glossary_id: 'uuid-g-1',
                        status: 'done',
                        job_model_name: null,
                        job_last_job_id: null,
                        job_message: null,
                        entries_translated: 10,
                        entries_total: 10,
                        created_at: '2026-04-01T10:00:00Z',
                        updated_at: '2026-04-01T11:00:00Z',
                    },
                    {
                        job_id: 'uuid-job-11',
                        glossary_id: 'uuid-g-1',
                        status: 'failed',
                        job_model_name: 'openai',
                        job_last_job_id: 'uuid-job-11',
                        job_message: 'Translation failed: timeout',
                        entries_translated: 3,
                        entries_total: 10,
                        created_at: '2026-04-02T10:00:00Z',
                        updated_at: '2026-04-02T10:05:00Z',
                    },
                ]
            })

            const result = await getTranslationJobs('uuid-g-1')

            expectTypeOf(result).toEqualTypeOf<GlossaryTranslationJob[]>()
            expect(result).toEqual([
                {
                    jobId: 'uuid-job-10',
                    glossaryId: 'uuid-g-1',
                    status: 'done',
                    jobModelName: null,
                    jobLastJobId: null,
                    jobMessage: null,
                    entriesTranslated: 10,
                    entriesTotal: 10,
                    createdAt: '2026-04-01T10:00:00Z',
                    updatedAt: '2026-04-01T11:00:00Z',
                },
                {
                    jobId: 'uuid-job-11',
                    glossaryId: 'uuid-g-1',
                    status: 'failed',
                    jobModelName: 'openai',
                    jobLastJobId: 'uuid-job-11',
                    jobMessage: 'Translation failed: timeout',
                    entriesTranslated: 3,
                    entriesTotal: 10,
                    createdAt: '2026-04-02T10:00:00Z',
                    updatedAt: '2026-04-02T10:05:00Z',
                },
            ] satisfies GlossaryTranslationJob[])
        })

        it('should return empty array when backend returns empty array', async () => {
            vi.mocked(client.get).mockResolvedValue({ data: [] })

            const result = await getTranslationJobs('uuid-g-1')

            expect(result).toEqual([])
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(getTranslationJobs('uuid-g-999')).rejects.toThrow()
        })
    })

    describe('getTranslationJob', () => {
        it('should call GET /glossaries/{glossaryId}/translation-jobs/{jobId}', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    job_id: 'uuid-job-5',
                    glossary_id: 'uuid-g-1',
                    status: 'processing',
                    job_model_name: null,
                    job_last_job_id: null,
                    job_message: null,
                    entries_translated: 2,
                    entries_total: 8,
                    created_at: '2026-04-01T09:00:00Z',
                    updated_at: '2026-04-01T09:01:00Z',
                }
            })

            await getTranslationJob('uuid-g-1', 'uuid-job-5')

            expect(client.get).toHaveBeenCalledWith('/glossaries/uuid-g-1/translation-jobs/uuid-job-5')
        })

        it('should map response from snake_case to camelCase', async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: {
                    job_id: 'uuid-job-6',
                    glossary_id: 'uuid-g-2',
                    status: 'done',
                    job_model_name: 'openai',
                    job_last_job_id: null,
                    job_message: null,
                    entries_translated: 7,
                    entries_total: 7,
                    created_at: '2026-04-01T08:00:00Z',
                    updated_at: '2026-04-01T08:10:00Z',
                }
            })

            const result = await getTranslationJob('uuid-g-2', 'uuid-job-6')

            expectTypeOf(result).toEqualTypeOf<GlossaryTranslationJob>()
            expect(result).toEqual({
                jobId: 'uuid-job-6',
                glossaryId: 'uuid-g-2',
                status: 'done',
                jobModelName: 'openai',
                jobLastJobId: null,
                jobMessage: null,
                entriesTranslated: 7,
                entriesTotal: 7,
                createdAt: '2026-04-01T08:00:00Z',
                updatedAt: '2026-04-01T08:10:00Z',
            } satisfies GlossaryTranslationJob)
        })

        it('should propagate 404 when job not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Translation job not found' })
            )

            await expect(getTranslationJob('uuid-g-1', 'uuid-job-999')).rejects.toThrow()
        })

        it('should propagate 404 when glossary not found', async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Glossary not found' })
            )

            await expect(getTranslationJob('uuid-g-999', 'uuid-job-1')).rejects.toThrow()
        })
    })
})
