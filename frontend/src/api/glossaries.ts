import client from './client'
import * as GlossaryType from '../types/glossary'

// --- Response mappers (API snake_case → frontend camelCase) ---

/* eslint-disable @typescript-eslint/no-explicit-any */

const mapGlossary = (data: any): GlossaryType.Glossary => ({
    glossaryId: data.glossary_id,
    glossaryName: data.glossary_name,
    glossaryDescription: data.glossary_description,
    novelId: data.novel_id,
    sourceLanguageCode: data.source_language_code,
    targetLanguageCode: data.target_language_code,
})

const mapGlossaryEntry = (data: any): GlossaryType.GlossaryEntry => ({
    glossaryEntryId: data.glossary_entry_id,
    glossaryId: data.glossary_id,
    sourceTerm: data.source_term,
    translatedTerm: data.translated_term,
    contextNotes: data.context_notes,
    entityType: data.entity_type,
})

const mapGlossaryContributor = (data: any): GlossaryType.GlossaryContributor => ({
    glossaryId: data.glossary_id,
    userId: data.user_id,
    glossaryContributorRole: data.glossary_contributor_role,
})

const mapImportResult = (data: any): GlossaryType.ImportResult => ({
    entriesCreated: data.entries_created,
    entriesUpdated: data.entries_updated,
    entriesSkipped: data.entries_skipped,
})

const mapTermPosition = (data: any): GlossaryType.TermPosition => ({
    start: data.start,
    end: data.end,
})

const mapTermOccurrence = (data: any): GlossaryType.TermOccurrence => ({
    chapterId: data.chapter_id,
    chapterNum: data.chapter_num,
    revisionTextId: data.revision_text_id,
    positions: (data.positions || []).map(mapTermPosition),
})

const mapSearchTermResponse = (data: any): GlossaryType.SearchTermResponse => ({
    occurrences: (data.occurrences || []).map(mapTermOccurrence),
    totalCount: data.total_count,
})

/* eslint-enable @typescript-eslint/no-explicit-any */

// --- Request mappers (frontend camelCase → API snake_case) ---

const mapCreateGlossaryRequest = (data: GlossaryType.CreateGlossary) => ({
    glossary_name: data.glossaryName,
    glossary_description: data.glossaryDescription,
    novel_id: data.novelId,
    source_language_code: data.sourceLanguageCode,
    target_language_code: data.targetLanguageCode,
})

const mapUpdateGlossaryRequest = (data: GlossaryType.UpdateGlossary) => ({
    glossary_name: data.glossaryName,
    glossary_description: data.glossaryDescription,
})

const mapCreateGlossaryEntryRequest = (data: GlossaryType.CreateGlossaryEntry) => ({
    glossary_id: data.glossaryId,
    source_term: data.sourceTerm,
    translated_term: data.translatedTerm,
    context_notes: data.contextNotes,
    entity_type: data.entityType,
})

const mapUpdateGlossaryEntryRequest = (data: GlossaryType.UpdateGlossaryEntry) => ({
    translated_term: data.translatedTerm,
    context_notes: data.contextNotes,
    entity_type: data.entityType,
})

const mapAddGlossaryContributorRequest = (data: GlossaryType.AddGlossaryContributor) => ({
    user_id: data.userId,
    glossary_contributor_role: data.glossaryContributorRole,
})

const mapUpdateGlossaryContributorRequest = (data: GlossaryType.UpdateGlossaryContributor) => ({
    glossary_contributor_role: data.glossaryContributorRole,
})

const mapImportFromLabelsRequest = (data: GlossaryType.ImportFromLabels) => ({
    label_group_id: data.labelGroupId,
    entity_types: data.entityTypes,
    overwrite_existing: data.overwriteExisting,
})

// --- API functions ---

// Glossaries

export const getGlossariesByNovel = async (novelId: string): Promise<GlossaryType.Glossary[]> => {
    const result = await client.get('/glossaries', {
        params: { 'novel-id': novelId }
    })
    return result.data.map(mapGlossary)
}

export const getGlossaryById = async (glossaryId: string): Promise<GlossaryType.Glossary> => {
    const result = await client.get(`/glossaries/${glossaryId}`)
    return mapGlossary(result.data)
}

