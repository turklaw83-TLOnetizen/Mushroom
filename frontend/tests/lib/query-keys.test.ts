/**
 * Tests for lib/query-keys.ts — cache key factory integrity.
 * Ensures keys are unique, deterministic, and structurally sound.
 */
import { describe, it, expect } from "vitest";
import { queryKeys } from "@/lib/query-keys";

describe("queryKeys", () => {
  // ── Structure Tests ──

  it("has cases section with required operations", () => {
    expect(queryKeys.cases).toBeDefined();
    expect(queryKeys.cases.all).toBeDefined();
    expect(typeof queryKeys.cases.byId).toBe("function");
    expect(typeof queryKeys.cases.preps).toBe("function");
  });

  it("has files section", () => {
    expect(queryKeys.files).toBeDefined();
    expect(typeof queryKeys.files.list).toBe("function");
  });

  // ── Determinism Tests ──

  it("produces same key for same input", () => {
    const key1 = queryKeys.cases.byId("case-123");
    const key2 = queryKeys.cases.byId("case-123");
    expect(key1).toEqual(key2);
  });

  it("produces different keys for different inputs", () => {
    const key1 = queryKeys.cases.byId("case-123");
    const key2 = queryKeys.cases.byId("case-456");
    expect(key1).not.toEqual(key2);
  });

  // ── Hierarchy Tests ──

  it("case.byId key starts with cases prefix", () => {
    const key = queryKeys.cases.byId("case-123");
    expect(key[0]).toBe("cases");
  });

  it("preps key includes case id", () => {
    const key = queryKeys.cases.preps("case-123");
    expect(key).toContain("case-123");
  });

  // ── War Game Keys ──

  it("has warGame section", () => {
    expect(queryKeys.warGame).toBeDefined();
  });

  // ── Readonly Tuple Tests ──

  it("returns readonly tuples", () => {
    const key = queryKeys.cases.all;
    // TypeScript readonly arrays — verify it's an array
    expect(Array.isArray(key)).toBe(true);
  });
});
