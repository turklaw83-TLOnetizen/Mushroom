"use client";

import { useState, useEffect } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Find the main scrollable content area
    function getScrollContainer() {
      return document.querySelector("main > .flex-1.overflow-y-auto") as HTMLElement | null
        || document.querySelector("main") as HTMLElement | null;
    }

    function handleScroll() {
      const el = getScrollContainer();
      if (!el) return;
      setVisible(el.scrollTop > 400);
    }

    // Try to attach to the main scroll container
    const el = getScrollContainer();
    if (el) {
      el.addEventListener("scroll", handleScroll, { passive: true });
      return () => el.removeEventListener("scroll", handleScroll);
    }

    // Fallback to window scroll
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    const el = document.querySelector("main > .flex-1.overflow-y-auto") as HTMLElement | null
      || document.querySelector("main") as HTMLElement | null;
    if (el) {
      el.scrollTo({ top: 0, behavior: "smooth" });
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={scrollToTop}
      aria-label="Scroll to top"
      className={`fixed bottom-20 right-6 z-40 h-10 w-10 rounded-full shadow-lg bg-card/90 backdrop-blur-sm border transition-all duration-200 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"
      }`}
    >
      <ArrowUp className="h-4 w-4" />
    </Button>
  );
}