export const createGlossary = async (request: GlossaryType.CreateGlossary): Promise<GlossaryType.Glossary> => {
    const result = await client.post('/glossaries', mapCreateGlossaryRequest(request))
    return mapGlossary(result.data)
}

export const updateGlossary = async (glossaryId: string, request: GlossaryType.UpdateGlossary): Promise<GlossaryType.Glossary> => {
    const result = await client.patch(`/glossaries/${glossaryId}`, mapUpdateGlossaryRequest(request))
    return mapGlossary(result.data)
}

export const deleteGlossary = async (glossaryId: string): Promise<void> => {
    await client.delete(`/glossaries/${glossaryId}`)
}

// Glossary Entries

export const getGlossaryEntriesByGlossary = async (glossaryId: string): Promise<GlossaryType.GlossaryEntry[]> => {
    const result = await client.get('/glossary-entries', {
        params: { 'glossary-id': glossaryId }
    })
    return result.data.map(mapGlossaryEntry)
}

export const getGlossaryEntryById = async (glossaryEntryId: string): Promise<GlossaryType.GlossaryEntry> => {
    const result = await client.get(`/glossary-entries/${glossaryEntryId}`)
    return mapGlossaryEntry(result.data)
}

export const createGlossaryEntry = async (request: GlossaryType.CreateGlossaryEntry): Promise<GlossaryType.GlossaryEntry> => {
    const result = await client.post('/glossary-entries', mapCreateGlossaryEntryRequest(request))
    return mapGlossaryEntry(result.data)
}

export const updateGlossaryEntry = async (glossaryEntryId: string, request: GlossaryType.UpdateGlossaryEntry): Promise<GlossaryType.GlossaryEntry> => {
    const result = await client.patch(`/glossary-entries/${glossaryEntryId}`, mapUpdateGlossaryEntryRequest(request))
    return mapGlossaryEntry(result.data)
}

export const deleteGlossaryEntry = async (glossaryEntryId: string): Promise<void> => {
    await client.delete(`/glossary-entries/${glossaryEntryId}`)
}

// Glossary Contributors

export const getGlossaryContributors = async (glossaryId: string): Promise<GlossaryType.GlossaryContributor[]> => {
    const result = await client.get(`/glossaries/${glossaryId}/contributors`)
    return result.data.map(mapGlossaryContributor)
}

export const addGlossaryContributor = async (
    glossaryId: string,
    request: GlossaryType.AddGlossaryContributor
): Promise<GlossaryType.GlossaryContributor> => {
    const result = await client.post(`/glossaries/${glossaryId}/contributors`, mapAddGlossaryContributorRequest(request))
    return mapGlossaryContributor(result.data)
}

export const updateGlossaryContributor = async (
    glossaryId: string,
    userId: string,
    request: GlossaryType.UpdateGlossaryContributor
): Promise<GlossaryType.GlossaryContributor> => {
    const result = await client.patch(`/glossaries/${glossaryId}/contributors/${userId}`, mapUpdateGlossaryContributorRequest(request))
    return mapGlossaryContributor(result.data)
}

export const deleteGlossaryContributor = async (glossaryId: string, userId: string): Promise<void> => {
    await client.delete(`/glossaries/${glossaryId}/contributors/${userId}`)
}

// Term Search

export const searchTermOccurrences = async (
    glossaryEntryId: string,
    request: GlossaryType.SearchTermRequest,
): Promise<GlossaryType.SearchTermResponse> => {
    const response = await client.post(
        `/glossary-entries/${glossaryEntryId}/search-occurrences`,
        {
            mode: request.mode,
            label_group_id: request.labelGroupId ?? null,
        },
    )
    return mapSearchTermResponse(response.data)
}

// Import

export const importGlossaryFromLabels = async (
    glossaryId: string,
    request: GlossaryType.ImportFromLabels
): Promise<GlossaryType.ImportResult> => {
    const result = await client.post(`/glossaries/${glossaryId}/import-from-labels`, mapImportFromLabelsRequest(request))
    return mapImportResult(result.data)
}
