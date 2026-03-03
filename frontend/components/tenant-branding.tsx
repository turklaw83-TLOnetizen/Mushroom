"use client";

import { useEffect, useState } from "react";

interface TenantTheme {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_family: string;
  firm_name: string;
  tagline: string;
  logo_url: string;
  sidebar_bg: string;
  header_bg: string;
}

const DEFAULT_THEME: TenantTheme = {
  primary_color: "#6366f1",
  secondary_color: "#8b5cf6",
  accent_color: "#f59e0b",
  font_family: "Inter, system-ui, sans-serif",
  firm_name: "Project Mushroom Cloud",
  tagline: "Legal Intelligence Suite",
  logo_url: "",
  sidebar_bg: "#1e1b4b",
  header_bg: "#ffffff",
};

export function TenantBranding() {
  const [theme, setTheme] = useState<TenantTheme>(DEFAULT_THEME);

  useEffect(() => {
    // Only fetch in multi-tenant mode
    const tenantId = process.env.NEXT_PUBLIC_TENANT_ID;
    if (!tenantId) return;

    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${api}/api/v1/tenants/${tenantId}/branding`)
      .then((r) => r.json())
      .then((data) => {
        if (data.primary_color) setTheme({ ...DEFAULT_THEME, ...data });
      })
      .catch(() => {}); // Use defaults on error
  }, []);

  useEffect(() => {
    // Apply CSS custom properties
    const root = document.documentElement;
    root.style.setProperty("--primary", theme.primary_color);
    root.style.setProperty("--secondary", theme.secondary_color);
    root.style.setProperty("--accent", theme.accent_color);
    root.style.setProperty("--font-family", theme.font_family);
    root.style.setProperty("--sidebar-bg", theme.sidebar_bg);
    root.style.setProperty("--header-bg", theme.header_bg);
  }, [theme]);

  return null; // This component only applies CSS vars
}
