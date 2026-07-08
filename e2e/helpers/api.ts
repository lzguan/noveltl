import type { APIRequestContext, Page } from "@playwright/test";

import { readSeed } from "./seed.js";

type Credentials = {
	username: string;
	password: string;
};

type TokenResponse = {
	access_token: string;
	token_type: string;
};

type ChapterContentResponse = {
	chapterContentId: string;
	chapterContentText: string;
	chapterContentVersion: number;
};

type LabelGroupWithRoleResponse = {
	labelGroup: {
		labelGroupId: string;
		labelGroupName: string;
		novelId: string;
	};
	role: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null;
}

function isTokenResponse(value: unknown): value is TokenResponse {
	return (
		isRecord(value) &&
		typeof value.access_token === "string" &&
		typeof value.token_type === "string"
	);
}

function isChapterContentResponse(value: unknown): value is ChapterContentResponse {
	return (
		isRecord(value) &&
		typeof value.chapterContentId === "string" &&
		typeof value.chapterContentText === "string" &&
		typeof value.chapterContentVersion === "number"
	);
}

function isLabelGroupWithRoleResponse(value: unknown): value is LabelGroupWithRoleResponse {
	return (
		isRecord(value) &&
		isRecord(value.labelGroup) &&
		typeof value.labelGroup.labelGroupId === "string" &&
		typeof value.labelGroup.labelGroupName === "string" &&
		typeof value.labelGroup.novelId === "string" &&
		typeof value.role === "string"
	);
}

export function apiUrl(path: string): string {
	const baseUrl = process.env.E2E_API_URL ?? "http://127.0.0.1:8001";
	return new URL(path, baseUrl).toString();
}

export async function loginToken(
	request: APIRequestContext,
	credentials: Credentials,
): Promise<TokenResponse> {
	const response = await request.post(apiUrl("/token"), {
		form: {
			username: credentials.username,
			password: credentials.password,
		},
	});

	if (!response.ok()) {
		throw new Error(`Login failed with status ${response.status()}: ${await response.text()}`);
	}

	const body = await response.json();
	if (!isTokenResponse(body)) {
		throw new Error("Login response did not match the expected token shape.");
	}

	return body;
}

export async function loginByApi(
	page: Page,
	request: APIRequestContext,
	credentials: Credentials = readSeed().user,
): Promise<string> {
	const body = await loginToken(request, credentials);

	await page.addInitScript((token) => {
		window.localStorage.setItem("access_token", token.access_token);
		window.localStorage.setItem("token_type", token.token_type);
	}, body);

	return body.access_token;
}

export async function labelGroupsWithRole(
	request: APIRequestContext,
	token: string,
	novelId: string,
): Promise<LabelGroupWithRoleResponse[]> {
	const response = await request.get(apiUrl(`/label-groups-with-role?novelId=${novelId}`), {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});

	if (!response.ok()) {
		throw new Error(
			`Label groups request failed with status ${response.status()}: ${await response.text()}`,
		);
	}

	const body = await response.json();
	if (!Array.isArray(body) || !body.every(isLabelGroupWithRoleResponse)) {
		throw new Error("Label groups response did not match the expected shape.");
	}

	return body;
}

export async function latestChapterContent(
	request: APIRequestContext,
	token: string,
	chapterId: string,
): Promise<ChapterContentResponse> {
	const response = await request.get(apiUrl(`/chapters/${chapterId}/content`), {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});

	if (!response.ok()) {
		throw new Error(
			`Latest chapter content request failed with status ${response.status()}: ${await response.text()}`,
		);
	}

	const body = await response.json();
	if (!isChapterContentResponse(body)) {
		throw new Error("Chapter content response did not match the expected shape.");
	}

	return body;
}
