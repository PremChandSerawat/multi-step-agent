import { Box, Button, IconButton, Tooltip, useTheme } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import { useColorMode } from "@/theme/ThemeProvider";

export function TopBar() {
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
      <Button
        variant="outlined"
        size="small"
        startIcon={<AutoAwesomeIcon sx={{ fontSize: 14 }} />}
        sx={{
          textTransform: "none",
          fontSize: 12,
          fontWeight: 600,
          borderRadius: 2,
          px: 2,
        }}
      >
        Pro Mode
      </Button>
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

