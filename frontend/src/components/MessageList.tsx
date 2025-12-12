import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  Typography,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";

import ReactMarkdown from "react-markdown";

import { Message } from "@/lib/useProductionChat";
import { StepItem, DotPulse, formatPhaseName } from "./StepItem";

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const theme = useTheme();
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const prevLengthRef = useRef(0);
  const [stepsOpen, setStepsOpen] = useState<Record<string, boolean>>({});

  // Scroll to bottom only when a new message is added
  useEffect(() => {
    if (messages.length > prevLengthRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }
    prevLengthRef.current = messages.length;
  }, [messages.length]);

  return (
    <Box
      sx={{
        flex: 1,
        width: "100%",
        maxWidth: 800,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 3,
        py: 2,
        pr: 4,
      }}
    >
      {messages.map((message) => {
        const isUser = message.role === "user";
        const hasSteps = message.steps.length > 0;
        const isThinking =
          message.isStreaming && !message.content && !hasSteps;
        const hasContent = message.content.trim().length > 0;
        const activeStepIndex = message.steps.length - 1;
        const activeStep =
          activeStepIndex >= 0 ? message.steps[activeStepIndex] : undefined;

        return (
          <Box
            key={message.id}
            sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <Box
                sx={{
                  width: 36,
                  height: 36,
                  borderRadius: 2,
                  bgcolor: isUser ? "primary.main" : "background.paper",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 12,
                  fontWeight: 600,
                  color: isUser
                    ? theme.palette.getContrastText(theme.palette.primary.main)
                    : "text.secondary",
                }}
              >
                {isUser ? (
                  "You"
                ) : (
                  <AutoAwesomeIcon
                    sx={{ fontSize: 18, color: "text.secondary" }}
                  />
                )}
              </Box>
              <Typography
                sx={{ fontWeight: 500, color: "text.primary", fontSize: 14 }}
              >
                {isUser ? "You" : "AI Assistant"}
              </Typography>
              {message.isStreaming && !isUser && (
                <Chip
                  size="small"
                  label={
                    message.currentAction ||
                    (hasSteps ? "Processing..." : "Thinking...")
                  }
                  sx={{
                    height: 22,
                    fontSize: 11,
                    bgcolor: alpha(theme.palette.primary.main, 0.15),
                    color: "primary.main",
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

            <Box sx={{ pl: 6.5 }}>
              {isUser && (
                <Typography
                  sx={{ color: "text.primary", fontSize: 14, lineHeight: 1.7 }}
                >
                  {message.content}
                </Typography>
              )}

              {!isUser && (
                <>
                  {hasSteps && (
                    <Box
                      sx={{
                        mb: hasContent ? 2 : 0,
                        borderRadius: 2,
                        border: "1px solid",
                        borderColor: alpha(theme.palette.primary.main, 0.15),
                        bgcolor: alpha(
                          theme.palette.primary.main,
                          theme.palette.mode === "dark" ? 0.06 : 0.08
                        ),
                        p: 1.25,
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          justifyContent: "space-between",
                        }}
                      >
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <Typography
                            sx={{
                              color: "text.primary",
                              fontWeight: 600,
                              fontSize: 13,
                              letterSpacing: 0.4,
                            }}
                          >
                            Steps ({message.steps.length})
                          </Typography>
                          {activeStep && (
                            <Typography
                              sx={{
                                color: "text.secondary",
                                fontSize: 12,
                                display: "flex",
                                alignItems: "center",
                                gap: 0.6,
                              }}
                            >
                              {message.isStreaming ? (
                                <>
                                  {formatPhaseName(activeStep.phase)}
                                  <DotPulse />
                                </>
                              ) : (
                                formatPhaseName(activeStep.phase)
                              )}
                            </Typography>
                          )}
                        </Box>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setStepsOpen((prev) => ({
                              ...prev,
                              [message.id]: !(prev[message.id] ?? false),
                            }))
                          }
                          sx={{ color: "text.secondary" }}
                        >
                          {(stepsOpen[message.id] ?? false) ? (
                            <ExpandLessIcon sx={{ fontSize: 18 }} />
                          ) : (
                            <ExpandMoreIcon sx={{ fontSize: 18 }} />
                          )}
                        </IconButton>
                      </Box>

                      <Collapse in={stepsOpen[message.id] ?? false} timeout="auto" unmountOnExit>
                        {message.isStreaming && activeStep && (
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "center",
                              gap: 1,
                              px: 1.25,
                              py: 1,
                              mt: 1,
                              mb: 1,
                              borderRadius: 1.5,
                              border: "1px dashed",
                              borderColor: alpha(theme.palette.primary.main, 0.4),
                              bgcolor: alpha(
                                theme.palette.primary.main,
                                theme.palette.mode === "dark" ? 0.08 : 0.12
                              ),
                            }}
                          >
                            <Typography
                              sx={{
                                color: "text.primary",
                                fontWeight: 600,
                                fontSize: 13,
                              }}
                            >
                              {formatPhaseName(activeStep.phase)}
                            </Typography>
                            <DotPulse />
                            <Typography
                              sx={{
                                color: "text.secondary",
                                fontSize: 13,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                flex: 1,
                              }}
                            >
                              {message.currentAction || activeStep.message}
                            </Typography>
                          </Box>
                        )}

                        {message.steps.map((step, idx) => (
                          <StepItem
                            key={step.id}
                            step={step}
                            isLast={idx === message.steps.length - 1}
                            isActive={message.isStreaming && idx === activeStepIndex}
                          />
                        ))}
                      </Collapse>
                    </Box>
                  )}

                  {hasContent && (
                    <Box>
                      {hasSteps && (
                        <Typography
                          sx={{
                            color: "text.secondary",
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
                          color: "text.primary",
                          fontSize: 14,
                          lineHeight: 1.8,
                          "& p": { margin: 0, mb: 1.5 },
                          "& p:last-child": { mb: 0 },
                          "& ul, & ol": {
                            pl: 2.5,
                            mb: 1.5,
                            "& li": { mb: 0.75 },
                          },
                          "& strong": {
                            fontWeight: 600,
                            color: "text.primary",
                          },
                          "& code": {
                            bgcolor: theme.palette.mode === "dark"
                              ? alpha(theme.palette.background.paper, 0.8)
                              : alpha(theme.palette.primary.main, 0.08),
                            px: 0.75,
                            py: 0.25,
                            borderRadius: 0.5,
                            fontSize: "0.9em",
                            fontFamily: "monospace",
                            color:
                              theme.palette.mode === "dark"
                                ? "#a5f3fc"
                                : theme.palette.primary.dark,
                          },
                          "& h1, & h2, & h3, & h4": {
                            color: "text.primary",
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

                  {isThinking && (
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                      }}
                    >
                      <CircularProgress
                        size={14}
                        sx={{ color: "text.secondary" }}
                      />
                      <Typography sx={{ color: "text.secondary", fontSize: 13 }}>
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
      <Box sx={{ pb: "calc(50vh)" }} ref={bottomRef} />
    </Box>
  );
}

