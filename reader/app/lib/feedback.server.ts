import {
	type FeedbackAnchor,
	type FeedbackEmoji,
	type FeedbackIssueCategory,
	isFeedbackEmoji,
	isFeedbackIssueCategory,
} from "./feedbackAnchor";

const DEFAULT_BACKEND_URL = "http://reader-api:8001";
const TIMEOUT_MS = 10_000;

export type FeedbackSubmission =
	| {
			kind: "reaction";
			emoji: FeedbackEmoji;
			contentHash?: string | null;
	  }
	| {
			kind: "issue";
			category: FeedbackIssueCategory;
			message: string;
			anchor?: FeedbackAnchor | null;
			contentHash?: string | null;
	  }
	| {
			kind: "comment";
			message: string;
			anchor?: FeedbackAnchor | null;
			contentHash?: string | null;
	  };

export type FeedbackSubmitResult = {
	feedbackId: string;
	createdAt: string;
};

export class FeedbackApiError extends Error {
	readonly status: number;
	readonly detail: string;

	constructor(status: number, detail: string) {
		super(detail);
		this.name = "FeedbackApiError";
		this.status = status;
		this.detail = detail;
	}
}

function backendBaseUrl(): string {
	const configured = process.env.READER_BACKEND_URL?.trim();
	return (configured || DEFAULT_BACKEND_URL).replace(/\/+$/, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function extractString(record: Record<string, unknown>, key: string): string {
	const value = record[key];
	if (typeof value !== "string") {
		throw new FeedbackApiError(502, `Unexpected feedback response: missing "${key}"`);
	}
	return value;
}

async function extractErrorDetail(res: Response): Promise<string> {
	try {
		const payload: unknown = await res.json();
		if (isRecord(payload)) {
			if (typeof payload.detail === "string" && payload.detail.trim()) {
				return payload.detail;
			}
			if (Array.isArray(payload.detail) && payload.detail.length > 0) {
				const first: unknown = payload.detail[0];
				if (isRecord(first) && typeof first.msg === "string" && first.msg.trim()) {
					return first.msg;
				}
			}
		}
	} catch {
		// Fall through to generic status message.
	}
	return `Feedback request failed (${res.status})`;
}

function readFormString(formData: FormData, key: string): string {
	const raw = formData.get(key);
	return typeof raw === "string" ? raw : "";
}

function parseOptionalAnchor(formData: FormData): FeedbackAnchor | null {
	const quote = readFormString(formData, "anchorQuote").trim();
	if (!quote) return null;

	const paragraphIndex = Number(readFormString(formData, "anchorParagraphIndex"));
	const startOffset = Number(readFormString(formData, "anchorStartOffset"));
	const endOffset = Number(readFormString(formData, "anchorEndOffset"));
	if (
		!Number.isInteger(paragraphIndex) ||
		paragraphIndex < 0 ||
		!Number.isInteger(startOffset) ||
		startOffset < 0 ||
		!Number.isInteger(endOffset) ||
		endOffset <= startOffset
	) {
		return null;
	}
	return {
		paragraphIndex,
		startOffset,
		endOffset,
		quote: quote.slice(0, 300),
	};
}

export function parseFeedbackFormData(
	formData: FormData,
): { ok: true; submission: FeedbackSubmission } | { ok: false; error: string } {
	const kind = readFormString(formData, "kind").trim();
	const contentHash = readFormString(formData, "contentHash").trim() || null;

	if (kind === "reaction") {
		const emoji = readFormString(formData, "emoji").trim();
		if (!isFeedbackEmoji(emoji)) {
			return { ok: false, error: "Choose a valid reaction." };
		}
		return { ok: true, submission: { kind: "reaction", emoji, contentHash } };
	}

	const message = readFormString(formData, "message").trim();
	if (!message) {
		return { ok: false, error: "Please enter a short note before sending." };
	}
	if (message.length > 2000) {
		return { ok: false, error: "Feedback message must be 2000 characters or fewer." };
	}

	const anchor = parseOptionalAnchor(formData);

	if (kind === "comment") {
		return { ok: true, submission: { kind: "comment", message, anchor, contentHash } };
	}

	if (kind === "issue") {
		const category = readFormString(formData, "category").trim();
		if (!isFeedbackIssueCategory(category)) {
			return { ok: false, error: "Choose a valid issue category." };
		}
		return {
			ok: true,
			submission: { kind: "issue", category, message, anchor, contentHash },
		};
	}

	if (kind === "detailed") {
		const selection = readFormString(formData, "category").trim();
		if (selection === "comment") {
			return { ok: true, submission: { kind: "comment", message, anchor, contentHash } };
		}
		if (isFeedbackIssueCategory(selection)) {
			return {
				ok: true,
				submission: { kind: "issue", category: selection, message, anchor, contentHash },
			};
		}
		return { ok: false, error: "Choose a valid feedback category." };
	}

	return { ok: false, error: "Unsupported feedback type." };
}

export async function submitChapterFeedback(
	novelId: string,
	chapterNum: number,
	submission: FeedbackSubmission,
	clientMeta?: { forwardedFor?: string | null; userAgent?: string | null },
): Promise<FeedbackSubmitResult> {
	const headers: Record<string, string> = {
		Accept: "application/json",
		"Content-Type": "application/json",
	};
	if (clientMeta?.forwardedFor) {
		headers["X-Forwarded-For"] = clientMeta.forwardedFor;
	}
	if (clientMeta?.userAgent) {
		headers["User-Agent"] = clientMeta.userAgent;
	}

	const body: Record<string, unknown> = { kind: submission.kind };
	if (submission.contentHash) {
		body.contentHash = submission.contentHash;
	}
	if (submission.kind === "reaction") {
		body.emoji = submission.emoji;
	} else if (submission.kind === "issue") {
		body.category = submission.category;
		body.message = submission.message;
		if (submission.anchor) {
			body.anchor = submission.anchor;
		}
	} else {
		body.message = submission.message;
		if (submission.anchor) {
			body.anchor = submission.anchor;
		}
	}

	let res: Response;
	try {
		res = await fetch(
			`${backendBaseUrl()}/novels/${encodeURIComponent(novelId)}/chapters/${chapterNum}/feedback`,
			{
				method: "POST",
				headers,
				body: JSON.stringify(body),
				signal: AbortSignal.timeout(TIMEOUT_MS),
			},
		);
	} catch {
		throw new FeedbackApiError(503, "Feedback service is temporarily unavailable.");
	}

	if (!res.ok) {
		const detail = await extractErrorDetail(res);
		throw new FeedbackApiError(res.status, detail);
	}

	let raw: unknown;
	try {
		raw = await res.json();
	} catch {
		throw new FeedbackApiError(502, "Feedback service returned invalid JSON.");
	}
	if (!isRecord(raw)) {
		throw new FeedbackApiError(502, "Unexpected feedback response payload.");
	}
	return {
		feedbackId: extractString(raw, "feedbackId"),
		createdAt: extractString(raw, "createdAt"),
	};
}
