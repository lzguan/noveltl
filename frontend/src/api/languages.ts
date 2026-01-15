import client from './client'
import { type Language } from '../types/language'

export const get_languages = async () : Promise<Language[]> => {
    const result = await client.get('/languages')
    return result.data
}

export const get_language_by_code = async (language_code : string) : Promise<Language> => {
    const result = await client.get(`/languages/${language_code}`)
    return result.data
}