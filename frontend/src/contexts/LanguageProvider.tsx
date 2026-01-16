import { useEffect, useState } from "react";
import type { Language } from "../types/language";
import { get_languages } from "../api/languages";
import { LanguageContext } from "./LanguageContext";

export const LanguageProvider = ({ children }: {children: React.ReactNode}) => {
    const [languages, setLanguages] = useState<Language[]>([]);
    useEffect(() => {
        get_languages().then(setLanguages).catch(err => {
            console.error("Failed to fetch languages:", err);
        });
    }, []);
    return (
        <LanguageContext.Provider value={languages}>
            {children}
        </LanguageContext.Provider>
    );
}

