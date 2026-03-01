/**
 * Offline Queue (Phase 23) — stores failed mutations in IndexedDB
 * and replays them when connection is restored.
 */

const DB_NAME = "mushroom_cloud_offline";
const STORE_NAME = "pending_mutations";
const DB_VERSION = 1;

interface PendingMutation {
    id: string;
    method: string;
    path: string;
    body?: unknown;
    timestamp: number;
    retries: number;
}

function openDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: "id" });
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

export async function enqueue(mutation: Omit<PendingMutation, "id" | "timestamp" | "retries">): Promise<void> {
    try {
        const db = await openDB();
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        const entry: PendingMutation = {
            ...mutation,
            id: crypto.randomUUID?.() || Date.now().toString(),
            timestamp: Date.now(),
            retries: 0,
        };
        store.put(entry);
        await new Promise<void>((resolve, reject) => {
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    } catch {
        // IndexedDB not available — silently drop
    }
}

export async function getPending(): Promise<PendingMutation[]> {
    try {
        const db = await openDB();
        const tx = db.transaction(STORE_NAME, "readonly");
        const store = tx.objectStore(STORE_NAME);
        const req = store.getAll();
        return new Promise((resolve, reject) => {
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject(req.error);
        });
    } catch {
        return [];
    }
}

export async function removePending(id: string): Promise<void> {
    try {
        const db = await openDB();
        const tx = db.transaction(STORE_NAME, "readwrite");
        tx.objectStore(STORE_NAME).delete(id);
        await new Promise<void>((resolve, reject) => {
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    } catch {
        // silent
    }
}

export async function replayPending(
    executeFn: (method: string, path: string, body?: unknown) => Promise<boolean>,
): Promise<{ succeeded: number; failed: number }> {
    const pending = await getPending();
    let succeeded = 0;
    let failed = 0;

    for (const mutation of pending.sort((a, b) => a.timestamp - b.timestamp)) {
        try {
            const ok = await executeFn(mutation.method, mutation.path, mutation.body);
            if (ok) {
                await removePending(mutation.id);
                succeeded++;
            } else {
                failed++;
            }
        } catch {
            failed++;
        }
    }

    return { succeeded, failed };
}

export async function clearAll(): Promise<void> {
    try {
        const db = await openDB();
        const tx = db.transaction(STORE_NAME, "readwrite");
        tx.objectStore(STORE_NAME).clear();
        await new Promise<void>((resolve, reject) => {
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    } catch {
        // silent
    }
}

// Auto-replay on reconnect
if (typeof window !== "undefined") {
    window.addEventListener("online", () => {
        // Delay to let connection stabilize
        setTimeout(async () => {
            const { replayPending } = await import("./offline-queue");
            const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const token = localStorage.getItem("token") || "";

            await replayPending(async (method, path, body) => {
                try {
                    const res = await fetch(`${API}/api/v1${path}`, {
                        method,
                        headers: {
                            "Content-Type": "application/json",
                            Authorization: `Bearer ${token}`,
                        },
                        body: body ? JSON.stringify(body) : undefined,
                    });
                    return res.ok;
                } catch {
                    return false;
                }
            });
        }, 2000);
    });
}
