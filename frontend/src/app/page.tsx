"use client";

import { useEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import TipsAndUpdatesOutlinedIcon from "@mui/icons-material/TipsAndUpdatesOutlined";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import BuildOutlinedIcon from "@mui/icons-material/BuildOutlined";

import { useProductionChat } from "@/lib/useProductionChat";
import { TopBar } from "@/components/TopBar";
import { Welcome } from "@/components/Welcome";
import { MessageList } from "@/components/MessageList";
import { ChatInput } from "@/components/ChatInput";

export default function Home() {
  const { messages, status, sendMessage } = useProductionChat({
    apiEndpoint: "/api/chat",
    streaming: true,
  });

  const [input, setInput] = useState("");
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const prevMessageCountRef = useRef(0);

  // Scroll only when a new message is added (not on streaming chunks)
  useEffect(() => {
    const list = scrollContainerRef.current;
    const prevCount = prevMessageCountRef.current;
    const currCount = messages.length;

    if (list && currCount > prevCount) {
      list.scrollTop = list.scrollHeight;
    }

    prevMessageCountRef.current = currCount;
  }, [messages.length]);

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
      position="relative"
      sx={{
        minHeight: "100vh",
        bgcolor: "background.default",
        color: "text.primary",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <TopBar />

      <Box
        ref={scrollContainerRef}
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: hasMessages ? "flex-start" : "center",
          px: 3,
          pb: 3,
          overflow: "hidden",
          maxHeight: "calc(100vh - 100px)",
          overflowY: "auto",
        }}
      >
        {!hasMessages && <Welcome />}
        {hasMessages && <MessageList messages={messages} />}

        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          isBusy={isBusy}
          hasMessages={hasMessages}
          suggestions={suggestions}
        />
      </Box>
    </Box>
  );
}
