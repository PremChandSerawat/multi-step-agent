import { Box, Chip, Typography } from "@mui/material";
import { keyframes } from "@emotion/react";
import { alpha, useTheme } from "@mui/material/styles";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import BuildIcon from "@mui/icons-material/Build";

import { Step } from "@/lib/useProductionChat";

export function formatPhaseName(phase: string) {
  return phase
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .trim()
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

const pulse = keyframes`
  0% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.25); opacity: 1; }
  100% { transform: scale(1); opacity: 0.8; }
`;

const dotBlink = keyframes`
  0%, 20% { transform: translateY(0); opacity: 0.4; }
  50% { transform: translateY(-2px); opacity: 1; }
  80%, 100% { transform: translateY(0); opacity: 0.4; }
`;

export function DotPulse() {
  return (
    <Box sx={{ display: "inline-flex", gap: 0.4 }}>
      {[0, 1, 2].map((i) => (
        <Box
          key={i}
          component="span"
          sx={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            bgcolor: "currentColor",
            animation: `${dotBlink} 1.4s ease-in-out infinite`,
            animationDelay: `${i * 0.15}s`,
          }}
        />
      ))}
    </Box>
  );
}

interface StepItemProps {
  step: Step;
  isLast: boolean;
  isActive?: boolean;
}

export function StepItem({ step, isLast, isActive = false }: StepItemProps) {
  const theme = useTheme();
  const statusColor = step.isComplete && !isActive
    ? theme.palette.success.main
    : theme.palette.warning.main;

  return (
    <Box
      sx={{
        borderRadius: 2,
        border: "1px solid",
        borderColor: isActive ? alpha(theme.palette.primary.main, 0.3) : "divider",
        bgcolor: isActive
          ? alpha(theme.palette.primary.main, theme.palette.mode === "dark" ? 0.15 : 0.08)
          : "background.paper",
        overflow: "hidden",
        mb: isLast ? 0 : 1,
        px: 1.5,
        py: 1.25,
        position: "relative",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1.5,
          mb: 0.5,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              bgcolor: statusColor,
              boxShadow: `0 0 0 4px ${alpha(statusColor, 0.15)}`,
              animation: isActive ? `${pulse} 1.6s ease-in-out infinite` : "none",
              flexShrink: 0,
            }}
          />
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            <BuildIcon sx={{ fontSize: 14, color: "text.secondary" }} />
            <Typography
              sx={{
                fontWeight: 600,
                color: "text.primary",
                fontSize: 13,
                letterSpacing: 0.2,
              }}
            >
              {formatPhaseName(step.phase)}
            </Typography>
          </Box>
        </Box>

        <Chip
          size="small"
          label={
            isActive ? (
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.35 }}>
                  Processing <DotPulse />
                </Box>
              </Box>
            ) : (
              "Completed"
            )
          }
          icon={!isActive ? <CheckCircleOutlineIcon sx={{ fontSize: 16 }} /> : undefined}
          sx={{
            height: 24,
            fontSize: 11,
            bgcolor: isActive
              ? alpha(theme.palette.warning.main, 0.15)
              : alpha(theme.palette.success.main, 0.15),
            color: isActive ? theme.palette.warning.dark : theme.palette.success.dark,
            "& .MuiChip-icon": { ml: 0.5 },
          }}
        />
      </Box>

      <Typography sx={{ color: "text.secondary", fontSize: 13, lineHeight: 1.6 }}>
        {step.message}
      </Typography>
    </Box>
  );
}

