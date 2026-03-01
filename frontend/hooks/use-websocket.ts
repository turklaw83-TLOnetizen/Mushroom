"use client";

import { useEffect, useRef, useState, useCallback } from "react";

type ConnectionState = "connecting" | "connected" | "disconnected" | "reconnecting";

interface UseWebSocketOptions {
  url: string;
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  heartbeatInterval?: number;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
  enabled?: boolean;
}

export function useWebSocket<T = any>({
  url,
  onMessage,
  onConnect,
  onDisconnect,
  heartbeatInterval = 25000,
  maxReconnectAttempts = 5,
  reconnectDelay = 2000,
  enabled = true,
}: UseWebSocketOptions) {
  const [state, setState] = useState<ConnectionState>("disconnected");
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const intentionalClose = useRef(false);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval>>();
  const messageQueue = useRef<any[]>([]);

  const connect = useCallback(() => {
    if (!enabled || !url) return;

    setState("connecting");
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setState("connected");
      reconnectCount.current = 0;
      onConnect?.();

      // Start heartbeat
      heartbeatTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ping" }));
        }
      }, heartbeatInterval);

      // Send queued messages
      while (messageQueue.current.length > 0) {
        const msg = messageQueue.current.shift();
        ws.send(JSON.stringify(msg));
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "pong") return; // Heartbeat response
        setLastMessage(data as T);
        onMessage?.(data);
      } catch {
        // Non-JSON message
      }
    };

    ws.onclose = () => {
      clearInterval(heartbeatTimer.current);

      if (intentionalClose.current) {
        setState("disconnected");
        onDisconnect?.();
        return;
      }

      if (reconnectCount.current < maxReconnectAttempts) {
        setState("reconnecting");
        reconnectCount.current++;
        setTimeout(connect, reconnectDelay * reconnectCount.current);
      } else {
        setState("disconnected");
        onDisconnect?.();
      }
    };

    ws.onerror = () => {
      // onclose will fire after onerror
    };
  }, [url, enabled, onMessage, onConnect, onDisconnect, heartbeatInterval, maxReconnectAttempts, reconnectDelay]);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    wsRef.current?.close();
    wsRef.current = null;
    clearInterval(heartbeatTimer.current);
  }, []);

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      messageQueue.current.push(data);
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      intentionalClose.current = false;
      connect();
    }
    return () => {
      disconnect();
    };
  }, [enabled, url]);

  return { state, lastMessage, send, disconnect, reconnect: connect };
}
