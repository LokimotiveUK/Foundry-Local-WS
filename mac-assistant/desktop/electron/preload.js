/**
 * Mac Assistant - Preload Script
 *
 * Exposes safe APIs to the renderer process via contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer
contextBridge.exposeInMainWorld('electronAPI', {
  // Settings
  getSettings: () => ipcRenderer.invoke('get-settings'),
  setSettings: (settings) => ipcRenderer.invoke('set-settings', settings),
  getTheme: () => ipcRenderer.invoke('get-theme'),

  // Event listeners
  onNewChat: (callback) => ipcRenderer.on('new-chat', callback),
  onOpenSettings: (callback) => ipcRenderer.on('open-settings', callback),
  onToggleSidebar: (callback) => ipcRenderer.on('toggle-sidebar', callback),
  onToggleMetrics: (callback) => ipcRenderer.on('toggle-metrics', callback),
  onSelectPocket: (callback) => ipcRenderer.on('select-pocket', (_, pocket) => callback(pocket)),
  onThemeChanged: (callback) => ipcRenderer.on('theme-changed', (_, theme) => callback(theme)),
  onExportData: (callback) => ipcRenderer.on('export-data', callback),
  onImportData: (callback) => ipcRenderer.on('import-data', callback),
  onContinueChat: (callback) => ipcRenderer.on('continue-chat', (_, data) => callback(data)),

  // Quick Prompt
  hideQuickPrompt: () => ipcRenderer.send('hide-quick-prompt'),
  openInMainWindow: (message, response) => ipcRenderer.send('open-in-main-window', { message, response }),
  onQuickPromptHidden: (callback) => ipcRenderer.on('quick-prompt-hidden', callback),

  // Cleanup
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
});

// Expose platform info
contextBridge.exposeInMainWorld('platform', {
  isMac: process.platform === 'darwin',
  isWindows: process.platform === 'win32',
  isLinux: process.platform === 'linux',
});
