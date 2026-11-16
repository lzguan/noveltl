import { data } from "react-router";
import { BackendError, BackendUnavailableError } from "../api/backend-fetch";
import {
	readChapterContentChaptersChapterIdContentGet,
	readChaptersByNovelChaptersGet,
	readNovelNovelsNovelIdGet,
	readNovelsNovelsGet,
} from "../api/endpoints/default/default";

export const listNovels = () => readNovelsNovelsGet();
export const getNovel = (novelId: string) => readNovelNovelsNovelIdGet(novelId);
export const listChapters = (novelId: string) => readChaptersByNovelChaptersGet({ novelId });
export const getChapterContent = (chapterId: string) =>
	readChapterContentChaptersChapterIdContentGet(chapterId);

export function notFound(message = "Not found"): never {
	throw data(message, { status: 404 });
}

// Converts backend failures into route error responses; anything else is rethrown untouched.
export function toRouteError(error: unknown): never {
	if (error instanceof BackendError) {
		if (error.status === 404 || error.status === 422 || error.status === 401) {
			notFound();
		}
		console.error(error);
		throw data("The library server rejected the request.", { status: 502 });
	}
	if (error instanceof BackendUnavailableError) {
		console.error(error);
		throw data("The library server is unavailable. Please try again shortly.", {
			status: 503,
		});
	}
	throw error;
}
