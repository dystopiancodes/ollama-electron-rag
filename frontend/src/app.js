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
import StopIcon from "@mui/icons-material/Stop";

import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import LinearProgress from "@mui/material/LinearProgress";
import Drawer from "@mui/material/Drawer";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import Paper from "@mui/material/Paper";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1976d2",
    },
  },
});

function App() {
  const [isGenerating, setIsGenerating] = useState(false);
  const abortControllerRef = useRef(null);
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

  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [kValue, setKValue] = useState(5); // Add this line
  const [currentKValue, setCurrentKValue] = useState(5);
  const [currentModel, setCurrentModel] = useState(""); // Add this line
  const [selectedFolder, setSelectedFolder] = useState("");
  const [backendReady, setBackendReady] = useState(false);
  const [backendStatus, setBackendStatus] = useState(
    "Checking backend status..."
  );

  useEffect(() => {
    const backendReadyHandler = () => {
      console.log("Backend ready signal received from main process");
      setBackendReady(true);
      fetchConfig();
      fetchModels();
    };

    window.electron.onBackendReady(backendReadyHandler);

    const intervalId = setInterval(() => {
      console.log("Checking backend status...");
      window.electron.checkBackend().then((isReady) => {
        console.log("Backend status:", isReady ? "ready" : "not ready");
        if (isReady) {
          setBackendReady(true);
          fetchConfig();
          fetchModels();
          setBackendStatus("Backend status: ready");
          clearInterval(intervalId);
        }
      });
    }, 5000);

    return () => {
      clearInterval(intervalId);
      window.electron.onBackendReady(null);
    };
  }, []);

  const fetchWithTimeout = async (url, options = {}, timeout = 5000) => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(id);
    return response;
  };

  const fetchConfig = async () => {
    try {
      const response = await fetch("http://localhost:8000/config");
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log(data);
      setPromptTemplate(data.prompt_template);
      setSelectedModel(data.model);
      setKValue(data.k);
      setCurrentModel(data.model);
      setCurrentKValue(data.k);
      setModels(data.available_models);
      setSelectedFolder(data.current_folder);
    } catch (error) {
      console.error("Error fetching config:", error);
      setSnackbar({
        open: true,
        message: "Error fetching configuration: " + error.message,
        severity: "error",
      });
    }
  };

  const fetchModels = async () => {
    try {
      const response = await fetchWithTimeout("http://localhost:8000/models");
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log("Fetched models:", data.models);
      setModels(data.models);
    } catch (error) {
      console.error("Error fetching models:", error);
      setSnackbar({
        open: true,
        message: "Error fetching models: " + error.message,
        severity: "error",
      });
    }
  };

  const handleFolderSelection = async () => {
    try {
      const result = await window.electron.selectFolder();
      if (result.success) {
        setSelectedFolder(result.path);
        setSnackbar({
          open: true,
          message: result.message || "Folder set successfully",
          severity: "success",
        });
        await fetchDocuments();
      } else {
        setSnackbar({
          open: true,
          message: `Error selecting folder: ${result.error}`,
          severity: "error",
        });
      }
    } catch (error) {
      console.error("Error selecting folder:", error);
      setSnackbar({
        open: true,
        message: `Error selecting folder: ${error.message}`,
        severity: "error",
      });
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!selectedFolder) {
      setSnackbar({
        open: true,
        message: "Please select a folder first",
        severity: "warning",
      });
      return;
    }
    setIsLoading(true);
    setIsGenerating(true);
    setAnswer("");
    setSources([]);
    setDebugInfo("");

    try {
      abortControllerRef.current = new AbortController();
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: query, k: currentKValue }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

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
      if (error.name === "AbortError") {
        console.log("Fetch aborted");
        setSnackbar({
          open: true,
          message: "Generation stopped",
          severity: "info",
        });
      } else {
        console.error("Error querying documents:", error);
        setSnackbar({
          open: true,
          message: "Error querying documents: " + error.message,
          severity: "error",
        });
      }
    } finally {
      setIsLoading(false);
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  const fetchDocuments = async () => {
    if (selectedFolder) {
      try {
        const response = await fetch("http://localhost:8000/documents");
        const data = await response.json();
        // Update your state with the new document list
        // ...
      } catch (error) {
        console.error("Error fetching documents:", error);
        setSnackbar({
          open: true,
          message: "Error fetching documents",
          severity: "error",
        });
      }
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
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
      console.log("Sending config:", {
        template: promptTemplate,
        model: selectedModel,
        k: kValue,
        folder: selectedFolder,
      });
      const response = await fetch("http://localhost:8000/config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          template: promptTemplate,
          model: selectedModel,
          k: parseInt(kValue, 10),
          folder: selectedFolder,
        }),
      });
      if (response.ok) {
        setCurrentModel(selectedModel);
        setCurrentKValue(parseInt(kValue, 10));
        setSnackbar({
          open: true,
          message: "Configuration saved successfully. LLM and k value updated.",
          severity: "success",
        });
        handleConfigClose();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to save configuration");
      }
    } catch (error) {
      console.error("Error saving config:", error);
      setSnackbar({
        open: true,
        message: `Error saving configuration: ${error.message}`,
        severity: "error",
      });
    }
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
        {!backendReady ? (
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "100vh",
            }}
          >
            <CircularProgress />
            <Typography variant="h6" sx={{ ml: 2 }}>
              Waiting for backend to start...
            </Typography>
          </Box>
        ) : (
          <>
            <Box
              sx={{ my: 4, position: "relative", minHeight: "100vh", pb: 10 }}
            >
              <Button
                onClick={handleFolderSelection}
                variant="contained"
                sx={{ mb: 2 }}
              >
                Select Folder
              </Button>

              {selectedFolder && (
                <Typography variant="body1" sx={{ mb: 2 }}>
                  Current folder: {selectedFolder}
                </Typography>
              )}

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
                <Box sx={{ display: "flex", gap: 2 }}>
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={isLoading}
                    startIcon={
                      isLoading ? <CircularProgress size={20} /> : null
                    }
                  >
                    {isLoading ? "Loading..." : "Submit"}
                  </Button>
                  {isGenerating && (
                    <Button
                      variant="outlined"
                      color="secondary"
                      onClick={handleStopGeneration}
                      startIcon={<StopIcon />}
                    >
                      Stop
                    </Button>
                  )}
                </Box>
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
                  Customize the prompt template and select the model.
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
                <FormControl fullWidth margin="normal">
                  <InputLabel id="model-select-label">Model</InputLabel>
                  <Select
                    labelId="model-select-label"
                    value={selectedModel}
                    label="Model"
                    onChange={(e) => setSelectedModel(e.target.value)}
                  >
                    {models.map((model) => (
                      <MenuItem key={model} value={model}>
                        {model}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField
                  margin="normal"
                  label="K Value"
                  type="number"
                  fullWidth
                  variant="outlined"
                  value={kValue}
                  onChange={(e) => setKValue(parseInt(e.target.value, 10))}
                />

                <Box mt={2}>
                  <Button
                    onClick={handleResetAndRescan}
                    variant="contained"
                    color="secondary"
                    disabled={isResetting}
                  >
                    {isResetting
                      ? "Resetting..."
                      : "Reset DB and Rescan Documents"}
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
            <Paper
              elevation={3}
              sx={{
                position: "fixed",
                bottom: 16,
                right: 16,
                padding: 1,
                borderRadius: 1,
                backgroundColor: "rgba(255, 255, 255, 0.8)",
                zIndex: 1000,
              }}
            >
              <Typography variant="caption" display="block">
                Model: {currentModel}
              </Typography>
              <Typography variant="caption" display="block">
                k: {currentKValue}
              </Typography>
            </Paper>
          </>
        )}
      </Container>
    </ThemeProvider>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<App />);
