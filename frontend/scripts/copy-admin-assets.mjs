import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");

mkdirSync(dist, { recursive: true });

for (const file of ["admin.html"]) {
  const src = join(root, file);
  if (existsSync(src)) {
    copyFileSync(src, join(dist, file));
  }
}
