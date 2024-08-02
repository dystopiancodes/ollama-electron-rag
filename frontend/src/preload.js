const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  selectFolder: () => ipcRenderer.invoke("select-folder"),
  openFile: (filename) => ipcRenderer.invoke("open-file", filename),
  onBackendReady: (callback) => {
    if (callback) {
      ipcRenderer.on("backendReady", callback);
    } else {
      ipcRenderer.removeAllListeners("backendReady");
    }
  },
  checkBackend: () => ipcRenderer.invoke("check-backend"),
});

console.log("Preload script executed");
