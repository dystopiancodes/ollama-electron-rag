const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const axios = require("axios");

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
      contentSecurityPolicy:
        "default-src 'self'; connect-src 'self' http://localhost:8000; script-src 'self'",
    },
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));

  // Open DevTools for debugging
  mainWindow.webContents.openDevTools();

  mainWindow.webContents.on("did-finish-load", () => {
    console.log("Window loaded");
  });
}

app.whenReady().then(() => {
  console.log("App is ready");
  createWindow();

  ipcMain.handle("open-file", async (event, filename) => {
    console.log("Main: Received request to open file:", filename);

    // First, try to find the file in the app's user data directory
    let documentsPath = path.join(app.getPath("userData"), "documents");
    let filePath = path.join(documentsPath, filename);

    console.log("Main: Checking file at path:", filePath);

    if (!fs.existsSync(filePath)) {
      console.log(
        "File not found in user data directory, checking in the backend data directory"
      );
      // If not found, try the backend data directory
      documentsPath = path.join(
        __dirname,
        "..",
        "..",
        "backend",
        "data",
        "documents"
      );
      filePath = path.join(documentsPath, filename);
      console.log("Main: Checking file at alternate path:", filePath);
    }

    if (fs.existsSync(filePath)) {
      console.log("Main: File found, attempting to open");
      try {
        await shell.openPath(filePath);
        console.log("Main: File opened successfully");
        return { success: true, message: "File opened successfully" };
      } catch (error) {
        console.error("Main: Error opening file:", error);
        return {
          success: false,
          message: `Error opening file: ${error.message}`,
        };
      }
    } else {
      console.error("Main: File not found");
      return { success: false, message: "File not found" };
    }
  });

  ipcMain.handle("select-folder", async () => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ["openDirectory"],
      });

      if (!result.canceled && result.filePaths.length > 0) {
        const folderPath = result.filePaths[0];
        try {
          const response = await axios.post(
            "http://localhost:8000/set-folder",
            {
              path: folderPath,
            }
          );
          console.log("Backend response:", response.data);
          return folderPath;
        } catch (error) {
          console.error("Error setting folder on backend:", error);
          if (error.response) {
            console.error("Backend error response:", error.response.data);
          } else if (error.request) {
            console.error("No response received from backend");
          } else {
            console.error("Error setting up the request:", error.message);
          }
          throw new Error(`Failed to set folder on backend: ${error.message}`);
        }
      }
      return null;
    } catch (error) {
      console.error("Error in select-folder:", error);
      throw error;
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
