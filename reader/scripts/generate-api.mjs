import { spawnSync } from "node:child_process";
import { rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const reader = new URL("../", import.meta.url);

// These directories are wholly generated. The handwritten fetch wrapper lives beside them.
for (const directory of ["app/api/endpoints/", "app/api/models/"]) {
	await rm(new URL(directory, reader), { recursive: true, force: true });
}

const result = spawnSync("pnpm", ["exec", "orval"], {
	cwd: fileURLToPath(reader),
	stdio: "inherit",
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
