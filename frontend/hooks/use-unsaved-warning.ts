"use client";
import { useEffect } from "react";

/** Warns the user before leaving the page when there are unsaved changes. */
export function useUnsavedWarning(isDirty: boolean) {
  useEffect(() => {
    if (!isDirty) return;

    function onBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault();
      e.returnValue = "";
    }

    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty]);
}
