/**
 * Tenant theme utilities for white-label branding.
 */

export interface TenantTheme {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_family: string;
  firm_name: string;
  tagline: string;
  logo_url: string;
  favicon_url: string;
  sidebar_bg: string;
  header_bg: string;
}

export const DEFAULT_THEME: TenantTheme = {
  primary_color: "#6366f1",
  secondary_color: "#8b5cf6",
  accent_color: "#f59e0b",
  font_family: "Inter, system-ui, sans-serif",
  firm_name: "Project Mushroom Cloud",
  tagline: "Legal Intelligence Suite",
  logo_url: "",
  favicon_url: "",
  sidebar_bg: "#1e1b4b",
  header_bg: "#ffffff",
};

export async function fetchTenantTheme(tenantId: string): Promise<TenantTheme> {
  const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${api}/api/v1/tenants/${tenantId}/branding`);
    if (!res.ok) return DEFAULT_THEME;
    const data = await res.json();
    return { ...DEFAULT_THEME, ...data };
  } catch {
    return DEFAULT_THEME;
  }
}

export function applyTheme(theme: TenantTheme) {
  const root = document.documentElement;
  root.style.setProperty("--primary", theme.primary_color);
  root.style.setProperty("--secondary", theme.secondary_color);
  root.style.setProperty("--accent", theme.accent_color);
  root.style.setProperty("--font-family", theme.font_family);
  root.style.setProperty("--sidebar-bg", theme.sidebar_bg);
  root.style.setProperty("--header-bg", theme.header_bg);

  if (theme.favicon_url) {
    const link = document.querySelector("link[rel='icon']") as HTMLLinkElement;
    if (link) link.href = theme.favicon_url;
  }
}
