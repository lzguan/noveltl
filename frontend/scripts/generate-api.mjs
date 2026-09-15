import { spawnSync } from "node:child_process";
import { rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const frontend = new URL("../", import.meta.url);

// These directories are wholly generated. Keep handwritten API helpers intact.
// Clean once: the fetch and Effect generators share the endpoints directory.
for (const directory of ["src/api/endpoints/", "src/api/models/"]) {
	await rm(new URL(directory, frontend), { recursive: true, force: true });
}

const result = spawnSync("pnpm", ["exec", "orval"], {
	cwd: fileURLToPath(frontend),
	stdio: "inherit",
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
