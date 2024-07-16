import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import IconButton from '@mui/material/IconButton';
import SettingsIcon from '@mui/icons-material/Settings';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
  },
});

function App() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [configOpen, setConfigOpen] = useState(false);
  const [promptTemplate, setPromptTemplate] = useState('');
  const answerRef = useRef(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await fetch('http://localhost:8000/config');
      const data = await response.json();
      setPromptTemplate(data.prompt_template);
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const handleQuery = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setAnswer('');
    setSources([]);

    try {
      const response = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: query }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        lines.forEach(line => {
          if (line) {
            try {
              const data = JSON.parse(line);
              if (data.answer) {
                setAnswer(prev => prev + data.answer);
              }
              if (data.sources) {
                setSources(data.sources);
              }
            } catch (error) {
              console.error('Error parsing JSON:', error);
            }
          }
        });
      }
    } catch (error) {
      console.error('Error querying documents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSourceClick = (filename) => {
    console.log('Attempting to open file:', filename);
    if (window.electron && window.electron.openFile) {
      window.electron.openFile(filename)
        .then((result) => {
          console.log('File open result:', result);
          setSnackbar({
            open: true,
            message: result.message,
            severity: result.success ? 'success' : 'error'
          });
        })
        .catch(error => {
          console.error('Error opening file:', error);
          setSnackbar({
            open: true,
            message: `Error opening file: ${error.message}`,
            severity: 'error'
          });
        });
    } else {
      console.error('Electron API not available');
      setSnackbar({
        open: true,
        message: 'Electron API not available',
        severity: 'error'
      });
    }
  };

  const handleCloseSnackbar = (event, reason) => {
    if (reason === 'clickaway') {
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
      const response = await fetch('http://localhost:8000/config', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ template: promptTemplate }),
      });
      if (response.ok) {
        setSnackbar({
          open: true,
          message: 'Config saved successfully',
          severity: 'success'
        });
      } else {
        throw new Error('Failed to save config');
      }
    } catch (error) {
      console.error('Error saving config:', error);
      setSnackbar({
        open: true,
        message: 'Error saving config',
        severity: 'error'
      });
    }
    handleConfigClose();
  };

  const handleConfigReset = async () => {
    try {
      const response = await fetch('http://localhost:8000/config/reset', {
        method: 'POST',
      });
      if (response.ok) {
        await fetchConfig();
        setSnackbar({
          open: true,
          message: 'Config reset to default',
          severity: 'success'
        });
      } else {
        throw new Error('Failed to reset config');
      }
    } catch (error) {
      console.error('Error resetting config:', error);
      setSnackbar({
        open: true,
        message: 'Error resetting config',
        severity: 'error'
      });
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md">
        <Box sx={{ my: 4, position: 'relative' }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Local RAG App
          </Typography>
          <IconButton
            sx={{ position: 'absolute', top: 0, right: 0 }}
            onClick={handleConfigOpen}
          >
            <SettingsIcon />
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
              {isLoading ? 'Loading...' : 'Submit'}
            </Button>
          </form>
          {answer && (
            <Box sx={{ mt: 4 }} ref={answerRef}>
              <Typography variant="h6">Answer:</Typography>
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
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
                  sx={{ display: 'block', mb: 1 }}
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
            <TextField
              autoFocus
              margin="dense"
              label="Prompt Template"
              type="text"
              fullWidth
              multiline
              rows={4}
              variant="outlined"
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={handleConfigReset}>Reset to Default</Button>
            <Button onClick={handleConfigClose}>Cancel</Button>
            <Button onClick={handleConfigSave}>Save</Button>
          </DialogActions>
        </Dialog>
        <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleCloseSnackbar}>
          <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Container>
    </ThemeProvider>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<App />);