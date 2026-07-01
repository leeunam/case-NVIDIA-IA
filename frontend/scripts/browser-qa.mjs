import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  buildMockHumanReviewRunRecord,
  buildMockRunRecord,
  buildMockSmokeMatrix
} from "../src/mock-data.js";
import { createInitialState, renderApp } from "../src/renderer.js";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const outputDir = process.env.FRONTEND_QA_OUTPUT_DIR || join(tmpdir(), "nvidia-startup-intel-frontend-qa");
const chrome = process.env.CHROME_BIN || firstExistingPath(["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]);
const viewports = [
  { name: "desktop", size: "1366,900" },
  { name: "mobile", size: "390,844" }
];
const completedRun = buildMockRunRecord(
  {
    startup_url: "https://neuralmind.ai/",
    startup_name: "NeuralMind"
  },
  {
    runId: "mock-completed-run",
    createdAt: "2026-06-30T15:00:00.000Z"
  }
);
const humanReviewRun = buildMockHumanReviewRunRecord();
const smokeMatrix = buildMockSmokeMatrix();
const scenarios = [
  { name: "launcher", state: createInitialState({ activeSection: "runs" }) },
  { name: "run-workspace", state: createInitialState({ activeSection: "runs", currentRun: completedRun }) },
  { name: "evidence", state: createInitialState({ activeSection: "evidence", currentRun: completedRun }) },
  { name: "assessment", state: createInitialState({ activeSection: "assessment", currentRun: completedRun }) },
  { name: "nvidia-match", state: createInitialState({ activeSection: "nvidia-match", currentRun: completedRun }) },
  { name: "briefing", state: createInitialState({ activeSection: "briefing", currentRun: completedRun }) },
  { name: "run-history", state: createInitialState({ activeSection: "runs", currentRun: humanReviewRun }) },
  { name: "production-smokes", state: createInitialState({ activeSection: "production-smokes", smokeMatrix }) }
];

if (!chrome) {
  throw new Error("Chrome was not found. Set CHROME_BIN to run browser QA.");
}

await mkdir(outputDir, { recursive: true });
const css = await readFile(join(root, "src/styles.css"), "utf8");

for (const scenario of scenarios) {
  const htmlPath = join(outputDir, `${scenario.name}.html`);
  await writeFile(htmlPath, htmlDocument(renderApp(scenario.state), css), "utf8");
  for (const viewport of viewports) {
    await captureScreenshot({ viewport, scenario, htmlPath });
  }
}

console.log(`Frontend browser QA screenshots: ${outputDir}`);

async function captureScreenshot({ viewport, scenario, htmlPath }) {
  const screenshot = join(outputDir, `${viewport.name}-${scenario.name}.png`);
  const userDataDir = join(outputDir, `.chrome-${viewport.name}-${scenario.name}`);
  const result = spawnSync(
    chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--no-sandbox",
      "--hide-scrollbars",
      `--user-data-dir=${userDataDir}`,
      `--window-size=${viewport.size}`,
      `--screenshot=${screenshot}`,
      pathToFileURL(htmlPath).href
    ],
    { encoding: "utf8", timeout: 20000, killSignal: "SIGKILL" }
  );
  if (result.error) {
    throw new Error(`browser_qa_failed:${viewport.name}:${scenario.name}:${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(
      `browser_qa_failed:${viewport.name}:${scenario.name}:${result.stderr || result.stdout || "chrome_failed"}`
    );
  }
  const fileStat = await stat(screenshot);
  if (!fileStat.isFile() || fileStat.size <= 0) {
    throw new Error(`browser_qa_empty_screenshot:${screenshot}`);
  }
  console.log(`${viewport.name} ${scenario.name}: ${screenshot}`);
}

function htmlDocument(appHtml, css) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>NVIDIA Startup Intel Workbench QA</title>
    <style>${css}</style>
  </head>
  <body>
    ${appHtml}
  </body>
</html>
`;
}

function firstExistingPath(paths) {
  return paths.find((path) => existsSync(path)) || "";
}
