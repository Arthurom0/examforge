// Exposes a tiny, explicit API to the web UI (window.examforge). Nothing else from Node is reachable.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("examforge", {
  savePDF: (suggestedName) => ipcRenderer.invoke("save-pdf", suggestedName),
  openDataFolder: () => ipcRenderer.invoke("open-data-folder"),
  version: ipcRenderer.sendSync("app-version-sync"),
});
