 "use client";

import {
  CssBaseline,
  PaletteMode,
  ThemeProvider as MuiThemeProvider,
  createTheme,
} from "@mui/material";
import {
  PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type ColorModeContextValue = {
  mode: PaletteMode;
  toggle: () => void;
};

const ColorModeContext = createContext<ColorModeContextValue>({
  mode: "dark",
  toggle: () => {},
});

const STORAGE_KEY = "color-mode";

function buildTheme(mode: PaletteMode) {
  const isDark = mode === "dark";

  return createTheme({
    palette: {
      mode,
      primary: {
        main: isDark ? "#60a5fa" : "#2563eb",
      },
      background: {
        default: isDark ? "#0a0a0a" : "#f7f9fc",
        paper: isDark ? "#111827" : "#ffffff",
      },
      text: {
        primary: isDark ? "#e5e7eb" : "#111827",
        secondary: isDark ? "#9ca3af" : "#4b5563",
      },
      divider: isDark ? "#27272a" : "#e5e7eb",
    },
    shape: {
      borderRadius: 12,
    },
    typography: {
      fontFamily: "var(--font-geist-sans), system-ui, -apple-system, sans-serif",
      h4: { fontWeight: 600 },
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
            borderRadius: 12,
            boxShadow: "none",
          },
          contained: {
            boxShadow: "none",
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 10,
          },
        },
      },
      MuiInputBase: {
        styleOverrides: {
          root: {
            fontSize: 14,
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: 10,
          },
        },
      },
    },
    mixins: {
      toolbar: {
        minHeight: 64,
      },
    },
  });
}

export function useColorMode() {
  return useContext(ColorModeContext);
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [mode, setMode] = useState<PaletteMode>("dark");

  useEffect(() => {
    const stored =
      typeof window !== "undefined"
        ? (localStorage.getItem(STORAGE_KEY) as PaletteMode | null)
        : null;
    if (stored === "light" || stored === "dark") {
      setMode(stored);
      return;
    }

    if (typeof window !== "undefined") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)")
        .matches;
      setMode(prefersDark ? "dark" : "light");
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, mode);
    }
  }, [mode]);

  const toggle = useCallback(
    () => setMode((prev) => (prev === "dark" ? "light" : "dark")),
    []
  );

  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ColorModeContext.Provider value={{ mode, toggle }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ColorModeContext.Provider>
  );
}

