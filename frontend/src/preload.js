const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electron", {
  selectFolder: () => ipcRenderer.invoke("select-folder"),

  openFile: (filename) => {
    console.log("Preload: Requesting to open file:", filename);
    return ipcRenderer.invoke("open-file", filename);
  },
});

console.log("Preload script executed");
