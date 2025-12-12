import { Box, Typography } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";

export function Welcome() {
  return (
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
          bgcolor: "background.paper",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          mb: 3,
        }}
      >
        <AutoAwesomeIcon sx={{ fontSize: 32, color: "text.secondary" }} />
      </Box>
      <Typography
        variant="h4"
        sx={{
          fontWeight: 500,
          color: "text.primary",
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
          color: "text.primary",
          mb: 2,
          fontSize: { xs: 24, sm: 32 },
        }}
      >
        How Can I be an Assistance?
      </Typography>
      <Typography sx={{ color: "text.secondary", fontSize: 14 }}>
        I&apos;m available 24/7 for you, ask me anything about your production
        line.
      </Typography>
    </Box>
  );
}

