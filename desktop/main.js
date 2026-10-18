// ExamForge desktop shell: starts the bundled Python engine on a free localhost port and shows the UI
// in a native window. No browser involved; everything stays on this computer.
const { app, BrowserWindow, dialog, ipcMain, nativeTheme, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const path = require("path");
const http = require("http");

const DATA_DIR = app.getPath("userData"); // ~/Library/Application Support/ExamForge on macOS
const LOG_DIR = path.join(DATA_DIR, "logs");
const ENV_FILE = path.join(DATA_DIR, ".env");

let backend = null;
let baseUrl = null;
let mainWindow = null;
let quitting = false;

if (!app.requestSingleInstanceLock()) {
  app.quit();
}

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

/** Packaged: the PyInstaller binary in Resources. Development: the repo's .venv Python. */
function backendCommand(port) {
  const args = ["--port", String(port)];
  if (app.isPackaged) {
    const exe = process.platform === "win32" ? "examforge-server.exe" : "examforge-server";
    return {
      cmd: path.join(process.resourcesPath, "backend", "examforge-server", exe),
      args,
      cwd: path.join(process.resourcesPath, "backend", "examforge-server"),
      staticDir: path.join(process.resourcesPath, "frontend"),
    };
  }
  const repo = path.resolve(__dirname, "..");
  const py = process.platform === "win32" ? path.join(repo, ".venv", "Scripts", "python.exe") : path.join(repo, ".venv", "bin", "python");
  return {
    cmd: fs.existsSync(py) ? py : "python3",
    args: ["-m", "app.desktop_server", ...args],
    cwd: path.join(repo, "backend"),
    staticDir: path.join(repo, "frontend", "dist"),
  };
}

function startBackend(port) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const log = fs.createWriteStream(path.join(LOG_DIR, "engine.log"), { flags: "w" });
  const { cmd, args, cwd, staticDir } = backendCommand(port);
  const env = {
    ...process.env,
    EXAMFORGE_DATA_DIR: DATA_DIR,
    EXAMFORGE_ENV_FILE: ENV_FILE,
    EXAMFORGE_STATIC_DIR: staticDir,
    PYTHONUNBUFFERED: "1",
  };
  backend = spawn(cmd, args, { cwd, env });
  backend.stdout.pipe(log);
  backend.stderr.pipe(log);
  backend.on("exit", (code) => {
    backend = null;
    if (!quitting) {
      dialog.showErrorBox(
        "ExamForge stopped unexpectedly",
        `The ExamForge engine exited (code ${code}). Details are in:\n${path.join(LOG_DIR, "engine.log")}`,
      );
      app.quit();
    }
  });
}

function waitForHealth(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(`${url}/api/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on("error", retry);
      req.setTimeout(2000, () => req.destroy());
    };
    const retry = () => (Date.now() > deadline ? reject(new Error("timeout")) : setTimeout(attempt, 300));
    attempt();
  });
}

function isInternal(url) {
  return baseUrl && url.startsWith(baseUrl);
}

function configureWindow(win) {
  // Links to other sites open in the default browser; app pages (print view, PDFs) open in a new app window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isInternal(url)) {
      return {
        action: "allow",
        overrideBrowserWindowOptions: {
          width: 1000,
          height: 900,
          backgroundColor: "#ffffff",
          webPreferences: windowPrefs(),
        },
      };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!isInternal(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });
}

app.on("browser-window-created", (_e, win) => configureWindow(win));

function windowPrefs() {
  return {
    preload: path.join(__dirname, "preload.js"),
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true,
    plugins: true, // built-in PDF viewer for opening uploaded course PDFs
  };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: "ExamForge",
    show: false,
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#020617" : "#f8fafc",
    webPreferences: windowPrefs(),
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => (mainWindow = null));
  return mainWindow;
}

async function boot() {
  const win = createWindow();
  win.loadFile(path.join(__dirname, "loading.html"));
  try {
    const port = await freePort();
    baseUrl = `http://127.0.0.1:${port}`;
    startBackend(port);
    // The first launch can be slow while macOS verifies the bundled engine.
    await waitForHealth(baseUrl, 90_000);
    if (!win.isDestroyed()) win.loadURL(baseUrl);
  } catch (err) {
    dialog.showErrorBox(
      "ExamForge could not start",
      `The engine did not respond (${err.message}). Details are in:\n${path.join(LOG_DIR, "engine.log")}`,
    );
    app.quit();
  }
}

ipcMain.handle("save-pdf", async (event, suggestedName) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  const { canceled, filePath } = await dialog.showSaveDialog(win, {
    title: "Save problem set as PDF",
    defaultPath: path.join(app.getPath("documents"), suggestedName || "ExamForge.pdf"),
    filters: [{ name: "PDF", extensions: ["pdf"] }],
  });
  if (canceled || !filePath) return { saved: false };
  const pdf = await event.sender.printToPDF({
    pageSize: "A4",
    printBackground: true,
    margins: { top: 0.6, bottom: 0.6, left: 0.6, right: 0.6 },
  });
  fs.writeFileSync(filePath, pdf);
  shell.showItemInFolder(filePath);
  return { saved: true, path: filePath };
});

ipcMain.handle("open-data-folder", () => shell.openPath(DATA_DIR));
ipcMain.on("app-version-sync", (event) => (event.returnValue = app.getVersion()));

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

app.whenReady().then(boot);

// macOS convention: closing the window keeps the app in the Dock; clicking the Dock icon reopens it.
app.on("activate", () => {
  if (!mainWindow && baseUrl) createWindow().loadURL(baseUrl);
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  quitting = true;
  if (backend) backend.kill();
});
