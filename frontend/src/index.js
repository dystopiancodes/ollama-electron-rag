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
      proxy: false,
      family: 4,
    })
    .then((response) => {
      console.log("Backend is ready");
      console.log("Response data:", response.data);
      app.emit("backend-ready");
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

  app.on("backend-ready", () => {
    createWindow();
    if (mainWindow) {
      mainWindow.webContents.send("backendReady");
    }
  });

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
