import { spawnSync } from "node:child_process";
import { readdir } from "node:fs/promises";
import { dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const checkedExtensions = new Set([".js", ".mjs"]);
const ignoredDirectories = new Set(["dist", "node_modules"]);
const files = await collectJavaScriptFiles(root);
const failures = [];

for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], {
    encoding: "utf8"
  });
  if (result.status !== 0) {
    failures.push({ file, result });
  }
}

if (failures.length) {
  for (const failure of failures) {
    console.error(`Syntax check failed: ${relative(root, failure.file)}`);
    if (failure.result.stdout) {
      console.error(failure.result.stdout.trim());
    }
    if (failure.result.stderr) {
      console.error(failure.result.stderr.trim());
    }
  }
  process.exit(1);
}

console.log(`Checked ${files.length} frontend JavaScript files.`);

async function collectJavaScriptFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) {
        files.push(...(await collectJavaScriptFiles(path)));
      }
      continue;
    }
    if (entry.isFile() && checkedExtensions.has(extname(entry.name))) {
      files.push(path);
    }
  }
  return files.sort();
}
