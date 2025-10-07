import { useCallback, useEffect, useRef, useState } from "react";

const RECONNECT_MS = 2000;

export function socketUrl(location = window.location) {
  return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/boss/`;
}

// Live server state over the boss WebSocket. The server pushes a full snapshot on every change.
export function useServerState(token, { onAuthFailed, WebSocketImpl = globalThis.WebSocket } = {}) {
  const [state, setState] = useState({ clients: [], session: null });
  const [online, setOnline] = useState(false);
  const [notice, setNotice] = useState("");
  const socketRef = useRef(null);
  const authFailed = useRef(onAuthFailed);
  authFailed.current = onAuthFailed;

  useEffect(() => {
    let stopped = false;
    let retry = null;

    function open() {
      const socket = new WebSocketImpl(socketUrl());
      socketRef.current = socket;
      socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "auth_ok") {
          setOnline(true);
        } else if (message.type === "auth_failed") {
          stopped = true;
          authFailed.current?.();
        } else if (message.type === "state") {
          setState({ clients: message.clients, session: message.session });
        } else if (message.type === "error") {
          setNotice(message.message);
        }
      };
      socket.onclose = () => {
        setOnline(false);
        if (!stopped) retry = setTimeout(open, RECONNECT_MS);
      };
    }

    open();
    return () => {
      stopped = true;
      clearTimeout(retry);
      socketRef.current?.close();
    };
  }, [token, WebSocketImpl]);

  const send = useCallback((message) => {
    setNotice("");
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocketImpl.OPEN) {
      socket.send(JSON.stringify(message));
    } else {
      setNotice("Not connected to the server. Try again in a moment.");
    }
  }, [WebSocketImpl]);

  return { ...state, online, notice, setNotice, send };
}
