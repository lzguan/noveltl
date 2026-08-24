import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const e2eDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(e2eDir, "..");
const seedFile = process.env.E2E_SEED_FILE ?? path.join(e2eDir, ".seed.json");

function requiredEnv(name: string): string {
	const value = process.env[name];
	if (!value) {
		throw new Error(`${name} must be set for e2e tests.`);
	}
	return value;
}

export default function globalSetup() {
	if (process.env.E2E_SKIP_SEED === "1") {
		return;
	}

	const dbUrl = process.env.E2E_DB_URL ?? process.env.TEST_URL;
	if (!dbUrl) {
		requiredEnv("TEST_URL");
	}

	execFileSync(
		"uv",
		["--directory", "backend", "run", "--no-sync", "python", "scripts/e2e_seed.py"],
		{
			cwd: repoRoot,
			env: {
				...process.env,
				DB_HOST: process.env.E2E_DB_HOST ?? process.env.TEST_HOST ?? process.env.DB_HOST,
				DB_USER: process.env.E2E_DB_USER ?? process.env.TEST_USER ?? process.env.DB_USER,
				DB_PASSWORD:
					process.env.E2E_DB_PASSWORD ??
					process.env.TEST_PASSWORD ??
					process.env.DB_PASSWORD,
				DB_NAME: process.env.E2E_DB_NAME ?? process.env.TEST_NAME ?? process.env.DB_NAME,
				DB_URL: dbUrl,
				REDIS_HOST: process.env.E2E_REDIS_HOST ?? "test_redis",
				REDIS_PORT: process.env.E2E_REDIS_PORT ?? process.env.REDIS_PORT ?? "6379",
				SECRET_KEY: process.env.SECRET_KEY ?? "e2e-secret",
				E2E_SEED_FILE: seedFile,
			},
			stdio: "inherit",
		},
	);
}
