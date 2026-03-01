"use client";

import { useState, useCallback } from "react";
import { useWebSocket } from "./use-websocket";

interface Viewer {
  user_id: string;
  name: string;
  role: string;
  status: "active" | "idle";
  joined_at: number;
}

export function usePresence(caseId: string | null) {
  const [viewers, setViewers] = useState<Viewer[]>([]);
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const wsUrl = caseId
    ? `${apiBase.replace("http", "ws")}/ws/presence/${caseId}?token=${typeof window !== "undefined" ? localStorage.getItem("token") || "" : ""}`
    : "";

  const { state, send } = useWebSocket<any>({
    url: wsUrl,
    enabled: !!caseId,
    heartbeatInterval: 30000,
    onMessage: (data) => {
      if (data.type === "viewers_update") {
        setViewers(data.viewers || []);
      }
    },
    onConnect: () => {
      // Send initial heartbeat
      send({ type: "heartbeat" });
    },
  });

  const sendActivity = useCallback(() => {
    send({ type: "activity" });
  }, [send]);

  return {
    viewers,
    isConnected: state === "connected",
    sendActivity,
  };
}
