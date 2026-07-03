import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

type E2ESeed = {
  user: {
    username: string;
    password: string;
  };
  novelId: string;
  chapterId: string;
  chapterTitle: string;
  chapterText: string;
  chapterContentId: string;
  chapterContentVersion: number;
  labelGroupId: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isSeed(value: unknown): value is E2ESeed {
  if (!isRecord(value) || !isRecord(value.user)) {
    return false;
  }

  return (
    typeof value.user.username === "string" &&
    typeof value.user.password === "string" &&
    typeof value.novelId === "string" &&
    typeof value.chapterId === "string" &&
    typeof value.chapterTitle === "string" &&
    typeof value.chapterText === "string" &&
    typeof value.chapterContentId === "string" &&
    typeof value.chapterContentVersion === "number" &&
    typeof value.labelGroupId === "string"
  );
}

export function readSeed(): E2ESeed {
  const e2eDir = path.dirname(fileURLToPath(import.meta.url));
  const seedFile = process.env.E2E_SEED_FILE ?? path.resolve(e2eDir, "..", ".seed.json");
  const parsed = JSON.parse(fs.readFileSync(seedFile, "utf-8"));

  if (!isSeed(parsed)) {
    throw new Error(`Invalid e2e seed file: ${seedFile}`);
  }

  return parsed;
}
