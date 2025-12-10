const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type StreamEvent =
  | { type: "step"; node?: string; state: Record<string, unknown> }
  | { type: "final"; result: Record<string, unknown> };

export async function runQuery(question: string) {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json();
}

export function streamAgent(question: string, onEvent: (event: StreamEvent) => void) {
  const source = new EventSource(
    `${API_BASE}/stream?question=${encodeURIComponent(question)}`
  );

  source.onmessage = (evt) => {
    try {
      const parsed = JSON.parse(evt.data);
      onEvent(parsed as StreamEvent);
    } catch (err) {
      console.error("Failed to parse SSE message", err);
    }
  };

  source.onerror = (err) => {
    console.error("SSE error", err);
    source.close();
  };

  return () => source.close();
}

