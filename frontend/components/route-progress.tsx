"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname } from "next/navigation";

export function RouteProgress() {
  const pathname = usePathname();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const prevPathRef = useRef(pathname);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // When pathname changes, the navigation already completed
    if (prevPathRef.current !== pathname) {
      // Complete the bar
      setProgress(100);
      setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 200);
      prevPathRef.current = pathname;
    }
  }, [pathname]);

  // Intercept link clicks to start the progress bar
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = (e.target as HTMLElement).closest("a");
      if (!target) return;
      const href = target.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("http") || href.startsWith("mailto:")) return;
      if (href === pathname) return; // Same page
      if (e.metaKey || e.ctrlKey || e.shiftKey) return; // New tab

      // Start progress
      setVisible(true);
      setProgress(15);

      // Simulate progress
      let current = 15;
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        current += Math.random() * 12;
        if (current > 90) {
          current = 90;
          if (timerRef.current) clearInterval(timerRef.current);
        }
        setProgress(current);
      }, 200);
    }

    document.addEventListener("click", handleClick, true);
    return () => {
      document.removeEventListener("click", handleClick, true);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [pathname]);

  if (!visible && progress === 0) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[200] h-[3px] pointer-events-none">
      <div
        className="h-full bg-gradient-to-r from-[oklch(0.55_0.23_264)] to-[oklch(0.62_0.21_293)] transition-all duration-200 ease-out"
        style={{
          width: `${progress}%`,
          opacity: visible || progress > 0 ? 1 : 0,
        }}
      />
    </div>
  );
}
