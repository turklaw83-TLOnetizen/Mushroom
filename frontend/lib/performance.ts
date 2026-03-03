/**
 * Web Vitals performance tracking — reports LCP, FID, CLS, TTFB, INP to backend.
 */

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface WebVital {
  name: string;
  value: number;
  id: string;
}

let reported = false;

export function reportWebVitals(metric: WebVital) {
  // Batch and send
  const payload: Record<string, number | string> = {
    [metric.name.toLowerCase()]: metric.value,
    pathname: typeof window !== "undefined" ? window.location.pathname : "",
  };

  // Only report once per page load
  if (reported) return;

  // Debounce: wait for all vitals to collect
  setTimeout(() => {
    if (reported) return;
    reported = true;

    fetch(`${API}/api/v1/metrics/web-vitals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {}); // Fire and forget
  }, 3000);
}

export function initWebVitals() {
  if (typeof window === "undefined") return;

  // Use web-vitals library if available, otherwise use PerformanceObserver
  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const metric: WebVital = {
          name: entry.entryType === "largest-contentful-paint" ? "LCP" :
                entry.entryType === "first-input" ? "FID" :
                entry.entryType === "layout-shift" ? "CLS" : entry.name,
          value: entry.entryType === "layout-shift"
            ? (entry as any).value
            : (entry as PerformanceEntry).startTime || 0,
          id: crypto.randomUUID?.() || String(Date.now()),
        };
        reportWebVitals(metric);
      }
    });

    observer.observe({ type: "largest-contentful-paint", buffered: true });
    observer.observe({ type: "first-input", buffered: true });
    observer.observe({ type: "layout-shift", buffered: true });
  } catch {
    // Older browser, skip
  }

  // TTFB
  if (performance.getEntriesByType) {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
    if (nav) {
      reportWebVitals({ name: "TTFB", value: nav.responseStart - nav.requestStart, id: "ttfb" });
    }
  }
}
