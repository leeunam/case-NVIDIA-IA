import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildMockHumanReviewRunRecord, buildMockRunRecord, buildMockSmokeMatrix } from "../src/mock-data.js";
import { SECTIONS, createInitialState, renderApp, sectionIdFromValue } from "../src/renderer.js";

const css = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("normalizes direct-linked workbench sections for browser QA", () => {
  assert.equal(sectionIdFromValue("runs"), "runs");
  assert.equal(sectionIdFromValue("evidence"), "evidence");
  assert.equal(sectionIdFromValue("assessment"), "assessment");
  assert.equal(sectionIdFromValue("nvidia-match"), "nvidia-match");
  assert.equal(sectionIdFromValue("briefing"), "briefing");
  assert.equal(sectionIdFromValue("production-smokes"), "production-smokes");
  assert.equal(sectionIdFromValue("unsupported"), "runs");
});

test("renders every final QA workbench section with active navigation and no secret-like values", () => {
  const currentRun = buildMockRunRecord(
    {
      startup_url: "https://neuralmind.ai/",
      startup_name: "NeuralMind"
    },
    {
      runId: "mock-final-qa-run",
      createdAt: "2026-06-30T15:00:00.000Z"
    }
  );
  const smokeMatrix = buildMockSmokeMatrix();

  for (const section of SECTIONS) {
    const html = renderApp(createInitialState({ activeSection: section.id, currentRun, smokeMatrix }));

    assert.match(html, /aria-label="Primary navigation"/);
    assert.match(html, /aria-label="Workbench sections"/);
    assert.match(html, new RegExp(`data-section="${section.id}" aria-current="page"`));
    assert.match(html, new RegExp(`data-section="${section.id}" aria-selected="true"`));
    assert.doesNotMatch(html, />undefined</);
    assert.doesNotMatch(html, />null</);
    assert.doesNotMatch(html, /(sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|postgresql:\/\/[^<\s]+:[^<\s]+@)/i);
  }
});

test("renders the current run lookup path used as run-history QA coverage", () => {
  const currentRun = buildMockHumanReviewRunRecord();
  const html = renderApp(createInitialState({ activeSection: "runs", currentRun }));

  assert.match(html, /mock-human-review-run/);
  assert.match(html, /Branch decisions/);
  assert.match(html, /Persistence references/);
  assert.match(html, /human_review_requested/);
});

test("keeps launcher controls labeled and busy state announced", () => {
  const idleHtml = renderApp(createInitialState());
  const busyHtml = renderApp(createInitialState({ isBusy: true }));
  const controlCount = countMatches(idleHtml, /<(input|select)\b/g);
  const labelCount = countMatches(idleHtml, /<label\b/g);

  assert.ok(labelCount >= controlCount);
  assert.match(busyHtml, /disabled aria-busy="true"/);
  assert.match(idleHtml, /role="tablist" aria-label="Run workspace sections"/);
});

test("keeps responsive and overflow CSS guardrails for final QA surfaces", () => {
  assert.match(css, /a:focus-visible/);
  assert.match(css, /button:focus-visible/);
  assert.match(css, /@media \(max-width: 980px\)/);
  assert.match(css, /@media \(max-width: 640px\)/);
  assert.match(css, /\.smoke-row > \*/);
  assert.match(css, /\.context-link[\s\S]*overflow-wrap: anywhere/);
  assert.match(css, /\.run-chip[\s\S]*white-space: nowrap/);
  assert.match(css, /\.source-link[\s\S]*overflow-wrap: anywhere/);
});

function countMatches(text, pattern) {
  return (text.match(pattern) || []).length;
}
