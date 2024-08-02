require("dotenv").config();
const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const axios = require("axios");
const { spawn } = require("child_process");
const dns = require("dns");
const net = require("net");

// Force IPv4
dns.setDefaultResultOrder("ipv4first");

// Override net.isIP to always return 4 for localhost
const originalIsIP = net.isIP;
net.isIP = (input) => {
  if (input === "localhost" || input === "127.0.0.1") {
    return 4;
  }
  return originalIsIP(input);
};

let mainWindow;
let backendProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));
  mainWindow.webContents.openDevTools();
}

function findVenvPython(backendPath) {
  const venvPath = path.join(backendPath, "venv");
  let pythonPath;

  if (process.platform === "win32") {
    pythonPath = path.join(venvPath, "Scripts", "python.exe");
  } else {
    pythonPath = path.join(venvPath, "bin", "python");
  }

  if (fs.existsSync(pythonPath)) {
    console.log(`Found venv Python at: ${pythonPath}`);
    return pythonPath;
  }

  throw new Error("Virtual environment Python not found");
}

function startBackend() {
  const backendPath = path.join(__dirname, "..", "..", "backend");
  const pythonPath = findVenvPython(backendPath);

  console.log(`Starting backend process with ${pythonPath}...`);
  backendProcess = spawn(
    pythonPath,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    {
      cwd: backendPath,
      stdio: "pipe",
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    }
  );
  backendProcess.stdout.on("data", (data) => {
    console.log(`Backend stdout: ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`Backend stderr: ${data}`);
  });

  backendProcess.on("error", (error) => {
    console.error("Failed to start backend:", error);
    dialog.showErrorBox(
      "Backend Error",
      `Failed to start backend: ${error.message}`
    );
  });

  backendProcess.on("exit", (code, signal) => {
    if (code !== 0) {
      console.error(`Backend process exited with code ${code}`);
      dialog.showErrorBox(
        "Backend Error",
        `Backend process exited unexpectedly with code ${code}`
      );
    }
  });
  checkBackendHealth();
}

function checkBackendHealth(retries = 0, maxRetries = 30) {
  if (retries >= maxRetries) {
    console.error("Backend health check failed after maximum retries");
    dialog.showErrorBox(
      "Backend Error",
      "Failed to connect to the backend after multiple attempts. Please check the backend logs and restart the application."
    );
    app.quit();
    return;
  }

  console.log(
    `Attempting to connect to backend (attempt ${retries + 1}/${maxRetries})...`
  );
  axios
    .get("http://127.0.0.1:8000/health", {
      timeout: 1000,
      headers: { Host: "localhost" },
      proxy: false, // Disable any proxy settings
      family: 4, // Force IPv4
    })
    .then((response) => {
      console.log("Backend is ready, creating window");
      console.log("Response data:", response.data);
      createWindow();
    })
    .catch((error) => {
      console.log(`Backend not ready yet: ${error.message}`);
      if (error.response) {
        console.log("Error response data:", error.response.data);
        console.log("Error response status:", error.response.status);
        console.log("Error response headers:", error.response.headers);
      } else if (error.request) {
        console.log("Error request:", error.request);
      }
      setTimeout(() => checkBackendHealth(retries + 1, maxRetries), 1000);
    });
}

app.whenReady().then(() => {
  console.log("Electron app is ready");
  startBackend();

  app.on("activate", function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", function () {
  if (process.platform !== "darwin") {
    if (backendProcess) {
      backendProcess.kill();
    }
    app.quit();
  }
});

// ... (rest of the code remains the same)

// ... (rest of the code remains the same)

ipcMain.handle("select-folder", async () => {
  try {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory"],
    });

    if (!result.canceled && result.filePaths.length > 0) {
      const folderPath = result.filePaths[0];
      try {
        const response = await axios.post("http://127.0.0.1:8000/set-folder", {
          path: folderPath,
        });
        console.log("Backend response:", response.data);
        return {
          success: true,
          path: folderPath,
          message: response.data.message,
        };
      } catch (error) {
        console.error(
          "Error setting folder on backend:",
          error.response ? error.response.data : error.message
        );
        return {
          success: false,
          error: error.response ? error.response.data.detail : error.message,
        };
      }
    }
    return { success: false, error: "No folder selected" };
  } catch (error) {
    console.error("Error in select-folder:", error);
    return { success: false, error: error.message };
  }
});
ipcMain.handle("check-backend", async () => {
  try {
    const response = await axios.get("http://localhost:8000/health");
    return response.status === 200;
  } catch (error) {
    console.error("Error checking backend:", error);
    return false;
  }
});
