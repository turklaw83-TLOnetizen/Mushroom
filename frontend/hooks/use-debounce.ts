// ---- useDebounce Hook ---------------------------------------------------
"use client";

import { useState, useEffect } from "react";

/**
 * Debounce a value by a given delay in milliseconds.
 * Returns the debounced value after the delay has elapsed without changes.
 */
export function useDebounce<T>(value: T, delay = 300): T {
    const [debounced, setDebounced] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);

    return debounced;
}
