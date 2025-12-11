"use client";

import { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Chip,
  Collapse,
  InputBase,
  Typography,
  CircularProgress,
  IconButton,
} from "@mui/material";
import ReactMarkdown from "react-markdown";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import BuildIcon from "@mui/icons-material/Build";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import AddIcon from "@mui/icons-material/Add";
import SendIcon from "@mui/icons-material/Send";
import TipsAndUpdatesOutlinedIcon from "@mui/icons-material/TipsAndUpdatesOutlined";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import BuildOutlinedIcon from "@mui/icons-material/BuildOutlined";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

import { useProductionChat, Step } from "@/lib/useProductionChat";

// Step display component - collapsible
function StepItem({ step, isLast }: { step: Step; isLast: boolean }) {
  const [expanded, setExpanded] = useState(false);

  const formatPhaseName = (phase: string) => {
    return phase
      .replace(/_/g, " ")
      .replace(/([A-Z])/g, " $1")
      .trim()
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(" ");
  };

  return (
    <Box
      sx={{
        borderRadius: 2,
        border: "1px solid #27272a",
        bgcolor: "#18181b",
        overflow: "hidden",
        mb: isLast ? 0 : 1,
      }}
    >
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 1.5,
          py: 1,
          cursor: "pointer",
          "&:hover": { bgcolor: "#27272a" },
          transition: "background-color 0.15s",
        }}
      >
        {step.isComplete ? (
          <CheckCircleOutlineIcon sx={{ fontSize: 16, color: "#22c55e" }} />
        ) : (
          <CircularProgress size={16} sx={{ color: "#6b7280" }} />
        )}
        <BuildIcon sx={{ fontSize: 14, color: "#6b7280" }} />
        <Typography
          sx={{
            flex: 1,
            fontWeight: 500,
            color: "#e5e7eb",
            fontSize: 13,
          }}
        >
          {step.isComplete
            ? formatPhaseName(step.phase)
            : `Running ${formatPhaseName(step.phase)}...`}
        </Typography>
        {expanded ? (
          <ExpandLessIcon sx={{ fontSize: 18, color: "#6b7280" }} />
        ) : (
          <ExpandMoreIcon sx={{ fontSize: 18, color: "#6b7280" }} />
        )}
      </Box>
      <Collapse in={expanded}>
        <Box
          sx={{
            borderTop: "1px solid #27272a",
            px: 1.5,
            py: 1.25,
            bgcolor: "#0a0a0a",
          }}
        >
          <Typography sx={{ color: "#9ca3af", fontSize: 13 }}>
            {step.message}
          </Typography>
        </Box>
      </Collapse>
    </Box>
  );
}

// Quick suggestion chip
function SuggestionChip({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      onClick={onClick}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1,
        px: 2,
        py: 1,
        borderRadius: 999,
        border: "1px solid #3f3f46",
        bgcolor: "transparent",
        color: "#9ca3af",
        textTransform: "none",
        fontSize: 13,
        fontWeight: 400,
        "&:hover": {
          bgcolor: "#27272a",
          borderColor: "#52525b",
        },
      }}
    >
      {icon}
      {label}
    </Button>
  );
}

