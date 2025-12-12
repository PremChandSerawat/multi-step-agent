"use client";

import { useState, useCallback, useRef } from "react";

// Types
export interface Step {
  id: string;
  phase: string;
  message: string;
  timestamp: string;
  isComplete: boolean;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps: Step[];
  isStreaming: boolean;
  currentAction?: string; // Current action being performed (shown while streaming)
  metadata?: Record<string, unknown>;
}

export type ChatStatus = "idle" | "submitted" | "streaming" | "error";

export interface UseProductionChatOptions {
  apiEndpoint?: string;
  streaming?: boolean;
  onError?: (error: Error) => void;
  onFinish?: (message: Message) => void;
}

export interface UseProductionChatReturn {
  messages: Message[];
  status: ChatStatus;
  error: Error | null;
  sendMessage: (content: string) => Promise<void>;
  stop: () => void;
  reset: () => void;
}

// Parse step from text like "[understand] Analyzed question; Will call tools"
function parseStepFromText(text: string): { phase: string; message: string } | null {
  const match = text.match(/^\[([^\]]+)\]\s*(.+)$/);
  if (match) {
    return { phase: match[1], message: match[2] };
  }
  return null;
}

// Parse tool-call event to step
function parseToolCallToStep(event: {
  toolCallId: string;
  toolName: string;
  args: { message?: string };
}): Step {
  return {
    id: event.toolCallId,
    phase: event.toolName,
    message: event.args?.message || "Processing...",
    timestamp: new Date().toISOString(),
    isComplete: true,
  };
}

// Generate unique ID
function generateId(prefix = "msg"): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

export function useProductionChat(
  options: UseProductionChatOptions = {}
): UseProductionChatReturn {
  const {
    apiEndpoint = "/api/chat",
    streaming = true,
    onError,
    onFinish,
  } = options;

  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const conversationIdRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setStatus("idle");
  }, []);

  const reset = useCallback(() => {
    stop();
    setMessages([]);
    setError(null);
    setStatus("idle");
    conversationIdRef.current = null;
  }, [stop]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      const conversationId =
        conversationIdRef.current ?? (conversationIdRef.current = generateId("thread"));

      const userMessage: Message = {
        id: generateId(),
        role: "user",
        content: content.trim(),
        steps: [],
        isStreaming: false,
      };

      const assistantMessage: Message = {
        id: generateId(),
        role: "assistant",
        content: "",
        steps: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setStatus("submitted");
      setError(null);

      // Create abort controller for this request
      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(apiEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: conversationId,
            messages: [
              ...messages.map((m) => ({
                role: m.role,
                content: m.content,
              })),
              { role: "user", content: content.trim() },
            ],
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        if (streaming && response.body) {
          setStatus("streaming");
          await handleStreamingResponse(response.body, assistantMessage.id);
        } else {
          // Non-streaming: parse JSON response
          const data = await response.json();
          const answer = data.data?.answer || data.answer || "No response received.";
          const steps = (data.timeline || []).map((t: Record<string, unknown>, i: number) => ({
            id: `step-${i}`,
            phase: t.phase as string,
            message: t.message as string,
            timestamp: t.timestamp as string,
            isComplete: true,
          }));

          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMessage.id
                ? { ...m, content: answer, steps, isStreaming: false, metadata: data }
                : m
            )
          );
          
          const finalMessage = { ...assistantMessage, content: answer, steps, isStreaming: false };
          onFinish?.(finalMessage);
        }

        setStatus("idle");
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          // Request was aborted, mark message as complete
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMessage.id
                ? { ...m, isStreaming: false, content: m.content || "Request cancelled." }
                : m
            )
          );
          setStatus("idle");
          return;
        }

        const errorObj = err instanceof Error ? err : new Error(String(err));
        setError(errorObj);
        setStatus("error");
        onError?.(errorObj);

        // Update assistant message with error
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id
              ? { ...m, content: `Error: ${errorObj.message}`, isStreaming: false }
              : m
          )
        );
      }
    },
    [apiEndpoint, streaming, messages, onError, onFinish]
  );

  // Handle SSE streaming response
  const handleStreamingResponse = useCallback(
    async (body: ReadableStream<Uint8Array>, messageId: string) => {
      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulatedContent = "";
      let accumulatedSteps: Step[] = [];
      let stepCounter = 0;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data:")) {
              const dataStr = line.slice(5).trim();
              
              if (dataStr === "[DONE]") {
                continue;
              }

              try {
                const event = JSON.parse(dataStr);
                
                // Handle tool-call events (steps)
                if (event.type === "tool-call") {
                  const step = parseToolCallToStep({
                    toolCallId: event.toolCallId || `step-${stepCounter++}`,
                    toolName: event.toolName || "processing",
                    args: event.args || {},
                  });
                  accumulatedSteps = [...accumulatedSteps, step];
                  
                  // Update message with new step
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === messageId
                        ? {
                            ...m,
                            steps: accumulatedSteps,
                            currentAction: step.message, // Track current action
                          }
                        : m
                    )
                  );
                }
                // Handle text-delta events (content)
                else if (event.type === "text-delta" && event.delta) {
                  const delta = event.delta;
                  
                  // Check if delta is a step (legacy format: starts with [phase])
                  const stepParsed = parseStepFromText(delta.trim());
                  if (stepParsed) {
                    const step: Step = {
                      id: `step-${stepCounter++}`,
                      phase: stepParsed.phase,
                      message: stepParsed.message,
                      timestamp: new Date().toISOString(),
                      isComplete: true,
                    };
                    accumulatedSteps = [...accumulatedSteps, step];
                  } else {
                    // Regular content
                    accumulatedContent += delta;
                  }

                  // Update message state
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === messageId
                        ? {
                            ...m,
                            content: accumulatedContent.trim(),
                            steps: accumulatedSteps,
                          }
                        : m
                    )
                  );
                } 
                // Handle finish event
                else if (event.type === "finish") {
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === messageId
                        ? {
                            ...m,
                            isStreaming: false,
                            metadata: event.metadata,
                            currentAction: undefined,
                          }
                        : m
                    )
                  );
                }
              } catch {
                // Ignore JSON parse errors for incomplete chunks
              }
            }
          }
        }

        // Mark streaming complete
        setMessages((prev) =>
          prev.map((m) =>
            m.id === messageId ? { ...m, isStreaming: false } : m
          )
        );

        const finalMessage = {
          id: messageId,
          role: "assistant" as const,
          content: accumulatedContent.trim(),
          steps: accumulatedSteps,
          isStreaming: false,
        };
        onFinish?.(finalMessage);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          throw err;
        }
      }
    },
    [onFinish]
  );

  return {
    messages,
    status,
    error,
    sendMessage,
    stop,
    reset,
  };
}
