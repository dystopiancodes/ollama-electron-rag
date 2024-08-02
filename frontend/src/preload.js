const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  selectFolder: () => ipcRenderer.invoke("select-folder"),
  openFile: (filename) => ipcRenderer.invoke("open-file", filename),
  checkBackend: () => ipcRenderer.invoke("check-backend"),
  onBackendReady: (callback) => ipcRenderer.on("backend-ready", callback),
});

console.log("Preload script executed");
