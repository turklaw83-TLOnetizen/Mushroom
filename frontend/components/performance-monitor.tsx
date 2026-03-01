"use client";

import { useEffect } from "react";
import { initWebVitals } from "@/lib/performance";

export function PerformanceMonitor() {
  useEffect(() => {
    initWebVitals();
  }, []);

  return null;
}