export default function Home() {
  const { messages, status, sendMessage, stop } = useProductionChat({
    apiEndpoint: "/api/chat",
    streaming: true,
  });

  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const isBusy = status === "submitted" || status === "streaming";
  const hasMessages = messages.length > 0;

  const handleSend = (text: string) => {
    const value = text.trim();
    if (!value || isBusy) return;
    setInput("");
    void sendMessage(value);
  };

  const suggestions = [
    {
      icon: <TipsAndUpdatesOutlinedIcon sx={{ fontSize: 16 }} />,
      label: "Find current bottleneck?",
    },
    {
      icon: <SpeedOutlinedIcon sx={{ fontSize: 16 }} />,
      label: "What's today's OEE?",
    },
    {
      icon: <BuildOutlinedIcon sx={{ fontSize: 16 }} />,
      label: "How to improve throughput?",
    },
  ];

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#0a0a0a",
        color: "#ffffff",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Top bar */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 3,
          py: 2,
        }}
      >
        <IconButton sx={{ color: "#6b7280" }}>
          <Box
            sx={{
              width: 20,
              height: 20,
              border: "1.5px solid #6b7280",
              borderRadius: 0.5,
            }}
          />
        </IconButton>
        <Button
          variant="contained"
          size="small"
          startIcon={<AutoAwesomeIcon sx={{ fontSize: 14 }} />}
          sx={{
            bgcolor: "#1f2937",
            color: "#e5e7eb",
            textTransform: "none",
            fontSize: 12,
            fontWeight: 500,
            borderRadius: 2,
            px: 2,
            "&:hover": { bgcolor: "#374151" },
          }}
        >
          Pro Mode
        </Button>
      </Box>

      {/* Main content */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: hasMessages ? "flex-start" : "center",
          px: 3,
          pb: 3,
          overflow: "hidden",
        }}
      >
        {/* Welcome screen */}
        {!hasMessages && (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              mb: 4,
            }}
          >
            <Box
              sx={{
                width: 64,
                height: 64,
                borderRadius: 3,
                bgcolor: "#1f2937",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                mb: 3,
              }}
            >
              <AutoAwesomeIcon sx={{ fontSize: 32, color: "#9ca3af" }} />
            </Box>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 500,
                color: "#ffffff",
                mb: 1,
                fontSize: { xs: 24, sm: 32 },
              }}
            >
              Good to See You!
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 500,
                color: "#ffffff",
                mb: 2,
                fontSize: { xs: 24, sm: 32 },
              }}
            >
              How Can I be an Assistance?
            </Typography>
            <Typography sx={{ color: "#6b7280", fontSize: 14 }}>
              I&apos;m available 24/7 for you, ask me anything about your
              production line.
            </Typography>
          </Box>
        )}

        {/* Chat messages */}
        {hasMessages && (
          <Box
            ref={listRef}
            sx={{
              flex: 1,
              width: "100%",
              maxWidth: 800,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 3,
              py: 2,
              mb: 2,
            }}
          >
            {messages.map((message) => {
              const isUser = message.role === "user";
              const hasSteps = message.steps.length > 0;
              const isThinking =
                message.isStreaming && !message.content && !hasSteps;
              const hasContent = message.content.trim().length > 0;

              return (
                <Box
                  key={message.id}
                  sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}
                >
                  {/* Avatar and name */}
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <Box
                      sx={{
                        width: 36,
                        height: 36,
                        borderRadius: 2,
                        bgcolor: isUser ? "#3b82f6" : "#1f2937",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#fff",
                      }}
                    >
                      {isUser ? (
                        "You"
                      ) : (
                        <AutoAwesomeIcon
                          sx={{ fontSize: 18, color: "#9ca3af" }}
                        />
                      )}
                    </Box>
                    <Typography
                      sx={{ fontWeight: 500, color: "#e5e7eb", fontSize: 14 }}
                    >
                      {isUser ? "You" : "AI Assistant"}
                    </Typography>
                    {message.isStreaming && !isUser && (
                      <Chip
                        size="small"
                        label={message.currentAction || (hasSteps ? "Processing..." : "Thinking...")}
                        sx={{
                          height: 22,
                          fontSize: 11,
                          bgcolor: "rgba(59,130,246,0.15)",
                          color: "#60a5fa",
                          border: "none",
                          maxWidth: 300,
                          "& .MuiChip-label": {
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          },
                        }}
                      />
                    )}
                  </Box>

                  {/* Message content */}
                  <Box sx={{ pl: 6.5 }}>
                    {/* User message */}
                    {isUser && (
                      <Typography
                        sx={{ color: "#d1d5db", fontSize: 14, lineHeight: 1.7 }}
                      >
                        {message.content}
                      </Typography>
                    )}

                    {/* Assistant message */}
                    {!isUser && (
                      <>
                        {/* Steps section */}
                        {hasSteps && (
                          <Box sx={{ mb: hasContent ? 2 : 0 }}>
                            <Typography
                              sx={{
                                color: "#6b7280",
                                fontWeight: 500,
                                fontSize: 12,
                                textTransform: "uppercase",
                                letterSpacing: 0.5,
                                mb: 1.5,
                              }}
                            >
                              Steps
                            </Typography>
                            {message.steps.map((step, idx) => (
                              <StepItem
                                key={step.id}
                                step={step}
                                isLast={idx === message.steps.length - 1}
                              />
                            ))}
                          </Box>
                        )}

                        {/* Response content */}
                        {hasContent && (
                          <Box>
                            {hasSteps && (
                              <Typography
                                sx={{
                                  color: "#6b7280",
                                  fontWeight: 500,
                                  fontSize: 12,
                                  textTransform: "uppercase",
                                  letterSpacing: 0.5,
                                  mb: 1.5,
                                }}
                              >
                                Response
                              </Typography>
                            )}
                            <Typography
                              component="div"
                              sx={{
                                color: "#d1d5db",
                                fontSize: 14,
                                lineHeight: 1.8,
                                "& p": { margin: 0, mb: 1.5 },
                                "& p:last-child": { mb: 0 },
                                "& ul, & ol": {
                                  pl: 2.5,
                                  mb: 1.5,
                                  "& li": { mb: 0.75 },
                                },
                                "& strong": { fontWeight: 600, color: "#f3f4f6" },
                                "& code": {
                                  bgcolor: "#1f2937",
                                  px: 0.75,
                                  py: 0.25,
                                  borderRadius: 0.5,
                                  fontSize: "0.9em",
                                  fontFamily: "monospace",
                                  color: "#a5f3fc",
                                },
                                "& h1, & h2, & h3, & h4": {
                                  color: "#f9fafb",
                                  fontWeight: 600,
                                  mt: 2,
                                  mb: 1,
                                },
                              }}
                            >
                              <ReactMarkdown>{message.content}</ReactMarkdown>
                            </Typography>
                          </Box>
                        )}

                        {/* Thinking indicator */}
                        {isThinking && (
                          <Box
                            sx={{ display: "flex", alignItems: "center", gap: 1 }}
                          >
                            <CircularProgress
                              size={14}
                              sx={{ color: "#6b7280" }}
                            />
                            <Typography sx={{ color: "#6b7280", fontSize: 13 }}>
                              Thinking...
                            </Typography>
                          </Box>
                        )}
                      </>
                    )}
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}

        {/* Input area */}
        <Box
          sx={{
            width: "100%",
            maxWidth: 600,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          {/* Feature bar - only on welcome screen */}
          {!hasMessages && (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                px: 1,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <AutoAwesomeIcon sx={{ fontSize: 14, color: "#9ca3af" }} />
                <Typography sx={{ color: "#9ca3af", fontSize: 13 }}>
                  Production AI Copilot - Powered by LangGraph
                </Typography>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                <FiberManualRecordIcon sx={{ fontSize: 8, color: "#22c55e" }} />
                <Typography sx={{ color: "#22c55e", fontSize: 12 }}>
                  Active
                </Typography>
              </Box>
            </Box>
          )}

          {/* Input field */}
          <Box
            component="form"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              bgcolor: "#18181b",
              borderRadius: 999,
              border: "1px solid #27272a",
              px: 1,
              py: 0.5,
            }}
          >
            <IconButton sx={{ color: "#6b7280" }}>
              <AddIcon sx={{ fontSize: 20 }} />
            </IconButton>
            <InputBase
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything ..."
              disabled={isBusy}
              sx={{
                flex: 1,
                color: "#e5e7eb",
                fontSize: 14,
                "& .MuiInputBase-input": {
                  p: 0.75,
                  "&::placeholder": { color: "#6b7280", opacity: 1 },
                },
              }}
            />
            <IconButton
              type="submit"
              disabled={isBusy || !input.trim()}
              sx={{ color: input.trim() ? "#e5e7eb" : "#4b5563" }}
            >
              {isBusy ? (
                <CircularProgress size={20} sx={{ color: "#6b7280" }} />
              ) : (
                <SendIcon sx={{ fontSize: 20 }} />
              )}
            </IconButton>
          </Box>

          {/* Suggestion chips - only on welcome screen */}
          {!hasMessages && (
            <Box
              sx={{
                display: "flex",
                flexWrap: "wrap",
                gap: 1,
                justifyContent: "center",
              }}
            >
              {suggestions.map((s, idx) => (
                <SuggestionChip
                  key={idx}
                  icon={s.icon}
                  label={s.label}
                  onClick={() => handleSend(s.label)}
                />
              ))}
            </Box>
          )}

          {/* Processing indicator */}
          {isBusy && (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 2,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <CircularProgress size={12} sx={{ color: "#6b7280" }} />
                <Typography sx={{ color: "#6b7280", fontSize: 12 }}>
                  Processing your request...
                </Typography>
              </Box>
              <Button
                onClick={stop}
                sx={{
                  textTransform: "none",
                  fontSize: 12,
                  color: "#ef4444",
                  minWidth: "auto",
                  px: 1.5,
                  "&:hover": { bgcolor: "rgba(239,68,68,0.1)" },
                }}
              >
                Stop
              </Button>
            </Box>
          )}
        </Box>
      </Box>

      {/* Footer */}
      <Box sx={{ textAlign: "center", py: 2, color: "#6b7280", fontSize: 12 }}>
        Production AI Copilot powered by LangGraph & OpenAI
      </Box>
    </Box>
  );
}
