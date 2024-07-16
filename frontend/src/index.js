const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
  });

  win.loadFile(path.join(__dirname, 'index.html'));
  
  // Open DevTools for debugging
  win.webContents.openDevTools();

  win.webContents.on('did-finish-load', () => {
    console.log('Window loaded');
  });
}

app.whenReady().then(() => {
  console.log('App is ready');
  createWindow();

  ipcMain.handle('open-file', async (event, filename) => {
    console.log('Main: Received request to open file:', filename);
    
    // First, try to find the file in the app's user data directory
    let documentsPath = path.join(app.getPath('userData'), 'documents');
    let filePath = path.join(documentsPath, filename);
    
    console.log('Main: Checking file at path:', filePath);
    
    if (!fs.existsSync(filePath)) {
      console.log('File not found in user data directory, checking in the backend data directory');
      // If not found, try the backend data directory
      documentsPath = path.join(__dirname, '..', '..', 'backend', 'data', 'documents');
      filePath = path.join(documentsPath, filename);
      console.log('Main: Checking file at alternate path:', filePath);
    }

    if (fs.existsSync(filePath)) {
      console.log('Main: File found, attempting to open');
      try {
        await shell.openPath(filePath);
        console.log('Main: File opened successfully');
        return { success: true, message: 'File opened successfully' };
      } catch (error) {
        console.error('Main: Error opening file:', error);
        return { success: false, message: `Error opening file: ${error.message}` };
      }
    } else {
      console.error('Main: File not found');
      return { success: false, message: 'File not found' };
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});