/**
 * Tests for lib/api-routes.ts — route factory integrity.
 * Ensures all routes produce valid paths with correct parameters.
 */
import { describe, it, expect } from "vitest";
import { routes } from "@/lib/api-routes";

describe("routes", () => {
  // ── Static Routes ──

  it("has health endpoint", () => {
    expect(routes.health).toBe("/health");
  });

  // ── Cases ──

  it("generates case routes with id", () => {
    expect(routes.cases.byId("abc")).toBe("/cases/abc");
    expect(routes.cases.preps("abc")).toBe("/cases/abc/preps");
  });

  it("generates prep state route", () => {
    expect(routes.cases.prepState("abc", "p1")).toBe("/cases/abc/preps/p1/state");
  });

  // ── Users ──

  it("generates user routes", () => {
    expect(routes.users.list).toBe("/users");
    expect(routes.users.byId("u1")).toBe("/users/u1");
  });

  // ── War Game ──

  it("has warGame section", () => {
    expect(routes.warGame).toBeDefined();
  });

  it("generates war game session routes", () => {
    const sessionsPath = routes.warGame.sessions("c1", "p1");
    expect(sessionsPath).toContain("c1");
    expect(sessionsPath).toContain("p1");
    expect(sessionsPath).toContain("war-game");
  });

  it("generates war game attack route", () => {
    const attackPath = routes.warGame.attack("c1", "p1", "s1", "theory");
    expect(attackPath).toContain("theory");
    expect(attackPath).toContain("attack");
  });

  // ── No Trailing Slashes ──

  it("routes don't have trailing slashes", () => {
    const testRoutes = [
      routes.health,
      routes.cases.list,
      routes.users.list,
      routes.cases.byId("test"),
    ];
    for (const r of testRoutes) {
      expect(r.endsWith("/")).toBe(false);
    }
  });

  // ── No Double Slashes ──

  it("routes don't have double slashes", () => {
    const testRoutes = [
      routes.cases.byId("test"),
      routes.cases.preps("test"),
      routes.cases.prepState("test", "p1"),
    ];
    for (const r of testRoutes) {
      expect(r).not.toContain("//");
    }
  });
});
