import { useEffect, useRef } from "react";
import { getTokens } from "../api/client";

export type LiveMessage<T = Record<string, unknown>> = { topic: string; at: string; data: T };

export function wsUrl(path: string, params: Record<string, string>): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/v1${path}?${new URLSearchParams(params).toString()}`;
}

/** Subscribe to the authenticated live feed; reconnects with backoff while mounted. */
export function useLive(topics: string[], onMessage: (m: LiveMessage) => void): void {
  const handler = useRef(onMessage);
  handler.current = onMessage;
  const key = topics.join(",");

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry = 0;
    let closed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const token = getTokens()?.access_token;
      if (!token || closed) return;
      socket = new WebSocket(wsUrl("/ws/live", { token, topics: key }));
      socket.onopen = () => (retry = 0);
      socket.onmessage = (e) => handler.current(JSON.parse(e.data) as LiveMessage);
      socket.onclose = () => {
        if (closed) return;
        retry = Math.min(retry + 1, 5);
        timer = setTimeout(connect, 500 * 2 ** retry);
      };
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [key]);
}
