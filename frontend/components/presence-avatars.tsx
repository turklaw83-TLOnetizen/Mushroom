"use client";

import { usePresence } from "@/hooks/use-presence";

const COLORS = ["bg-blue-500", "bg-green-500", "bg-purple-500", "bg-orange-500", "bg-pink-500"];
const MAX_VISIBLE = 5;

export function PresenceAvatars({ caseId }: { caseId: string }) {
  const { viewers, isConnected } = usePresence(caseId);

  if (!isConnected || viewers.length === 0) return null;

  const visible = viewers.slice(0, MAX_VISIBLE);
  const overflow = viewers.length - MAX_VISIBLE;

  return (
    <div className="flex items-center -space-x-2">
      {visible.map((v, i) => (
        <div
          key={v.user_id}
          className={`relative w-8 h-8 rounded-full ${COLORS[i % COLORS.length]} flex items-center justify-center text-white text-xs font-bold ring-2 ring-white`}
          title={`${v.name} (${v.role})`}
        >
          {v.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()}
          <span
            className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white ${
              v.status === "active" ? "bg-green-400 animate-pulse" : "bg-yellow-400"
            }`}
          />
        </div>
      ))}
      {overflow > 0 && (
        <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-xs font-medium ring-2 ring-white">
          +{overflow}
        </div>
      )}
    </div>
  );
}
