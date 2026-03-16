import { makeAxiosError } from './testUtils'
import { getLanguageByCode, getLanguages } from "../languages";
import { type Language } from "../../types/language";
import client from "../client";
import { vi } from "vitest";

vi.mock("../client");

describe("Languages API", () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe("getLanguages", () => {
        it("should call GET /languages and map response to camelCase", async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: [
                    { language_code: "en", language_name: "English" },
                    { language_code: "jp", language_name: "Japanese" }
                ]
            });

            const languages = await getLanguages();
            
            expect(client.get).toHaveBeenCalledWith('/languages');
            expectTypeOf(languages).toEqualTypeOf<Language[]>();
            expect(languages).toEqual([
                { languageCode: "en", languageName: "English" },
                { languageCode: "jp", languageName: "Japanese" }
            ] satisfies Language[]);
        });

        it("should return empty array when backend returns empty array", async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: []
            });

            const languages = await getLanguages();
            
            expect(languages).toEqual([]);
        });
    });

    describe("getLanguageByCode", () => {
        it("should call GET /languages/{code} and map response to camelCase", async () => {
            vi.mocked(client.get).mockResolvedValue({
                data: { language_code: "en", language_name: "English" }
            });

            const language = await getLanguageByCode("en");
            
            expect(client.get).toHaveBeenCalledWith('/languages/en');
            expectTypeOf(language).toEqualTypeOf<Language>();
            expect(language).toEqual({ languageCode: "en", languageName: "English" } satisfies Language);
        });

        it("should propagate 404 error when language not found", async () => {
            vi.mocked(client.get).mockRejectedValue(
                makeAxiosError(404, { detail: 'Language not found' })
            );

            await expect(getLanguageByCode("invalid")).rejects.toThrow();
        });
    });
});