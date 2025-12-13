import { Box, Button, IconButton, Tooltip, useTheme } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import StreamIcon from "@mui/icons-material/Stream";
import SyncIcon from "@mui/icons-material/Sync";
import { useColorMode } from "@/theme/ThemeProvider";

interface TopBarProps {
  syncMode?: boolean;
  onSyncModeToggle?: () => void;
}

export function TopBar({ syncMode = false, onSyncModeToggle }: TopBarProps) {
  const theme = useTheme();
  const { mode, toggle } = useColorMode();

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        px: 3,
        py: 2,
        borderBottom: 1,
        borderColor: "divider",
      }}
    >
      <IconButton sx={{ color: "text.secondary" }}>
        <Box
          sx={{
            width: 20,
            height: 20,
            border: "1.5px solid",
            borderColor: "text.secondary",
            borderRadius: 0.5,
          }}
        />
      </IconButton>
      
      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <Tooltip title={syncMode ? "Switch to streaming mode" : "Switch to sync mode"}>
          <Button
            variant={syncMode ? "contained" : "outlined"}
            size="small"
            onClick={onSyncModeToggle}
            startIcon={syncMode ? <SyncIcon sx={{ fontSize: 14 }} /> : <StreamIcon sx={{ fontSize: 14 }} />}
            sx={{
              textTransform: "none",
              fontSize: 12,
              fontWeight: 600,
              borderRadius: 2,
              px: 2,
              bgcolor: syncMode ? "primary.main" : "transparent",
              color: syncMode ? "primary.contrastText" : "text.primary",
              borderColor: syncMode ? "primary.main" : "divider",
              "&:hover": {
                bgcolor: syncMode ? "primary.dark" : theme.palette.action.hover,
              },
            }}
          >
            {syncMode ? "Sync" : "Stream"}
          </Button>
        </Tooltip>
      </Box>
      
      <Tooltip
        title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        <IconButton
          onClick={toggle}
          sx={{
            color: "text.secondary",
            bgcolor: theme.palette.action.hover,
            "&:hover": { bgcolor: theme.palette.action.selected },
          }}
        >
          {mode === "dark" ? (
            <LightModeIcon sx={{ fontSize: 18 }} />
          ) : (
            <DarkModeIcon sx={{ fontSize: 18 }} />
          )}
        </IconButton>
      </Tooltip>
    </Box>
  );
}

