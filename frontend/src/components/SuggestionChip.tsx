import { Button } from "@mui/material";
import React from "react";

interface SuggestionChipProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}

export function SuggestionChip({ icon, label, onClick }: SuggestionChipProps) {
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
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "background.paper",
        color: "text.secondary",
        textTransform: "none",
        fontSize: 13,
        fontWeight: 500,
        "&:hover": {
          bgcolor: "action.hover",
        },
      }}
    >
      {icon}
      {label}
    </Button>
  );
}

