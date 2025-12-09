/**
 * Mac Assistant - Electron Main Process
 *
 * Handles window management, IPC communication, and system integration.
 */

const { app, BrowserWindow, ipcMain, Menu, Tray, shell, nativeTheme, globalShortcut, screen, nativeImage } = require('electron');
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
    quickPromptShortcut: 'CmdOrCtrl+Space',
  }
});

let mainWindow = null;
let quickPromptWindow = null;
let tray = null;

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

// Create Quick Prompt Window (floating spotlight-like window)
function createQuickPromptWindow() {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;

  quickPromptWindow = new BrowserWindow({
    width: 680,
    height: 400,
    x: Math.floor((screenWidth - 680) / 2),
    y: Math.floor(screenHeight / 4),
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  quickPromptWindow.loadFile(path.join(__dirname, 'src', 'quick-prompt.html'));

  // Hide on blur
  quickPromptWindow.on('blur', () => {
    hideQuickPrompt();
  });

  quickPromptWindow.on('closed', () => {
    quickPromptWindow = null;
  });
}

function showQuickPrompt() {
  if (!quickPromptWindow) {
    createQuickPromptWindow();
    quickPromptWindow.once('ready-to-show', () => {
      quickPromptWindow.show();
      quickPromptWindow.focus();
    });
  } else {
    quickPromptWindow.show();
    quickPromptWindow.focus();
  }
}

function hideQuickPrompt() {
  if (quickPromptWindow && quickPromptWindow.isVisible()) {
    quickPromptWindow.hide();
    quickPromptWindow.webContents.send('quick-prompt-hidden');
  }
}

function toggleQuickPrompt() {
  if (quickPromptWindow && quickPromptWindow.isVisible()) {
    hideQuickPrompt();
  } else {
    showQuickPrompt();
  }
}

// Create system tray
function createTray() {
  // Create a simple template icon programmatically (16x16 for macOS menu bar)
  // This is a simple circle icon that works as a template
  const iconDataUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAbwAAAG8B8aLcQwAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAADVSURBVDiNpZMxCoQwEEX/JIVewMJC8AR6Am+ghY2FhZVewMLKI3gDb2DnKSwtvIGFhZVHsLAQC0VYWSGb1d3FB4HJZObNZIYB/oyot+q6Ts65EEKSXQCQJMMJAFRVVXI4HOR93/sAgLIs8wDg8/lMkpTn+eMqPM9LAIBlWQiCgHVdowxDUiwWS+R5HqqqEsdx/wVJkgQlBNE0jaZpJiVJ4nPnug4AvOu6/wmKoliaprmu64ZhGP5bwWKx8AFgGAbZtu1f4Lpu0nXdbwDiWS0Z+wFXrD+mHnVnfAAAAABJRU5ErkJggg==';

  const icon = nativeImage.createFromDataURL(iconDataUrl);
  icon.setTemplateImage(true);  // Make it a template image for macOS

  tray = new Tray(icon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Quick Prompt',
      accelerator: store.get('quickPromptShortcut'),
      click: () => showQuickPrompt(),
    },
    { type: 'separator' },
    {
      label: 'Show Mac Assistant',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: 'New Chat',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('new-chat');
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Preferences...',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('open-settings');
        }
      },
    },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);

  tray.setToolTip('Mac Assistant');
  tray.setContextMenu(contextMenu);

  // Click on tray icon shows quick prompt
  tray.on('click', () => {
    toggleQuickPrompt();
  });
}

// Register global shortcut for quick prompt
function registerGlobalShortcuts() {
  const shortcut = store.get('quickPromptShortcut') || 'CmdOrCtrl+Shift+Space';

  try {
    globalShortcut.register(shortcut, () => {
      toggleQuickPrompt();
    });
  } catch (error) {
    console.error('Failed to register global shortcut:', error);
    // Try fallback shortcut
    try {
      globalShortcut.register('CmdOrCtrl+Shift+Space', () => {
        toggleQuickPrompt();
      });
    } catch (fallbackError) {
      console.error('Failed to register fallback shortcut:', fallbackError);
    }
  }
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

// IPC handlers for quick prompt
ipcMain.on('hide-quick-prompt', () => {
  hideQuickPrompt();
});

ipcMain.on('open-in-main-window', (event, { message, response }) => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
    mainWindow.webContents.send('continue-chat', { message, response });
  }
  hideQuickPrompt();
});

// App lifecycle
app.whenReady().then(() => {
  createWindow();
  createMenu();
  createTray();
  registerGlobalShortcuts();

  // Handle theme changes
  nativeTheme.on('updated', () => {
    mainWindow?.webContents.send('theme-changed',
      nativeTheme.shouldUseDarkColors ? 'dark' : 'light'
    );
    quickPromptWindow?.webContents.send('theme-changed',
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

app.on('will-quit', () => {
  // Unregister all shortcuts
  globalShortcut.unregisterAll();
});
