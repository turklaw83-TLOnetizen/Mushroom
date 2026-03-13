/**
 * Tests for lib/constants.ts — formatters and status color system.
 */
import { describe, it, expect } from "vitest";
import {
  formatLabel,
  formatDate,
  formatBytes,
  formatCurrency,
  getStatusColor,
  ESIGN_STATUS_COLORS,
  INVOICE_STATUS_COLORS,
  WAR_GAME_DIFFICULTY_COLORS,
  VERDICT_COLORS,
} from "@/lib/constants";

// ── formatLabel ──

describe("formatLabel", () => {
  it("converts snake_case to Title Case", () => {
    expect(formatLabel("evidence_strength")).toBe("Evidence Strength");
  });

  it("converts kebab-case to Title Case", () => {
    expect(formatLabel("war-game")).toBe("War Game");
  });

  it("handles single word", () => {
    expect(formatLabel("active")).toBe("Active");
  });

  it("handles empty string", () => {
    expect(formatLabel("")).toBe("");
  });
});

// ── formatDate ──

describe("formatDate", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2026-03-12T10:00:00");
    expect(result).toContain("Mar");
    expect(result).toContain("12");
    expect(result).toContain("2026");
  });

  it("returns dash for null", () => {
    expect(formatDate(null)).toBe("\u2014");
  });

  it("returns dash for undefined", () => {
    expect(formatDate(undefined)).toBe("\u2014");
  });

  it("returns dash for empty string", () => {
    expect(formatDate("")).toBe("\u2014");
  });
});

// ── formatBytes ──

describe("formatBytes", () => {
  it("formats zero bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it("formats bytes", () => {
    expect(formatBytes(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    const result = formatBytes(1536);
    expect(result).toContain("KB");
  });

  it("formats megabytes", () => {
    const result = formatBytes(1048576);
    expect(result).toContain("MB");
  });

  it("formats gigabytes", () => {
    const result = formatBytes(1073741824);
    expect(result).toContain("GB");
  });
});

// ── formatCurrency ──

describe("formatCurrency", () => {
  it("formats whole dollar amount", () => {
    expect(formatCurrency(100)).toBe("$100.00");
  });

  it("formats cents", () => {
    expect(formatCurrency(99.5)).toBe("$99.50");
  });

  it("formats large amounts with commas", () => {
    expect(formatCurrency(10000)).toBe("$10,000.00");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0.00");
  });
});

// ── getStatusColor ──

describe("getStatusColor", () => {
  it("returns esign color for known status", () => {
    const result = getStatusColor("signed", "esign");
    expect(result).toContain("green");
  });

  it("returns invoice color for known status", () => {
    const result = getStatusColor("paid", "invoice");
    expect(result).toContain("green");
  });

  it("falls back to generic for unknown domain status", () => {
    const result = getStatusColor("active", "generic");
    expect(result).toBeTruthy();
  });

  it("returns zinc fallback for completely unknown status", () => {
    const result = getStatusColor("xyzunknown123", "generic");
    expect(result).toContain("zinc");
  });
});

// ── Color Map Completeness ──

describe("Status Color Maps", () => {
  it("ESIGN has all expected statuses", () => {
    const expected = ["pending", "sent", "viewed", "signed", "declined"];
    for (const status of expected) {
      expect(ESIGN_STATUS_COLORS[status]).toBeDefined();
    }
  });

  it("INVOICE has all expected statuses", () => {
    const expected = ["draft", "sent", "paid", "overdue"];
    for (const status of expected) {
      expect(INVOICE_STATUS_COLORS[status]).toBeDefined();
    }
  });

  it("WAR_GAME_DIFFICULTY has all levels", () => {
    expect(WAR_GAME_DIFFICULTY_COLORS["standard"]).toBeDefined();
    expect(WAR_GAME_DIFFICULTY_COLORS["aggressive"]).toBeDefined();
    expect(WAR_GAME_DIFFICULTY_COLORS["ruthless"]).toBeDefined();
  });

  it("VERDICT has all outcomes", () => {
    expect(VERDICT_COLORS["favorable"]).toBeDefined();
    expect(VERDICT_COLORS["unfavorable"]).toBeDefined();
    expect(VERDICT_COLORS["mixed"]).toBeDefined();
  });
});
