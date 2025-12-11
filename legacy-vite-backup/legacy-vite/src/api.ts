const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export type TimelineEntry = {
  phase?: string;
  message: string;
  timestamp?: string;
  data_keys?: string[];
};

export type StreamEvent =
  | {
      type: "step";
      node?: string;
      phase?: string;
      state: {
        steps?: string[];
        data?: Record<string, unknown>;
        timeline?: TimelineEntry[];
      };
    }
  | { type: "final"; result: Record<string, unknown> };

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



