import React from "react";
import {
  Box,
  CircularProgress,
  IconButton,
  InputBase,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SendIcon from "@mui/icons-material/Send";

import { SuggestionChip } from "./SuggestionChip";

interface Suggestion {
  icon: React.ReactNode;
  label: string;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  isBusy: boolean;
  hasMessages: boolean;
  suggestions: Suggestion[];
}

export function ChatInput({
  value,
  onChange,
  onSend,
  isBusy,
  hasMessages,
  suggestions,
}: ChatInputProps) {
  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSend(value);
  };

  return (
    <Box
      sx={{
        width: "100%",
        maxWidth: 600,
        display: "flex",
        flexDirection: "column",
        gap: 2,
        mt: hasMessages ? "auto" : 0,
        position: hasMessages ? "sticky" : "static",
        bottom: 0,
        bgcolor: "background.default",
        pt: hasMessages ? 1.5 : 0,
        pb: 1.5,
        borderTop: hasMessages ? "1px solid" : "none",
        borderColor: "divider",
        boxShadow: hasMessages ? "0 -8px 24px rgba(0, 0, 0, 0.15)" : "none",
      }}
    >
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          bgcolor: "background.paper",
          borderRadius: 999,
          border: "1px solid",
          borderColor: "divider",
          px: 1,
          py: 0.5,
        }}
      >
        <IconButton sx={{ color: "text.secondary" }}>
          <AddIcon sx={{ fontSize: 20 }} />
        </IconButton>
        <InputBase
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ask anything ..."
          disabled={isBusy}
          sx={{
            flex: 1,
            color: "text.primary",
            fontSize: 14,
            "& .MuiInputBase-input": {
              p: 0.75,
              "&::placeholder": { color: "text.secondary", opacity: 1 },
            },
          }}
        />
        <IconButton
          type="submit"
          disabled={isBusy || !value.trim()}
          sx={{ color: value.trim() ? "text.primary" : "text.disabled" }}
        >
          {isBusy ? (
            <CircularProgress size={20} sx={{ color: "text.secondary" }} />
          ) : (
            <SendIcon sx={{ fontSize: 20 }} />
          )}
        </IconButton>
      </Box>

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
              onClick={() => onSend(s.label)}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}

