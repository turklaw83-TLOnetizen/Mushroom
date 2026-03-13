#!/usr/bin/env tsx
// ── Spec Verification Script ────────────────────────────────────
// Checks the codebase against scripts/spec-manifest.json and prints
// a pass/fail report showing counts, new files, and missing files.
//
// Run with:
//   npx tsx scripts/verify-spec.ts          # Verify mode (default)
//   npx tsx scripts/verify-spec.ts --update  # Auto-update manifest from disk
//
// The --update flag scans the filesystem and regenerates the manifest
// so the harness stays in sync as features are added or removed.

import { readFileSync, writeFileSync, readdirSync, statSync } from "fs";
import { join, relative, resolve } from "path";

const ROOT = resolve(__dirname, "..");
const UPDATE_MODE = process.argv.includes("--update");

// ── Glob helper (recursive pattern matching) ─────────────────────

function globFiles(pattern: string, root: string): string[] {
  const isDirPattern = pattern.endsWith("/");
  const parts = pattern.replace(/\/$/, "").split("/");
  return walkGlob(root, parts, 0, isDirPattern).map((f) =>
    relative(root, f).replace(/\\/g, "/")
  );
}

function walkGlob(
  dir: string,
  parts: string[],
  idx: number,
  isDirPattern: boolean
): string[] {
  if (idx >= parts.length) return [];

  const part = parts[idx];
  const isLast = idx === parts.length - 1;

  if (part === "**") {
    const results: string[] = [];
    results.push(...walkGlob(dir, parts, idx + 1, isDirPattern));
    for (const entry of safeReaddir(dir)) {
      const full = join(dir, entry);
      if (isDirectory(full)) {
        results.push(...walkGlob(full, parts, idx, isDirPattern));
      }
    }
    return results;
  }

  if (part.includes("*")) {
    const results: string[] = [];
    for (const entry of safeReaddir(dir)) {
      if (matchWildcard(entry, part)) {
        const full = join(dir, entry);
        if (isLast) {
          if (isDirPattern) {
            if (isDirectory(full)) results.push(full);
          } else {
            if (!isDirectory(full)) results.push(full);
          }
        } else {
          if (isDirectory(full)) {
            results.push(...walkGlob(full, parts, idx + 1, isDirPattern));
          }
        }
      }
    }
    return results;
  }

  // Literal segment (including [id] brackets)
  const full = join(dir, part);
  if (isLast) {
    if (isDirPattern) {
      if (isDirectory(full)) return [full];
    } else {
      if (fileExists(full) && !isDirectory(full)) return [full];
    }
    return [];
  }

  if (isDirectory(full)) {
    return walkGlob(full, parts, idx + 1, isDirPattern);
  }

  // Literal doesn't match — try wildcard match for bracket segments like [id]
  const results: string[] = [];
  for (const entry of safeReaddir(dir)) {
    if (entry === part || matchWildcard(entry, part)) {
      const entryFull = join(dir, entry);
      if (isDirectory(entryFull)) {
        results.push(...walkGlob(entryFull, parts, idx + 1, isDirPattern));
      }
    }
  }
  return results;
}

function matchWildcard(str: string, pattern: string): boolean {
  const regex = new RegExp(
    "^" +
      pattern
        .replace(/[.+^${}()|[\]\\]/g, "\\$&")
        .replace(/\*/g, ".*")
        .replace(/\?/g, ".") +
      "$"
  );
  return regex.test(str);
}

function safeReaddir(dir: string): string[] {
  try {
    return readdirSync(dir);
  } catch {
    return [];
  }
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function fileExists(path: string): boolean {
  try {
    statSync(path);
    return true;
  } catch {
    return false;
  }
}

// ── Load manifest ────────────────────────────────────────────────

interface ManifestCategory {
  pattern: string;
  expectedCount: number;
  expectedFiles?: string[];
  expectedDirs?: string[];
}

interface Manifest {
  description: string;
  updatedAt: string;
  categories: Record<string, ManifestCategory>;
}

const manifestPath = join(ROOT, "scripts", "spec-manifest.json");
const manifest: Manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));

// ── Update mode: regenerate manifest from disk ───────────────────

if (UPDATE_MODE) {
  console.log("Updating spec-manifest.json from current filesystem...\n");

  for (const [name, category] of Object.entries(manifest.categories)) {
    const isDir = category.pattern.endsWith("/");
    const found = globFiles(category.pattern, ROOT).sort();

    category.expectedCount = found.length;
    if (isDir) {
      category.expectedDirs = found;
      delete category.expectedFiles;
    } else {
      category.expectedFiles = found;
      delete category.expectedDirs;
    }

    console.log(`  ${name}: ${found.length} items`);
  }

  manifest.updatedAt = new Date().toISOString().slice(0, 10);
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf-8");
  console.log(`\nManifest updated (${manifest.updatedAt}).`);
  process.exit(0);
}

// ── Verify each category ─────────────────────────────────────────

let allPassed = true;
let totalExpected = 0;
let totalFound = 0;

console.log("=".repeat(60));
console.log("  SPEC VERIFICATION REPORT");
console.log(`  Manifest: ${manifest.updatedAt}`);
console.log("=".repeat(60));
console.log();

for (const [name, category] of Object.entries(manifest.categories)) {
  const found = globFiles(category.pattern, ROOT).sort();
  const expected = (category.expectedFiles ?? category.expectedDirs ?? [])
    .map((f) => f.replace(/\\/g, "/"))
    .sort();

  const countMatch = found.length === category.expectedCount;
  const newItems = found.filter((f) => !expected.includes(f));
  const missingItems = expected.filter((f) => !found.includes(f));
  const passed = countMatch && newItems.length === 0 && missingItems.length === 0;

  if (!passed) allPassed = false;
  totalExpected += category.expectedCount;
  totalFound += found.length;

  const status = passed ? "PASS" : "FAIL";
  const icon = passed ? "[OK]" : "[!!]";

  console.log(
    `${icon} ${name}: ${found.length}/${category.expectedCount} ${status}`
  );

  if (!countMatch) {
    console.log(
      `     Count mismatch: found ${found.length}, expected ${category.expectedCount}`
    );
  }

  if (newItems.length > 0) {
    console.log(`     NEW (not in manifest):`);
    for (const item of newItems) {
      console.log(`       + ${item}`);
    }
  }

  if (missingItems.length > 0) {
    console.log(`     MISSING (in manifest but not on disk):`);
    for (const item of missingItems) {
      console.log(`       - ${item}`);
    }
  }

  console.log();
}

// ── Summary ──────────────────────────────────────────────────────

console.log("=".repeat(60));
if (allPassed) {
  console.log(
    `  ALL CHECKS PASSED  (${totalFound} items across ${Object.keys(manifest.categories).length} categories)`
  );
} else {
  console.log(
    `  SOME CHECKS FAILED  (found ${totalFound}, expected ${totalExpected})`
  );
  console.log();
  console.log("  TIP: Run with --update to auto-sync manifest from disk:");
  console.log("    npx tsx scripts/verify-spec.ts --update");
}
console.log("=".repeat(60));

process.exit(allPassed ? 0 : 1);
