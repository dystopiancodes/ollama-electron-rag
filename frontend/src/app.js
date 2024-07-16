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
  const answerRef = useRef(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });


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

  useEffect(() => {
    if (answerRef.current) {
      answerRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [answer]);

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

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md">
        <Box sx={{ my: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Local RAG App
          </Typography>
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