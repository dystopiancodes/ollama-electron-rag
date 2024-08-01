import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Container from "@mui/material/Container";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import CircularProgress from "@mui/material/CircularProgress";
import Snackbar from "@mui/material/Snackbar";
import Alert from "@mui/material/Alert";
import IconButton from "@mui/material/IconButton";
import SettingsIcon from "@mui/icons-material/Settings";
import CodeIcon from "@mui/icons-material/Code";

import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import LinearProgress from "@mui/material/LinearProgress";
import Drawer from "@mui/material/Drawer";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1976d2",
    },
  },
});

function App() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "info",
  });
  const [configOpen, setConfigOpen] = useState(false);
  const [promptTemplate, setPromptTemplate] = useState("");
  const answerRef = useRef(null);
  const [isResetting, setIsResetting] = useState(false);
  const [resetProgress, setResetProgress] = useState({
    progress: 0,
    current: 0,
    total: 0,
  });
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugInfo, setDebugInfo] = useState("");

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await fetch("http://localhost:8000/config");
      const data = await response.json();
      setPromptTemplate(data.prompt_template);
    } catch (error) {
      console.error("Error fetching config:", error);
      setSnackbar({
        open: true,
        message: "Error fetching configuration",
        severity: "error",
      });
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setAnswer("");
    setSources([]);
    setDebugInfo("");

    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: query }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        lines.forEach((line) => {
          if (line) {
            try {
              const data = JSON.parse(line);
              if (data.answer) {
                setAnswer((prev) => prev + data.answer);
              }
              if (data.sources) {
                setSources(data.sources);
              }
              if (data.debug) {
                setDebugInfo((prev) => prev + data.debug + "\n");
              }
            } catch (error) {
              console.error("Error parsing JSON:", error);
            }
          }
        });
      }
    } catch (error) {
      console.error("Error querying documents:", error);
      setSnackbar({
        open: true,
        message: "Error querying documents",
        severity: "error",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSourceClick = (filename) => {
    console.log("Attempting to open file:", filename);
    if (window.electron && window.electron.openFile) {
      window.electron
        .openFile(filename)
        .then((result) => {
          console.log("File open result:", result);
          setSnackbar({
            open: true,
            message: result.message,
            severity: result.success ? "success" : "error",
          });
        })
        .catch((error) => {
          console.error("Error opening file:", error);
          setSnackbar({
            open: true,
            message: `Error opening file: ${error.message}`,
            severity: "error",
          });
        });
    } else {
      console.error("Electron API not available");
      setSnackbar({
        open: true,
        message: "Electron API not available",
        severity: "error",
      });
    }
  };

  const handleCloseSnackbar = (event, reason) => {
    if (reason === "clickaway") {
      return;
    }
    setSnackbar({ ...snackbar, open: false });
  };

  const handleConfigOpen = () => {
    setConfigOpen(true);
  };

  const handleConfigClose = () => {
    setConfigOpen(false);
  };

  const handleConfigSave = async () => {
    try {
      const response = await fetch("http://localhost:8000/config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ template: promptTemplate }),
      });
      if (response.ok) {
        setSnackbar({
          open: true,
          message: "Configuration saved successfully",
          severity: "success",
        });
      } else {
        throw new Error("Failed to save configuration");
      }
    } catch (error) {
      console.error("Error saving config:", error);
      setSnackbar({
        open: true,
        message: "Error saving configuration",
        severity: "error",
      });
    }
    handleConfigClose();
  };

  const handleConfigReset = async () => {
    try {
      const response = await fetch("http://localhost:8000/config/reset", {
        method: "POST",
      });
      if (response.ok) {
        await fetchConfig();
        setSnackbar({
          open: true,
          message: "Configuration reset to default",
          severity: "success",
        });
      } else {
        throw new Error("Failed to reset configuration");
      }
    } catch (error) {
      console.error("Error resetting config:", error);
      setSnackbar({
        open: true,
        message: "Error resetting configuration",
        severity: "error",
      });
    }
  };

  const toggleDebugPanel = () => {
    setDebugOpen(!debugOpen);
  };

  const handleResetAndRescan = async () => {
    setIsResetting(true);
    setResetProgress({ progress: 0, current: 0, total: 0 });
    try {
      const response = await fetch("http://localhost:8000/reset-and-rescan", {
        method: "POST",
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        lines.forEach((line) => {
          if (line) {
            const data = JSON.parse(line);
            if (data.status === "Processing") {
              setResetProgress({
                progress: parseFloat(data.progress),
                current: data.current,
                total: data.total,
              });
            } else if (data.status === "Completed") {
              setSnackbar({
                open: true,
                message: "Reset and rescan completed successfully",
                severity: "success",
              });
            }
          }
        });
      }
    } catch (error) {
      console.error("Error during reset and rescan:", error);
      setSnackbar({
        open: true,
        message: "Error during reset and rescan",
        severity: "error",
      });
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md">
        <Box sx={{ my: 4, position: "relative" }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Local RAG App
          </Typography>
          <IconButton
            sx={{ position: "absolute", top: 0, right: 40 }}
            onClick={handleConfigOpen}
            aria-label="settings"
          >
            <SettingsIcon />
          </IconButton>
          <IconButton
            sx={{ position: "absolute", top: 0, right: 0 }}
            onClick={toggleDebugPanel}
            aria-label="debug"
          >
            <CodeIcon />
          </IconButton>
          <form onSubmit={handleQuery}>
            <TextField
              fullWidth
              variant="outlined"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your question"
              disabled={isLoading}
              sx={{ mb: 2 }}
            />
            <Button
              type="submit"
              variant="contained"
              disabled={isLoading}
              startIcon={isLoading ? <CircularProgress size={20} /> : null}
            >
              {isLoading ? "Loading..." : "Submit"}
            </Button>
          </form>
          {answer && (
            <Box sx={{ mt: 4 }} ref={answerRef}>
              <Typography variant="h6">Answer:</Typography>
              <Typography variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
                {answer}
              </Typography>
            </Box>
          )}
          {sources.length > 0 && (
            <Box sx={{ mt: 4 }}>
              <Typography variant="h6">Sources:</Typography>
              {sources.map((source, index) => (
                <Link
                  key={index}
                  component="button"
                  variant="body2"
                  onClick={() => handleSourceClick(source)}
                  sx={{ display: "block", mb: 1 }}
                >
                  {source}
                </Link>
              ))}
            </Box>
          )}
        </Box>
        <Dialog open={configOpen} onClose={handleConfigClose}>
          <DialogTitle>Configuration</DialogTitle>
          <DialogContent>
            <Typography variant="body2" gutterBottom>
              Customize the prompt template. Use {"{context}"} for the retrieved
              document content and {"{question}"} for the user's question.
            </Typography>
            <TextField
              autoFocus
              margin="dense"
              label="Prompt Template"
              type="text"
              fullWidth
              multiline
              rows={8}
              variant="outlined"
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
            />
            <Box mt={2}>
              <Button
                onClick={handleResetAndRescan}
                variant="contained"
                color="secondary"
                disabled={isResetting}
              >
                {isResetting ? "Resetting..." : "Reset DB and Rescan Documents"}
              </Button>
            </Box>
            {isResetting && (
              <Box mt={2}>
                <LinearProgress
                  variant="determinate"
                  value={resetProgress.progress}
                />
                <Typography variant="body2" color="textSecondary">
                  {`${resetProgress.progress.toFixed(2)}% - ${
                    resetProgress.current
                  } of ${resetProgress.total} documents processed`}
                </Typography>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={handleConfigReset}>Reset to Default</Button>
            <Button onClick={handleConfigClose}>Cancel</Button>
            <Button onClick={handleConfigSave}>Save</Button>
          </DialogActions>
        </Dialog>
        <Snackbar
          open={snackbar.open}
          autoHideDuration={6000}
          onClose={handleCloseSnackbar}
        >
          <Alert
            onClose={handleCloseSnackbar}
            severity={snackbar.severity}
            sx={{ width: "100%" }}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
        <Drawer anchor="bottom" open={debugOpen} onClose={toggleDebugPanel}>
          <Box
            sx={{
              width: "auto",
              height: "50vh",
              padding: 2,
              overflowY: "auto",
            }}
          >
            <Typography variant="h6" gutterBottom>
              Debug Information
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={20}
              variant="outlined"
              value={debugInfo}
              InputProps={{
                readOnly: true,
              }}
            />
          </Box>
        </Drawer>
      </Container>
    </ThemeProvider>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
