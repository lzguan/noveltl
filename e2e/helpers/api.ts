import type { APIRequestContext, Page } from "@playwright/test";

import { readSeed } from "./seed";

type TokenResponse = {
  access_token: string;
  token_type: string;
};

type ChapterContentResponse = {
  chapterContentId: string;
  chapterContentText: string;
  chapterContentVersion: number;
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

export function apiUrl(path: string): string {
  const baseUrl = process.env.E2E_API_URL ?? "http://127.0.0.1:8001";
  return new URL(path, baseUrl).toString();
}

export async function loginByApi(page: Page, request: APIRequestContext): Promise<string> {
  const seed = readSeed();
  const response = await request.post(apiUrl("/token"), {
    form: {
      username: seed.user.username,
      password: seed.user.password,
    },
  });

  if (!response.ok()) {
    throw new Error(`Login failed with status ${response.status()}: ${await response.text()}`);
  }

  const body = await response.json();
  if (!isTokenResponse(body)) {
    throw new Error("Login response did not match the expected token shape.");
  }

  await page.addInitScript((token) => {
    window.localStorage.setItem("access_token", token.access_token);
    window.localStorage.setItem("token_type", token.token_type);
  }, body);

  return body.access_token;
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
    throw new Error(`Latest chapter content request failed with status ${response.status()}: ${await response.text()}`);
  }

  const body = await response.json();
  if (!isChapterContentResponse(body)) {
    throw new Error("Chapter content response did not match the expected shape.");
  }

  return body;
}
