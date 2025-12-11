"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Chat, useChat } from "@ai-sdk/react";
import {
  Box,
  Button,
  Chip,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ReactMarkdown from "react-markdown";

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function Home() {
  const chat = useMemo(
    () =>
      new Chat({
        // Not typed in this package, but supported at runtime.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        api: "/api/chat",
      } as any),
    [],
  );

  const { messages, sendMessage, status, stop } = useChat({
    chat,
  });
  const [input, setInput] = useState("");

  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const renderText = (msg: (typeof messages)[number]) => {
    if (msg.parts?.length) {
      return msg.parts
        .map((part) => (part.type === "text" ? part.text ?? "" : ""))
        .join("");
    }
    if ("content" in msg && typeof msg.content === "string") return msg.content;
    return "";
  };

  const isBusy = status === "submitted" || status === "streaming";

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        color: "text.primary",
        display: "flex",
        justifyContent: "center",
        px: { xs: 2, sm: 3 },
        py: { xs: 3, sm: 4 },
      }}
    >
      <Stack spacing={2} sx={{ width: "min(1080px, 100%)" }}>
        <Paper
          elevation={4}
          sx={{
            p: 2.5,
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 2,
          }}
        >
          <Box>
            <Typography variant="h5" fontWeight={700}>
              Production AI Copilot
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              LangGraph + OpenAI + Vercel AI SDK. Ask about throughput, OEE, or
              bottlenecks; reasoning streams live.
            </Typography>
          </Box>
          <Chip label="Streaming" color="primary" variant="outlined" />
        </Paper>

        <Paper
          elevation={6}
          sx={{
            display: "flex",
            flexDirection: "column",
            height: { xs: "70vh", md: "72vh" },
            overflow: "hidden",
          }}
        >
          <Box
            ref={listRef}
            sx={{
              flex: 1,
              overflowY: "auto",
              p: 2,
              display: "flex",
              flexDirection: "column",
              gap: 1.5,
              bgcolor: "background.paper",
            }}
          >
            {messages.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                Try: "Where is the current bottleneck and how can we improve
                OEE?"
              </Typography>
            )}

            {messages.map((message) => {
              const text = renderText(message);
              const isUser = message.role === "user";
              return (
                <Stack
                  key={message.id}
                  alignItems={isUser ? "flex-end" : "flex-start"}
                  spacing={0.5}
                >
                  <Typography variant="caption" color="text.secondary">
                    {isUser ? "You" : "Assistant"}
                  </Typography>
                  <Paper
                    variant="outlined"
                    sx={{
                      maxWidth: "80%",
                      bgcolor: isUser ? "primary.main" : "background.default",
                      color: isUser ? "primary.contrastText" : "text.primary",
                      px: 2,
                      py: 1.5,
                    }}
                  >
                    <Typography
                      variant="body2"
                      component="div"
                      sx={{
                        whiteSpace: "normal",
                        "& p": { margin: 0 },
                      }}
                    >
                      <ReactMarkdown>{text || "…"}</ReactMarkdown>
                    </Typography>
                  </Paper>
                </Stack>
              );
            })}
          </Box>

          <Divider />

          <Box
            component="form"
            onSubmit={(event) => {
              event.preventDefault();
              const value = input.trim();
              if (!value) return;
              setInput("");
              void sendMessage({ role: "user", content: value } as any);
            }}
            sx={{
              display: "flex",
              gap: 1,
              p: 1.5,
              alignItems: "center",
            }}
          >
            <TextField
              name="input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about throughput, downtime, or maintenance…"
              fullWidth
              size="small"
              disabled={isBusy}
            />
            <Button
              type="submit"
              variant="contained"
              disableElevation
              disabled={isBusy}
            >
              {isBusy ? "Sending..." : "Send"}
            </Button>
          </Box>

          {isBusy && (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                px: 2,
                pb: 1.5,
                gap: 2,
              }}
            >
              <Typography variant="body2" color="text.secondary">
                Streaming analysis from LangGraph agent…
              </Typography>
              <Button variant="outlined" size="small" onClick={stop}>
                Stop
              </Button>
            </Box>
          )}
        </Paper>
      </Stack>
    </Box>
  );
}
