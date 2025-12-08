/**
 * Mac Assistant - Electron Main Process
 *
 * Handles window management, IPC communication, and system integration.
 */

const { app, BrowserWindow, ipcMain, Menu, shell, nativeTheme } = require('electron');
const path = require('path');
const Store = require('electron-store');

// Persistent settings store
const store = new Store({
  defaults: {
    windowBounds: { width: 1200, height: 800 },
    apiPort: 8000,
    theme: 'system',
    sidebarWidth: 280,
    showMetrics: true,
  }
});

let mainWindow = null;

function createWindow() {
  const { width, height, x, y } = store.get('windowBounds');

  mainWindow = new BrowserWindow({
    width,
    height,
    x,
    y,
    minWidth: 800,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 15, y: 15 },
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#1a1a2e' : '#ffffff',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
    show: false,
  });

  // Load the app
  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'));

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Save window position on close
  mainWindow.on('close', () => {
    store.set('windowBounds', mainWindow.getBounds());
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
}

// Create application menu
function createMenu() {
  const template = [
    {
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        {
          label: 'Preferences...',
          accelerator: 'CmdOrCtrl+,',
          click: () => mainWindow?.webContents.send('open-settings'),
        },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'File',
      submenu: [
        {
          label: 'New Chat',
          accelerator: 'CmdOrCtrl+N',
          click: () => mainWindow?.webContents.send('new-chat'),
        },
        { type: 'separator' },
        {
          label: 'Export Data...',
          accelerator: 'CmdOrCtrl+E',
          click: () => mainWindow?.webContents.send('export-data'),
        },
        {
          label: 'Import Data...',
          accelerator: 'CmdOrCtrl+I',
          click: () => mainWindow?.webContents.send('import-data'),
        },
        { type: 'separator' },
        { role: 'close' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Toggle Sidebar',
          accelerator: 'CmdOrCtrl+\\',
          click: () => mainWindow?.webContents.send('toggle-sidebar'),
        },
        {
          label: 'Toggle Metrics',
          accelerator: 'CmdOrCtrl+M',
          click: () => mainWindow?.webContents.send('toggle-metrics'),
        },
        { type: 'separator' },
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'RAG',
      submenu: [
        {
          label: 'Medical Pocket',
          click: () => mainWindow?.webContents.send('select-pocket', 'medical'),
        },
        {
          label: 'Finance Pocket',
          click: () => mainWindow?.webContents.send('select-pocket', 'finance'),
        },
        {
          label: 'Study Pocket',
          click: () => mainWindow?.webContents.send('select-pocket', 'study'),
        },
        {
          label: 'Writing Pocket',
          click: () => mainWindow?.webContents.send('select-pocket', 'writing'),
        },
        { type: 'separator' },
        {
          label: 'No Pocket (General)',
          click: () => mainWindow?.webContents.send('select-pocket', null),
        },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        { type: 'separator' },
        { role: 'front' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Documentation',
          click: () => shell.openExternal('https://github.com/microsoft/Foundry-Local'),
        },
        {
          label: 'API Docs',
          click: () => shell.openExternal(`http://localhost:${store.get('apiPort')}/docs`),
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// IPC Handlers
ipcMain.handle('get-settings', () => {
  return {
    apiPort: store.get('apiPort'),
    theme: store.get('theme'),
    sidebarWidth: store.get('sidebarWidth'),
    showMetrics: store.get('showMetrics'),
  };
});

ipcMain.handle('set-settings', (event, settings) => {
  Object.entries(settings).forEach(([key, value]) => {
    store.set(key, value);
  });
  return true;
});

ipcMain.handle('get-theme', () => {
  const theme = store.get('theme');
  if (theme === 'system') {
    return nativeTheme.shouldUseDarkColors ? 'dark' : 'light';
  }
  return theme;
});

// App lifecycle
app.whenReady().then(() => {
  createWindow();
  createMenu();

  // Handle theme changes
  nativeTheme.on('updated', () => {
    mainWindow?.webContents.send('theme-changed',
      nativeTheme.shouldUseDarkColors ? 'dark' : 'light'
    );
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
