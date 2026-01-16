import { createContext, useContext } from "react";
import { type Language } from "../types/language";

export const LanguageContext = createContext<Language[]>([]);

export const useLanguages = () => useContext(LanguageContext);