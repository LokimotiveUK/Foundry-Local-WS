/**
 * Mac Assistant - Frontend Application
 *
 * Handles UI interactions, API communication, and real-time streaming.
 */

class MacAssistant {
  constructor() {
    // State
    this.currentSessionId = null;
    this.currentPocket = null;
    this.sessions = [];
    this.isStreaming = false;
    this.abortController = null;
    this.settings = {
      apiPort: 8000,
      temperature: 0.7,
      maxTokens: 2048,
      contextWindow: 10,
      verbose: true,
      theme: 'system',
      whisperModel: 'base',
    };

    // API base URL
    this.apiBase = `http://localhost:${this.settings.apiPort}`;

    // DOM Elements
    this.elements = {};

    // Audio recording state
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.isTranscribing = false;
    this.recordingStartTime = null;

    // Document manager state
    this.docManagerPocket = null;
    this.documents = [];
    this.pocketStats = {};
    this.pockets = [];
    this.moveDocFilename = null;

    // Folders & Tags state
    this.folders = [];
    this.tags = [];
    this.expandedFolders = new Set();  // Track which folders are expanded
    this.currentTagId = null;     // Filter by tag
    this.contextMenuSessionId = null;  // Session for context menu
    this.contextMenuFolderId = null;  // Folder for context menu

    // Chat attachments state
    this.attachments = [];  // Array of { file: File, name: string, type: string, size: number }

    // Projects state
    this.projects = [];
    this.currentProjectId = null;  // null = "All Chats"

    // Folder watchers state
    this.watchers = [];

    // Initialize
    this.init();
  }

  async init() {
    this.cacheElements();
    this.bindEvents();
    await this.loadSettings();
    await this.checkConnection();
    await this.loadPocketsForSidebar();
    await this.loadProjects();
    await this.loadFolders();
    await this.loadTags();
    await this.loadSessions();
    this.setupElectronListeners();
  }

  async loadPocketsForSidebar() {
    try {
      this.pockets = await this.apiRequest('/rag/pockets');
      this.updateMainPocketSelector();
    } catch (error) {
      console.error('Failed to load pockets:', error);
    }
  }

  cacheElements() {
    this.elements = {
      // Connection
      connectionStatus: document.getElementById('connectionStatus'),
      statusDot: document.querySelector('.status-dot'),
      statusText: document.querySelector('.status-text'),

      // Sidebar
      sidebar: document.getElementById('sidebar'),
      newChatBtn: document.getElementById('newChatBtn'),
      pocketSelect: document.getElementById('pocketSelect'),
      sessionsContainer: document.getElementById('sessionsContainer'),
      settingsBtn: document.getElementById('settingsBtn'),

      // Chat
      chatTitle: document.getElementById('chatTitle'),
      chatModel: document.getElementById('chatModel'),
      modelSwitcher: document.querySelector('.model-switcher'),
      modelDropdown: document.getElementById('modelDropdown'),
      modelDropdownList: document.getElementById('modelDropdownList'),
      openModelManagerFromDropdown: document.getElementById('openModelManagerFromDropdown'),
      toggleMetricsBtn: document.getElementById('toggleMetricsBtn'),
      messagesContainer: document.getElementById('messagesContainer'),
      messages: document.getElementById('messages'),
      welcomeMessage: document.getElementById('welcomeMessage'),
      metricsPanel: document.getElementById('metricsPanel'),
      tokensPerSec: document.getElementById('tokensPerSec'),
      tokenCount: document.getElementById('tokenCount'),
      responseTime: document.getElementById('responseTime'),

      // Input
      messageInput: document.getElementById('messageInput'),
      sendBtn: document.getElementById('sendBtn'),
      stopBtn: document.getElementById('stopBtn'),
      micBtn: document.getElementById('micBtn'),
      pocketIndicator: document.getElementById('pocketIndicator'),
      recordingIndicator: document.getElementById('recordingIndicator'),
      charCount: document.getElementById('charCount'),

      // Settings Modal
      settingsModal: document.getElementById('settingsModal'),
      closeSettingsBtn: document.getElementById('closeSettingsBtn'),
      modelSelect: document.getElementById('modelSelect'),
      temperatureSlider: document.getElementById('temperatureSlider'),
      tempValue: document.getElementById('tempValue'),
      maxTokensInput: document.getElementById('maxTokensInput'),
      contextWindowInput: document.getElementById('contextWindowInput'),
      verboseCheckbox: document.getElementById('verboseCheckbox'),
      themeSelect: document.getElementById('themeSelect'),
      whisperModelSelect: document.getElementById('whisperModelSelect'),
      apiPortInput: document.getElementById('apiPortInput'),
      cancelSettingsBtn: document.getElementById('cancelSettingsBtn'),
      saveSettingsBtn: document.getElementById('saveSettingsBtn'),

      // Sources Modal
      sourcesModal: document.getElementById('sourcesModal'),
      closeSourcesBtn: document.getElementById('closeSourcesBtn'),
      sourcesContent: document.getElementById('sourcesContent'),

      // Document Manager Modal
      manageDocsBtn: document.getElementById('manageDocsBtn'),
      docManagerModal: document.getElementById('docManagerModal'),
      closeDocManagerBtn: document.getElementById('closeDocManagerBtn'),
      pocketTabs: document.getElementById('pocketTabs'),
      addPocketBtn: document.getElementById('addPocketBtn'),
      deletePocketBtn: document.getElementById('deletePocketBtn'),
      statDocCount: document.getElementById('statDocCount'),
      statChunkCount: document.getElementById('statChunkCount'),
      statTotalSize: document.getElementById('statTotalSize'),
      statStatus: document.getElementById('statStatus'),
      uploadZone: document.getElementById('uploadZone'),
      fileInput: document.getElementById('fileInput'),
      uploadProgress: document.getElementById('uploadProgress'),
      progressFill: document.getElementById('progressFill'),
      progressText: document.getElementById('progressText'),
      refreshDocsBtn: document.getElementById('refreshDocsBtn'),
      ingestAllBtn: document.getElementById('ingestAllBtn'),
      docList: document.getElementById('docList'),

      // Create Pocket Modal
      createPocketModal: document.getElementById('createPocketModal'),
      closeCreatePocketBtn: document.getElementById('closeCreatePocketBtn'),
      newPocketId: document.getElementById('newPocketId'),
      newPocketName: document.getElementById('newPocketName'),
      newPocketDescription: document.getElementById('newPocketDescription'),
      newPocketColor: document.getElementById('newPocketColor'),
      cancelCreatePocketBtn: document.getElementById('cancelCreatePocketBtn'),
      confirmCreatePocketBtn: document.getElementById('confirmCreatePocketBtn'),

      // Move Document Modal
      moveDocModal: document.getElementById('moveDocModal'),
      closeMoveDocBtn: document.getElementById('closeMoveDocBtn'),
      moveDocName: document.getElementById('moveDocName'),
      moveTargetPocket: document.getElementById('moveTargetPocket'),
      cancelMoveDocBtn: document.getElementById('cancelMoveDocBtn'),
      confirmMoveDocBtn: document.getElementById('confirmMoveDocBtn'),

      // Model Manager Modal
      modelManagerModal: document.getElementById('modelManagerModal'),
      closeModelManagerBtn: document.getElementById('closeModelManagerBtn'),
      currentModelName: document.getElementById('currentModelName'),
      modelFilter: document.getElementById('modelFilter'),
      refreshModelsBtn: document.getElementById('refreshModelsBtn'),
      modelsList: document.getElementById('modelsList'),

      // Folders & Tags
      foldersList: document.getElementById('foldersList'),
      tagsList: document.getElementById('tagsList'),
      addFolderBtn: document.getElementById('addFolderBtn'),
      addTagBtn: document.getElementById('addTagBtn'),
      sessionsLabel: document.getElementById('sessionsLabel'),
      clearFilterBtn: document.getElementById('clearFilterBtn'),

      // Create Folder Modal
      createFolderModal: document.getElementById('createFolderModal'),
      folderModalTitle: document.getElementById('folderModalTitle'),
      closeCreateFolderBtn: document.getElementById('closeCreateFolderBtn'),
      folderNameInput: document.getElementById('folderNameInput'),
      folderColorInput: document.getElementById('folderColorInput'),
      folderColorPicker: document.getElementById('folderColorPicker'),
      cancelCreateFolderBtn: document.getElementById('cancelCreateFolderBtn'),
      confirmCreateFolderBtn: document.getElementById('confirmCreateFolderBtn'),

      // Create Tag Modal
      createTagModal: document.getElementById('createTagModal'),
      tagModalTitle: document.getElementById('tagModalTitle'),
      closeCreateTagBtn: document.getElementById('closeCreateTagBtn'),
      tagNameInput: document.getElementById('tagNameInput'),
      tagColorInput: document.getElementById('tagColorInput'),
      tagColorPicker: document.getElementById('tagColorPicker'),
      cancelCreateTagBtn: document.getElementById('cancelCreateTagBtn'),
      confirmCreateTagBtn: document.getElementById('confirmCreateTagBtn'),

      // Context Menu
      sessionContextMenu: document.getElementById('sessionContextMenu'),
      pinMenuText: document.getElementById('pinMenuText'),

      // Move to Folder Modal
      moveToFolderModal: document.getElementById('moveToFolderModal'),
      closeMoveToFolderBtn: document.getElementById('closeMoveToFolderBtn'),
      folderSelectList: document.getElementById('folderSelectList'),

      // Move to Project Modal
      moveToProjectModal: document.getElementById('moveToProjectModal'),
      closeMoveToProjectBtn: document.getElementById('closeMoveToProjectBtn'),
      projectSelectList: document.getElementById('projectSelectList'),

      // Folder Context Menu
      folderContextMenu: document.getElementById('folderContextMenu'),

      // Assign Folder to Project Modal
      assignFolderToProjectModal: document.getElementById('assignFolderToProjectModal'),
      closeAssignFolderBtn: document.getElementById('closeAssignFolderBtn'),
      folderProjectSelectList: document.getElementById('folderProjectSelectList'),

      // Edit Tags Modal
      editTagsModal: document.getElementById('editTagsModal'),
      closeEditTagsBtn: document.getElementById('closeEditTagsBtn'),
      tagsSelectList: document.getElementById('tagsSelectList'),
      createTagFromEditBtn: document.getElementById('createTagFromEditBtn'),
      saveTagsBtn: document.getElementById('saveTagsBtn'),

      // Chat Attachments
      inputArea: document.getElementById('inputArea'),
      attachBtn: document.getElementById('attachBtn'),
      chatFileInput: document.getElementById('chatFileInput'),
      attachmentsArea: document.getElementById('attachmentsArea'),
      attachmentsList: document.getElementById('attachmentsList'),
      attachmentIndicator: document.getElementById('attachmentIndicator'),

      // Projects
      projectSwitcher: document.getElementById('projectSwitcher'),
      projectCurrent: document.getElementById('projectCurrent'),
      projectDropdown: document.getElementById('projectDropdown'),
      projectDropdownList: document.getElementById('projectDropdownList'),
      addProjectBtn: document.getElementById('addProjectBtn'),
      createProjectModal: document.getElementById('createProjectModal'),
      closeProjectModalBtn: document.getElementById('closeProjectModalBtn'),
      projectNameInput: document.getElementById('projectNameInput'),
      projectDescInput: document.getElementById('projectDescInput'),
      projectColorPicker: document.getElementById('projectColorPicker'),
      projectColorInput: document.getElementById('projectColorInput'),
      projectPocketSelect: document.getElementById('projectPocketSelect'),
      projectPromptInput: document.getElementById('projectPromptInput'),
      cancelProjectBtn: document.getElementById('cancelProjectBtn'),
      saveProjectBtn: document.getElementById('saveProjectBtn'),

      // Folder Watchers
      openWatchersBtn: document.getElementById('openWatchersBtn'),
      watchersModal: document.getElementById('watchersModal'),
      closeWatchersBtn: document.getElementById('closeWatchersBtn'),
      watcherStatus: document.getElementById('watcherStatus'),
      watcherServiceStatus: document.getElementById('watcherServiceStatus'),
      addWatcherBtn: document.getElementById('addWatcherBtn'),
      watchersList: document.getElementById('watchersList'),
      watcherFormModal: document.getElementById('watcherFormModal'),
      watcherFormTitle: document.getElementById('watcherFormTitle'),
      closeWatcherFormBtn: document.getElementById('closeWatcherFormBtn'),
      watcherEditId: document.getElementById('watcherEditId'),
      watcherNameInput: document.getElementById('watcherNameInput'),
      watcherPathInput: document.getElementById('watcherPathInput'),
      browseWatcherPathBtn: document.getElementById('browseWatcherPathBtn'),
      watcherPocketSelect: document.getElementById('watcherPocketSelect'),
      watcherPatternsInput: document.getElementById('watcherPatternsInput'),
      watcherRecursiveCheck: document.getElementById('watcherRecursiveCheck'),
      watcherInitialScanCheck: document.getElementById('watcherInitialScanCheck'),
      cancelWatcherFormBtn: document.getElementById('cancelWatcherFormBtn'),
      saveWatcherBtn: document.getElementById('saveWatcherBtn'),

      // Model Switch Progress Modal
      switchProgressModal: document.getElementById('switchProgressModal'),
      switchFromModel: document.getElementById('switchFromModel'),
      switchToModel: document.getElementById('switchToModel'),
      phaseUnload: document.getElementById('phaseUnload'),
      phaseDownload: document.getElementById('phaseDownload'),
      phaseLoad: document.getElementById('phaseLoad'),
      switchProgressFill: document.getElementById('switchProgressFill'),
      switchStatusText: document.getElementById('switchStatusText'),
      cancelSwitchBtn: document.getElementById('cancelSwitchBtn'),
      switchError: document.getElementById('switchError'),
      switchErrorText: document.getElementById('switchErrorText'),
      switchRetryBtn: document.getElementById('switchRetryBtn'),
      downloadDetail: document.getElementById('downloadDetail'),
    };

    // Switch state tracking
    this._switchPollInterval = null;
    this._pendingSwitchModel = null;
  }

  bindEvents() {
    // New chat
    this.elements.newChatBtn.addEventListener('click', () => this.newChat());

    // Pocket selection
    this.elements.pocketSelect.addEventListener('change', (e) => {
      this.currentPocket = e.target.value || null;
      this.updatePocketIndicator();
    });

    // Settings
    this.elements.settingsBtn.addEventListener('click', () => this.openSettings());
    this.elements.closeSettingsBtn.addEventListener('click', () => this.closeSettings());
    this.elements.cancelSettingsBtn.addEventListener('click', () => this.closeSettings());
    this.elements.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

    // Sources modal
    this.elements.closeSourcesBtn.addEventListener('click', () => this.closeSourcesModal());

    // Modal backdrop clicks
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
      backdrop.addEventListener('click', () => {
        this.closeSettings();
        this.closeSourcesModal();
        this.closeDocManager();
        this.closeModelManager();
      });
    });

    // Message input
    this.elements.messageInput.addEventListener('input', () => this.handleInputChange());
    this.elements.messageInput.addEventListener('keydown', (e) => this.handleInputKeydown(e));
    this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
    this.elements.stopBtn.addEventListener('click', () => this.stopGeneration());

    // Microphone button - click to toggle recording
    this.elements.micBtn.addEventListener('click', () => this.toggleRecording());

    // Temperature slider
    this.elements.temperatureSlider.addEventListener('input', (e) => {
      this.elements.tempValue.textContent = e.target.value;
    });

    // Metrics toggle
    this.elements.toggleMetricsBtn.addEventListener('click', () => this.toggleMetrics());

    // Theme selection
    this.elements.themeSelect.addEventListener('change', (e) => this.setTheme(e.target.value));

    // Document Manager
    this.elements.manageDocsBtn.addEventListener('click', () => this.openDocManager());
    this.elements.closeDocManagerBtn.addEventListener('click', () => this.closeDocManager());
    this.elements.refreshDocsBtn.addEventListener('click', () => this.loadDocuments());
    this.elements.ingestAllBtn.addEventListener('click', () => this.ingestAllDocuments());
    this.elements.addPocketBtn.addEventListener('click', () => this.openCreatePocket());
    this.elements.deletePocketBtn.addEventListener('click', () => this.deletePocket());

    // File upload
    this.elements.fileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files));

    // Drag and drop
    this.elements.uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.elements.uploadZone.classList.add('drag-over');
    });
    this.elements.uploadZone.addEventListener('dragleave', () => {
      this.elements.uploadZone.classList.remove('drag-over');
    });
    this.elements.uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      this.elements.uploadZone.classList.remove('drag-over');
      this.handleFileSelect(e.dataTransfer.files);
    });

    // Create Pocket Modal
    this.elements.closeCreatePocketBtn.addEventListener('click', () => this.closeCreatePocket());
    this.elements.cancelCreatePocketBtn.addEventListener('click', () => this.closeCreatePocket());
    this.elements.confirmCreatePocketBtn.addEventListener('click', () => this.createPocket());

    // Color picker
    document.querySelectorAll('.color-option').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.color-option').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        this.elements.newPocketColor.value = btn.dataset.color;
      });
    });

    // Move Document Modal
    this.elements.closeMoveDocBtn.addEventListener('click', () => this.closeMoveDoc());
    this.elements.cancelMoveDocBtn.addEventListener('click', () => this.closeMoveDoc());
    this.elements.confirmMoveDocBtn.addEventListener('click', () => this.confirmMoveDocument());

    // Model Switcher Dropdown
    this.elements.chatModel.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleModelDropdown();
    });
    this.elements.openModelManagerFromDropdown.addEventListener('click', (e) => {
      e.stopPropagation();
      this.closeModelDropdown();
      this.openModelManager();
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!this.elements.modelSwitcher.contains(e.target)) {
        this.closeModelDropdown();
      }
    });

    // Model Manager Modal
    this.elements.closeModelManagerBtn.addEventListener('click', () => this.closeModelManager());
    this.elements.modelFilter.addEventListener('change', () => this.renderModelsList());
    this.elements.refreshModelsBtn.addEventListener('click', () => this.loadAllModels());

    // === Folders & Tags Events ===

    // Add folder/tag buttons
    this.elements.addFolderBtn?.addEventListener('click', () => this.openCreateFolderModal());
    this.elements.addTagBtn?.addEventListener('click', () => this.openCreateTagModal());
    this.elements.clearFilterBtn?.addEventListener('click', () => this.clearFilter());

    // Create Folder Modal
    this.elements.closeCreateFolderBtn?.addEventListener('click', () => this.closeCreateFolderModal());
    this.elements.cancelCreateFolderBtn?.addEventListener('click', () => this.closeCreateFolderModal());
    this.elements.confirmCreateFolderBtn?.addEventListener('click', () => this.createFolder());

    // Create Tag Modal
    this.elements.closeCreateTagBtn?.addEventListener('click', () => this.closeCreateTagModal());
    this.elements.cancelCreateTagBtn?.addEventListener('click', () => this.closeCreateTagModal());
    this.elements.confirmCreateTagBtn?.addEventListener('click', () => this.createTag());

    // Color picker for folder/tag modals
    this.elements.folderColorPicker?.addEventListener('click', (e) => {
      if (e.target.classList.contains('color-option')) {
        this.elements.folderColorPicker.querySelectorAll('.color-option').forEach(btn => btn.classList.remove('selected'));
        e.target.classList.add('selected');
        this.elements.folderColorInput.value = e.target.dataset.color;
      }
    });
    this.elements.tagColorPicker?.addEventListener('click', (e) => {
      if (e.target.classList.contains('color-option')) {
        this.elements.tagColorPicker.querySelectorAll('.color-option').forEach(btn => btn.classList.remove('selected'));
        e.target.classList.add('selected');
        this.elements.tagColorInput.value = e.target.dataset.color;
      }
    });

    // Move to Folder Modal
    this.elements.closeMoveToFolderBtn?.addEventListener('click', () => this.closeMoveToFolderModal());

    // Move to Project Modal
    this.elements.closeMoveToProjectBtn?.addEventListener('click', () => this.closeMoveToProjectModal());

    // Folder Context Menu
    document.addEventListener('click', () => this.hideFolderContextMenu());
    this.elements.folderContextMenu?.addEventListener('click', (e) => {
      const item = e.target.closest('.context-menu-item');
      if (item) {
        const action = item.dataset.action;
        this.handleFolderContextMenuAction(action);
      }
    });

    // Assign Folder to Project Modal
    this.elements.closeAssignFolderBtn?.addEventListener('click', () => this.closeAssignFolderToProjectModal());

    // Edit Tags Modal
    this.elements.closeEditTagsBtn?.addEventListener('click', () => this.closeEditTagsModal());
    this.elements.saveTagsBtn?.addEventListener('click', () => this.closeEditTagsModal());
    this.elements.createTagFromEditBtn?.addEventListener('click', () => {
      this.closeEditTagsModal();
      this.openCreateTagModal();
    });

    // Context Menu - hide on click outside
    document.addEventListener('click', () => this.hideContextMenu());
    this.elements.sessionContextMenu?.addEventListener('click', (e) => {
      const item = e.target.closest('.context-menu-item');
      if (item) {
        const action = item.dataset.action;
        this.handleContextMenuAction(action);
      }
    });

    // === Chat Attachments Events ===

    // Attach button
    this.elements.attachBtn?.addEventListener('click', () => {
      this.elements.chatFileInput?.click();
    });

    // File input change
    this.elements.chatFileInput?.addEventListener('change', (e) => {
      this.handleChatAttachments(e.target.files);
      e.target.value = ''; // Reset to allow re-selecting same file
    });

    // Drag and drop on input area
    this.elements.inputArea?.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.elements.inputArea.classList.add('drag-over');
    });
    this.elements.inputArea?.addEventListener('dragleave', (e) => {
      e.preventDefault();
      this.elements.inputArea.classList.remove('drag-over');
    });
    this.elements.inputArea?.addEventListener('drop', (e) => {
      e.preventDefault();
      this.elements.inputArea.classList.remove('drag-over');
      this.handleChatAttachments(e.dataTransfer.files);
    });

    // === Projects Events ===

    // Project switcher toggle
    this.elements.projectCurrent?.addEventListener('click', () => {
      this.elements.projectSwitcher?.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!this.elements.projectSwitcher?.contains(e.target)) {
        this.elements.projectSwitcher?.classList.remove('open');
      }
    });

    // Add project button
    this.elements.addProjectBtn?.addEventListener('click', () => this.openCreateProjectModal());
    this.elements.closeProjectModalBtn?.addEventListener('click', () => this.closeCreateProjectModal());
    this.elements.cancelProjectBtn?.addEventListener('click', () => this.closeCreateProjectModal());
    this.elements.saveProjectBtn?.addEventListener('click', () => this.createProject());
    this.elements.createProjectModal?.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeCreateProjectModal());

    // Project color picker
    this.elements.projectColorPicker?.querySelectorAll('.color-option').forEach(btn => {
      btn.addEventListener('click', () => {
        this.elements.projectColorPicker.querySelectorAll('.color-option').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        this.elements.projectColorInput.value = btn.dataset.color;
      });
    });

    // Folder Watchers
    this.elements.openWatchersBtn?.addEventListener('click', () => this.openWatchersModal());
    this.elements.closeWatchersBtn?.addEventListener('click', () => this.closeWatchersModal());
    this.elements.watchersModal?.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeWatchersModal());
    this.elements.addWatcherBtn?.addEventListener('click', () => this.openWatcherForm());
    this.elements.closeWatcherFormBtn?.addEventListener('click', () => this.closeWatcherForm());
    this.elements.cancelWatcherFormBtn?.addEventListener('click', () => this.closeWatcherForm());
    this.elements.saveWatcherBtn?.addEventListener('click', () => this.saveWatcher());
    this.elements.watcherFormModal?.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeWatcherForm());
  }

  setupElectronListeners() {
    if (!window.electronAPI) return;

    window.electronAPI.onNewChat(() => this.newChat());
    window.electronAPI.onOpenSettings(() => this.openSettings());
    window.electronAPI.onToggleSidebar(() => this.toggleSidebar());
    window.electronAPI.onToggleMetrics(() => this.toggleMetrics());
    window.electronAPI.onSelectPocket((pocket) => {
      this.elements.pocketSelect.value = pocket || '';
      this.currentPocket = pocket;
      this.updatePocketIndicator();
    });
    window.electronAPI.onThemeChanged((theme) => this.applyTheme(theme));

    // Handle "continue chat" from quick prompt
    window.electronAPI.onContinueChat?.(({ message, response }) => {
      this.continueFromQuickPrompt(message, response);
    });
  }

  // Continue chat from quick prompt window
  async continueFromQuickPrompt(message, response) {
    // Start a new chat with the message and response already populated
    await this.newChat();

    // Add the user message
    this.addMessageToUI('user', message);

    // Add the assistant response
    this.addMessageToUI('assistant', response);

    // Store in session if we have one
    if (this.currentSessionId) {
      try {
        await this.apiRequest('/chat/messages', {
          method: 'POST',
          body: JSON.stringify({
            session_id: this.currentSessionId,
            role: 'user',
            content: message,
          }),
        });

        await this.apiRequest('/chat/messages', {
          method: 'POST',
          body: JSON.stringify({
            session_id: this.currentSessionId,
            role: 'assistant',
            content: response,
          }),
        });
      } catch (error) {
        console.error('Failed to save continued chat:', error);
      }
    }
  }

  // === API Communication ===

  async apiRequest(endpoint, options = {}) {
    const url = `${this.apiBase}${endpoint}`;
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error (${endpoint}):`, error);
      throw error;
    }
  }

  async checkConnection() {
    try {
      const health = await this.apiRequest('/health');
      this.updateConnectionStatus(health.foundry_running, health.current_model);

      if (health.current_model) {
        this.elements.chatModel.textContent = health.current_model;
      }

      // Load models for settings
      if (health.foundry_running) {
        await this.loadModels();
      }
    } catch (error) {
      this.updateConnectionStatus(false);
    }

    // Poll connection status
    setTimeout(() => this.checkConnection(), 5000);
  }

  updateConnectionStatus(connected, model = null) {
    this.elements.statusDot.classList.toggle('connected', connected);
    this.elements.statusDot.classList.toggle('error', !connected);

    if (connected) {
      this.elements.statusText.textContent = model || 'Connected';
    } else {
      this.elements.statusText.textContent = 'Disconnected';
    }
  }

  async loadModels() {
    try {
      const models = await this.apiRequest('/models?cached_only=true');
      const current = await this.apiRequest('/models/current').catch(() => null);

      // Update settings dropdown
      this.elements.modelSelect.innerHTML = '';
      models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.alias;
        option.textContent = `${model.alias} (${this.formatModelSize(model.model_size)})`;
        option.selected = current && model.alias === current.alias;
        this.elements.modelSelect.appendChild(option);
      });

      // Update header model name
      const modelNameSpan = this.elements.chatModel.querySelector('.model-name');
      if (modelNameSpan && current) {
        modelNameSpan.textContent = current.alias;
      }
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  }

  formatModelSize(sizeMB) {
    if (!sizeMB || sizeMB === 0) {
      return 'Unknown size';
    }
    if (sizeMB >= 1000) {
      return `${(sizeMB / 1000).toFixed(1)} GB`;
    }
    return `${sizeMB} MB`;
  }

  // === Session Management ===

  async loadSessions() {
    try {
      // Build query params for filtering
      const params = new URLSearchParams();
      if (this.currentProjectId) {
        params.append('project_id', this.currentProjectId);
      }
      if (this.currentTagId) {
        params.append('tag_id', this.currentTagId);
      }

      const queryString = params.toString();
      const url = queryString ? `/chat/sessions?${queryString}` : '/chat/sessions';

      this.sessions = await this.apiRequest(url);
      // Render both folders (with updated counts) and sessions
      this.renderFolders();
      this.renderSessions();
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }

  renderSessions() {
    const container = this.elements.sessionsContainer;
    container.innerHTML = '';

    // Only render root-level sessions (sessions not in any folder)
    // Folder sessions are rendered in the FOLDERS section via renderFolders()
    const rootSessions = this.sessions.filter(session => !session.folder_id);

    if (rootSessions.length === 0) {
      container.innerHTML = '<p class="no-sessions">No chats found</p>';
      return;
    }

    rootSessions.forEach(session => {
      container.appendChild(this.createSessionItem(session, false));
    });
  }

  createSessionItem(session, isNested = false) {
    const item = document.createElement('div');
    item.className = `session-item${session.id === this.currentSessionId ? ' active' : ''}${session.is_pinned ? ' pinned' : ''}${isNested ? ' nested' : ''}`;
    item.dataset.sessionId = session.id;

    const date = new Date(session.updated_at);
    const timeStr = date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });

    // Build tags HTML if session has tags
    const tagsHtml = session.tags && session.tags.length > 0
      ? `<div class="session-tags">${session.tags.map(tag =>
          `<span class="session-tag" style="background: ${tag.color || '#007AFF'}20; color: ${tag.color || '#007AFF'}">${this.escapeHtml(tag.name)}</span>`
        ).join('')}</div>`
      : '';

    // Pinned icon
    const pinnedIcon = session.is_pinned
      ? `<span class="pin-icon" title="Pinned">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" stroke="none">
            <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>
          </svg>
        </span>`
      : '';

    item.innerHTML = `
      <div class="session-content">
        <div class="session-title-row">
          ${pinnedIcon}
          <div class="session-title">${this.escapeHtml(session.title)}</div>
        </div>
        <div class="session-meta">
          <span>${timeStr}</span>
          ${session.rag_pocket ? `<span class="session-pocket">${session.rag_pocket}</span>` : ''}
        </div>
        ${tagsHtml}
      </div>
      <button class="session-menu-btn" title="More options">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="1"></circle>
          <circle cx="12" cy="5" r="1"></circle>
          <circle cx="12" cy="19" r="1"></circle>
        </svg>
      </button>
    `;

    // Click on session content to load
    item.querySelector('.session-content').addEventListener('click', () => this.loadSession(session.id));

    // Click on menu button to show context menu
    item.querySelector('.session-menu-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.showContextMenu(e, session.id);
    });

    // Right-click to show context menu
    item.addEventListener('contextmenu', (e) => {
      this.showContextMenu(e, session.id);
    });

    return item;
  }

  toggleFolderExpand(folderId) {
    if (this.expandedFolders.has(folderId)) {
      this.expandedFolders.delete(folderId);
    } else {
      this.expandedFolders.add(folderId);
    }
    this.renderFolders();
    this.renderSessions();
  }

  async deleteSession(sessionId) {
    if (!confirm('Delete this chat? This cannot be undone.')) {
      return;
    }

    try {
      await this.apiRequest(`/chat/sessions/${sessionId}`, { method: 'DELETE' });

      // Remove from local array
      this.sessions = this.sessions.filter(s => s.id !== sessionId);

      // If we deleted the current session, start a new chat
      if (sessionId === this.currentSessionId) {
        this.newChat();
      }

      this.renderSessions();
    } catch (error) {
      console.error('Failed to delete session:', error);
      alert('Failed to delete chat. Please try again.');
    }
  }

  async loadSession(sessionId) {
    try {
      const session = await this.apiRequest(`/chat/sessions/${sessionId}`);
      this.currentSessionId = sessionId;
      this.currentPocket = session.rag_pocket;

      // Update UI
      this.elements.chatTitle.textContent = session.title;
      this.elements.pocketSelect.value = session.rag_pocket || '';
      this.updatePocketIndicator();

      // Render messages
      this.elements.welcomeMessage.style.display = 'none';
      this.elements.messages.innerHTML = '';

      session.messages.forEach(msg => {
        this.addMessageToUI(msg.role, msg.content);
      });

      // Update session list
      this.renderSessions();

      // Scroll to bottom
      this.scrollToBottom();
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  }

  newChat() {
    this.currentSessionId = null;
    this.elements.chatTitle.textContent = 'New Chat';
    this.elements.messages.innerHTML = '';
    this.elements.welcomeMessage.style.display = 'block';
    this.clearMetrics();
    this.renderSessions();
  }

  // === Messaging ===

  handleInputChange() {
    const input = this.elements.messageInput;
    const value = input.value;

    // Update char count
    this.elements.charCount.textContent = value.length;

    // Enable/disable send button
    this.elements.sendBtn.disabled = !value.trim() || this.isStreaming;

    // Auto-resize textarea
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
  }

  handleInputKeydown(e) {
    // Enter to send, Shift+Enter for new line
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.sendMessage();
    }
    // Shift+Enter allows default behavior (new line)
  }

  async sendMessage() {
    const message = this.elements.messageInput.value.trim();
    if (!message || this.isStreaming) return;

    // Capture attachments before clearing
    const currentAttachments = [...this.attachments];

    // Clear input and attachments
    this.elements.messageInput.value = '';
    this.handleInputChange();
    this.clearAttachments();

    // Hide welcome message
    this.elements.welcomeMessage.style.display = 'none';

    // Add user message to UI (with attachment badges if any)
    const attachmentBadges = currentAttachments.length > 0
      ? `<div class="message-attachments">${currentAttachments.map(a =>
          `<span class="message-attachment-badge">${this.getAttachmentIcon(a.type)} ${this.escapeHtml(a.name)}</span>`
        ).join('')}</div>`
      : '';
    this.addMessageToUI('user', message, false, attachmentBadges);

    // Create assistant message placeholder
    const assistantDiv = this.addMessageToUI('assistant', '', true);
    const bubbleDiv = assistantDiv.querySelector('.message-bubble');

    this.isStreaming = true;
    this.elements.sendBtn.disabled = true;
    this.elements.sendBtn.style.display = 'none';
    this.elements.stopBtn.style.display = 'flex';

    // Create AbortController for this request
    this.abortController = new AbortController();

    try {
      await this.streamResponse(message, bubbleDiv, currentAttachments);
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Stream aborted by user');
        // Append stopped indicator to existing content
        const currentContent = bubbleDiv.innerHTML;
        if (currentContent) {
          bubbleDiv.innerHTML = currentContent + '<span style="color: var(--text-muted); font-style: italic;"> [Stopped]</span>';
        }
      } else {
        console.error('Stream error:', error);
        bubbleDiv.innerHTML = `<span style="color: var(--error-color)">Error: ${error.message}</span>`;
      }
    } finally {
      this.isStreaming = false;
      this.abortController = null;
      this.elements.sendBtn.style.display = 'flex';
      this.elements.stopBtn.style.display = 'none';
      this.handleInputChange();
    }

    // Refresh sessions list
    await this.loadSessions();
  }

  stopGeneration() {
    if (this.abortController) {
      this.abortController.abort();
    }
  }

  async streamResponse(message, bubbleDiv, attachments = []) {
    // Process attachments - read file contents
    const processedAttachments = [];
    for (const att of attachments) {
      try {
        // For text-based files, read as text; for binary, read as base64
        const textTypes = ['.txt', '.md', '.json', '.csv', '.py', '.js', '.ts', '.html', '.css', '.xml', '.yaml', '.yml'];
        const isText = textTypes.includes(att.type);

        const content = isText
          ? await this.readFileAsText(att.file)
          : await this.readFileAsBase64(att.file);

        processedAttachments.push({
          filename: att.name,
          content,
          content_type: isText ? 'text' : 'base64',
          file_type: att.type,
        });
      } catch (error) {
        console.error(`Failed to read attachment ${att.name}:`, error);
      }
    }

    const body = {
      message,
      session_id: this.currentSessionId,
      rag_pocket: this.currentPocket,
      temperature: this.settings.temperature,
      max_tokens: this.settings.maxTokens,
      include_history: true,
      attachments: processedAttachments.length > 0 ? processedAttachments : undefined,
    };

    const response = await fetch(`${this.apiBase}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: this.abortController?.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullContent = '';
    let sources = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('event: sources')) {
          continue;
        }

        if (line.startsWith('event: metadata')) {
          continue;
        }

        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.sources) {
              sources = data.sources;
              continue;
            }

            if (data.content) {
              fullContent += data.content;
              bubbleDiv.innerHTML = this.formatMessage(fullContent);
              this.scrollToBottom();
            }

            if (data.metrics) {
              this.updateMetrics(data.metrics);
            }

            if (data.session_id && !this.currentSessionId) {
              this.currentSessionId = data.session_id;
            }
          } catch (e) {
            // Ignore parse errors for incomplete JSON
          }
        }
      }
    }

    // Add sources badge if we have sources
    if (sources.length > 0) {
      const sourcesHtml = `
        <div class="sources-badge" onclick="app.showSources(${JSON.stringify(sources).replace(/"/g, '&quot;')})">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          ${sources.length} source${sources.length > 1 ? 's' : ''}
        </div>
      `;
      bubbleDiv.innerHTML += sourcesHtml;
    }
  }

  addMessageToUI(role, content, isStreaming = false, attachmentHtml = '') {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (isStreaming) {
      bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    } else {
      bubble.innerHTML = this.formatMessage(content) + attachmentHtml;
    }

    div.appendChild(bubble);

    const meta = document.createElement('div');
    meta.className = 'message-meta';
    meta.textContent = new Date().toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    });
    div.appendChild(meta);

    this.elements.messages.appendChild(div);
    this.scrollToBottom();

    return div;
  }

  formatMessage(content) {
    // Basic markdown-like formatting
    let html = this.escapeHtml(content);

    // Code blocks
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  scrollToBottom() {
    this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
  }

  // === Metrics ===

  updateMetrics(metrics) {
    if (!metrics) return;

    if (metrics.tokens_per_second !== undefined) {
      this.elements.tokensPerSec.textContent = metrics.tokens_per_second.toFixed(1);
    }
    if (metrics.tokens_generated !== undefined) {
      this.elements.tokenCount.textContent = metrics.tokens_generated;
    }
    if (metrics.total_time !== undefined) {
      this.elements.responseTime.textContent = metrics.total_time.toFixed(2) + 's';
    }
  }

  clearMetrics() {
    this.elements.tokensPerSec.textContent = '--';
    this.elements.tokenCount.textContent = '--';
    this.elements.responseTime.textContent = '--';
  }

  toggleMetrics() {
    const panel = this.elements.metricsPanel;
    const btn = this.elements.toggleMetricsBtn;

    panel.classList.toggle('hidden');
    btn.classList.toggle('active');

    this.settings.verbose = !panel.classList.contains('hidden');
  }

  // === Sources ===

  showSources(sources) {
    const content = this.elements.sourcesContent;
    content.innerHTML = sources.map((source, i) => `
      <div class="source-item">
        <div class="source-header">
          <span class="source-name">${i + 1}. ${this.escapeHtml(source.document)}</span>
          <span class="source-score">Score: ${source.score}</span>
        </div>
        <div class="source-preview">${this.escapeHtml(source.text_preview)}</div>
      </div>
    `).join('');

    this.elements.sourcesModal.classList.add('visible');
  }

  closeSourcesModal() {
    this.elements.sourcesModal.classList.remove('visible');
  }

  // === Settings ===

  async loadSettings() {
    // Try to load from Electron store first
    if (window.electronAPI) {
      try {
        const electronSettings = await window.electronAPI.getSettings();
        this.settings = { ...this.settings, ...electronSettings };
        this.apiBase = `http://localhost:${this.settings.apiPort}`;
      } catch (e) {
        console.error('Failed to load Electron settings:', e);
      }
    }

    // Apply theme
    const theme = this.settings.theme;
    if (theme === 'system' && window.electronAPI) {
      const actualTheme = await window.electronAPI.getTheme();
      this.applyTheme(actualTheme);
    } else {
      this.applyTheme(theme);
    }

    // Update UI elements
    this.elements.temperatureSlider.value = this.settings.temperature;
    this.elements.tempValue.textContent = this.settings.temperature;
    this.elements.maxTokensInput.value = this.settings.maxTokens;
    this.elements.contextWindowInput.value = this.settings.contextWindow;
    this.elements.verboseCheckbox.checked = this.settings.verbose;
    this.elements.themeSelect.value = this.settings.theme;
    this.elements.whisperModelSelect.value = this.settings.whisperModel || 'base';
    this.elements.apiPortInput.value = this.settings.apiPort;

    // Apply verbose setting
    if (!this.settings.verbose) {
      this.elements.metricsPanel.classList.add('hidden');
    }
  }

  openSettings() {
    this.elements.settingsModal.classList.add('visible');
  }

  closeSettings() {
    this.elements.settingsModal.classList.remove('visible');
  }

  // === Model Manager ===

  openModelManager() {
    this.elements.modelManagerModal.classList.add('visible');
    this.loadAllModels();
  }

  closeModelManager() {
    this.elements.modelManagerModal.classList.remove('visible');
  }

  // === Model Dropdown (Quick Switcher) ===

  toggleModelDropdown() {
    const isOpen = this.elements.modelSwitcher.classList.contains('open');
    if (isOpen) {
      this.closeModelDropdown();
    } else {
      this.openModelDropdown();
    }
  }

  async openModelDropdown() {
    this.elements.modelSwitcher.classList.add('open');
    await this.populateModelDropdown();
  }

  closeModelDropdown() {
    this.elements.modelSwitcher.classList.remove('open');
  }

  async populateModelDropdown() {
    const list = this.elements.modelDropdownList;
    list.innerHTML = '<div class="doc-loading">Loading...</div>';

    try {
      const [cachedModels, currentModel] = await Promise.all([
        this.apiRequest('/models?cached_only=true'),
        this.apiRequest('/models/current').catch(() => null)
      ]);

      if (cachedModels.length === 0) {
        list.innerHTML = '<div class="model-dropdown-empty">No downloaded models.<br>Click "Manage All" to download models.</div>';
        return;
      }

      list.innerHTML = '';
      cachedModels.forEach(model => {
        const isCurrent = currentModel && (model.alias === currentModel.alias || model.id === currentModel.id);
        const item = document.createElement('div');
        item.className = `model-dropdown-item${isCurrent ? ' current' : ''}`;

        // Determine icon based on device type
        const isGPU = model.device_type?.toLowerCase().includes('gpu') ||
                      model.execution_provider?.toLowerCase().includes('cuda') ||
                      model.execution_provider?.toLowerCase().includes('coreml');
        const iconSvg = isGPU
          ? `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect></svg>`
          : `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"></rect><rect x="2" y="14" width="20" height="8" rx="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>`;

        item.innerHTML = `
          <div class="model-icon">${iconSvg}</div>
          <div class="model-info">
            <div class="model-name">${model.alias}</div>
            <div class="model-size">${this.formatModelSize(model.model_size)} • ${model.device_type || 'Unknown'}</div>
          </div>
        `;

        if (!isCurrent) {
          item.addEventListener('click', () => {
            this.closeModelDropdown();
            this.switchModel(model.alias, true);
          });
        }

        list.appendChild(item);
      });
    } catch (error) {
      console.error('Failed to load models for dropdown:', error);
      list.innerHTML = '<div class="model-dropdown-empty">Failed to load models</div>';
    }
  }

  async loadAllModels() {
    const modelsList = this.elements.modelsList;
    modelsList.innerHTML = '<div class="doc-loading">Loading models...</div>';

    try {
      // Load all models from catalog and current model
      const [allModels, currentModel] = await Promise.all([
        this.apiRequest('/models'),
        this.apiRequest('/models/current').catch(() => null)
      ]);

      this.allModels = allModels;
      this.currentLoadedModel = currentModel;

      // Update current model display
      if (currentModel) {
        this.elements.currentModelName.textContent = `${currentModel.alias} (${this.formatModelSize(currentModel.model_size)})`;
      } else {
        this.elements.currentModelName.textContent = 'No model loaded';
      }

      this.renderModelsList();

      // Check for any active downloads (in case page was refreshed during download)
      await this.checkActiveDownloads();
    } catch (error) {
      console.error('Failed to load models:', error);
      modelsList.innerHTML = '<div class="error-message">Failed to load models</div>';
    }
  }

  renderModelsList() {
    const modelsList = this.elements.modelsList;
    const filter = this.elements.modelFilter.value;

    let models = this.allModels || [];

    // Apply filter
    if (filter === 'cached') {
      models = models.filter(m => m.is_cached);
    } else if (filter === 'gpu') {
      models = models.filter(m => m.device_type?.toLowerCase().includes('gpu') || m.execution_provider?.toLowerCase().includes('cuda') || m.execution_provider?.toLowerCase().includes('coreml'));
    } else if (filter === 'cpu') {
      models = models.filter(m => m.device_type?.toLowerCase().includes('cpu'));
    }

    if (models.length === 0) {
      modelsList.innerHTML = '<div class="no-items">No models match the filter</div>';
      return;
    }

    modelsList.innerHTML = '';

    models.forEach(model => {
      const item = document.createElement('div');
      item.className = 'model-item';

      const isCurrent = this.currentLoadedModel && (model.alias === this.currentLoadedModel.alias || model.id === this.currentLoadedModel.id);
      const statusClass = isCurrent ? 'loaded' : (model.is_cached ? 'cached' : 'available');
      const statusText = isCurrent ? 'Loaded' : (model.is_cached ? 'Downloaded' : 'Available');

      // Determine icon based on device type
      let iconSvg;
      if (model.device_type?.toLowerCase().includes('gpu') || model.execution_provider?.toLowerCase().includes('cuda') || model.execution_provider?.toLowerCase().includes('coreml')) {
        iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>`;
      } else {
        iconSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>`;
      }

      item.innerHTML = `
        <div class="model-icon">${iconSvg}</div>
        <div class="model-info">
          <div class="model-name">${model.alias}</div>
          <div class="model-details">
            <span>${this.formatModelSize(model.model_size)}</span>
            <span>${model.device_type || 'Unknown'}</span>
            ${model.supports_tool_calling ? '<span class="model-badge">Tools</span>' : ''}
          </div>
        </div>
        <div class="model-status ${statusClass}">${statusText}</div>
        <div class="model-download-progress">
          <div class="download-status-text">Downloading ${this.formatModelSize(model.model_size)}...</div>
          <div class="download-progress-bar">
            <div class="download-progress-fill"></div>
          </div>
        </div>
        <div class="model-actions">
          ${!model.is_cached ? `<button class="model-action-btn download" data-alias="${model.alias}" data-size="${model.model_size}" title="Download model">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21,15v4a2,2 0 0,1 -2,2H5a2,2 0 0,1 -2,-2v-4"></path><polyline points="7,10 12,15 17,10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          </button>` : ''}
          ${model.is_cached && !isCurrent ? `<button class="model-action-btn switch" data-alias="${model.alias}" title="Switch to this model">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"></polyline><line x1="4" y1="20" x2="21" y2="3"></line><polyline points="21 16 21 21 16 21"></polyline><line x1="15" y1="15" x2="21" y2="21"></line><line x1="4" y1="4" x2="9" y2="9"></line></svg>
          </button>` : ''}
          ${model.is_cached && !isCurrent ? `<button class="model-action-btn delete" data-alias="${model.alias}" title="Delete from disk">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
          </button>` : ''}
          ${isCurrent ? '<span class="model-current-badge">In Use</span>' : ''}
        </div>
      `;
      item.dataset.alias = model.alias;

      // Add event listeners
      const downloadBtn = item.querySelector('.model-action-btn.download');
      if (downloadBtn) {
        downloadBtn.addEventListener('click', () => this.downloadModel(model.alias));
      }

      const switchBtn = item.querySelector('.model-action-btn.switch');
      if (switchBtn) {
        switchBtn.addEventListener('click', () => this.switchModel(model.alias));
      }

      const deleteBtn = item.querySelector('.model-action-btn.delete');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', () => this.deleteModel(model.alias));
      }

      modelsList.appendChild(item);
    });
  }

  async downloadModel(alias) {
    // Find the model item and add downloading class
    const modelItem = this.elements.modelsList.querySelector(`.model-item[data-alias="${alias}"]`);
    if (modelItem) {
      modelItem.classList.add('downloading');
    }

    try {
      // Start async download
      const response = await this.apiRequest(`/models/download/${encodeURIComponent(alias)}`, { method: 'POST' });

      if (response.status === 'started' || response.status === 'already_downloading') {
        // Poll for download status
        this.pollDownloadStatus(alias);
      } else if (response.status === 'completed' || response.status === 'already_cached') {
        // Already done - refresh the model list
        if (modelItem) {
          modelItem.classList.remove('downloading');
        }
        await this.loadAllModels();
        await this.loadModels();
      }
    } catch (error) {
      console.error('Failed to download model:', error);
      alert(`Failed to download model: ${error.message || 'Unknown error'}`);
      if (modelItem) {
        modelItem.classList.remove('downloading');
      }
    }
  }

  async deleteModel(alias) {
    // Confirm deletion
    if (!confirm(`Delete model "${alias}" from disk? This will free up storage space but you'll need to re-download it to use it again.`)) {
      return;
    }

    try {
      const response = await this.apiRequest(`/models/cache/${encodeURIComponent(alias)}`, {
        method: 'DELETE',
      });

      // Show success message with freed space
      alert(`Model "${alias}" deleted. Freed ${response.freed_mb || 0} MB of storage.`);

      // Refresh the model list
      await this.loadAllModels();
      await this.loadModels();
    } catch (error) {
      console.error('Failed to delete model:', error);
      alert(`Failed to delete model: ${error.message || 'Unknown error'}`);
    }
  }

  async pollDownloadStatus(alias) {
    const poll = async () => {
      try {
        const status = await this.apiRequest(`/models/downloads/${encodeURIComponent(alias)}/status`);

        if (status.status === 'downloading') {
          // Update progress display
          this.updateDownloadProgress(alias, status);
          // Still downloading, poll again in 1 second for smoother updates
          setTimeout(poll, 1000);
        } else if (status.status === 'completed') {
          // Download finished! Refresh the model list
          console.log(`Download completed: ${alias}`);
          await this.loadAllModels();
          await this.loadModels();
        } else if (status.status === 'failed') {
          // Download failed
          console.error(`Download failed: ${alias}`, status.error);
          alert(`Download failed: ${status.error || 'Unknown error'}`);
          const modelItem = this.elements.modelsList?.querySelector(`.model-item[data-alias="${alias}"]`);
          if (modelItem) {
            modelItem.classList.remove('downloading');
          }
        } else {
          // Not downloading (maybe completed before we started polling)
          await this.loadAllModels();
          await this.loadModels();
        }
      } catch (error) {
        console.error('Failed to poll download status:', error);
        // Stop polling on error
      }
    };

    poll();
  }

  updateDownloadProgress(alias, status) {
    const modelItem = this.elements.modelsList?.querySelector(`.model-item[data-alias="${alias}"]`);
    if (!modelItem) return;

    const progressText = modelItem.querySelector('.download-status-text');
    const progressFill = modelItem.querySelector('.download-progress-fill');

    // Display real-time progress from Foundry service stream
    if (progressText && status.expected_size_mb) {
      const percent = status.progress_percent || 0;
      const downloadedMb = status.downloaded_mb || 0;
      progressText.textContent = `Downloading: ${downloadedMb} MB / ${status.expected_size_mb} MB (${percent}%)`;
    }

    if (progressFill && status.progress_percent !== undefined) {
      // Stop the animation and show actual progress
      progressFill.style.animation = 'none';
      progressFill.style.width = `${status.progress_percent}%`;
      progressFill.style.marginLeft = '0';
    }
  }

  async checkActiveDownloads() {
    try {
      const response = await this.apiRequest('/models/downloads/status');
      const downloads = response.downloads || {};

      // For any active downloads, start polling
      for (const [alias, status] of Object.entries(downloads)) {
        if (status.status === 'downloading') {
          // Mark the model as downloading in the UI
          const modelItem = this.elements.modelsList?.querySelector(`.model-item[data-alias="${alias}"]`);
          if (modelItem) {
            modelItem.classList.add('downloading');
          }
          // Start polling
          this.pollDownloadStatus(alias);
        }
      }
    } catch (error) {
      console.error('Failed to check active downloads:', error);
    }
  }

  async switchModel(alias, fromHeader = false) {
    // Close dropdown if opened from header
    if (fromHeader) {
      this.closeModelDropdown();
    }

    // Store the pending model for retry functionality
    this._pendingSwitchModel = alias;

    // Get current model name for display
    const modelNameSpan = this.elements.chatModel.querySelector('.model-name');
    const currentModel = modelNameSpan?.textContent || 'current model';

    // Show the switch progress modal
    this.showSwitchProgressModal(currentModel, alias);

    try {
      // Start the async switch
      const startResult = await this.apiRequest('/models/switch/start', {
        method: 'POST',
        body: JSON.stringify({ model_alias: alias }),
      });

      if (startResult.status === 'already_loaded') {
        // Already on this model, just close the modal
        this.closeSwitchProgressModal();
        return;
      }

      if (startResult.status === 'already_switching') {
        // A switch is already in progress, just start polling
        console.log('Switch already in progress, starting poll...');
      }

      // Start polling for status updates
      this.startSwitchStatusPolling();

    } catch (error) {
      console.error('Failed to start model switch:', error);
      this.showSwitchError(error.message || 'Failed to start model switch');
    }
  }

  showSwitchProgressModal(fromModel, toModel) {
    const modal = this.elements.switchProgressModal;
    if (!modal) return;

    // Reset modal state
    modal.classList.remove('ready', 'failed');
    modal.classList.add('visible');

    // Set model names
    this.elements.switchFromModel.textContent = fromModel || '--';
    this.elements.switchToModel.textContent = toModel;

    // Reset phases
    this.elements.phaseUnload.classList.remove('active', 'completed', 'skipped');
    this.elements.phaseDownload.classList.remove('active', 'completed', 'skipped');
    this.elements.phaseLoad.classList.remove('active', 'completed', 'skipped');

    // Reset progress
    this.elements.switchProgressFill.style.width = '0%';
    this.elements.switchStatusText.textContent = 'Preparing...';
    this.elements.downloadDetail.textContent = '';

    // Hide error
    this.elements.switchError.style.display = 'none';

    // Show cancel button
    this.elements.cancelSwitchBtn.style.display = 'inline-flex';
    this.elements.cancelSwitchBtn.onclick = () => this.cancelModelSwitch();

    // Setup retry button
    this.elements.switchRetryBtn.onclick = () => this.retryModelSwitch();
  }

  closeSwitchProgressModal() {
    const modal = this.elements.switchProgressModal;
    if (modal) {
      modal.classList.remove('visible', 'ready', 'failed');
    }
    this.stopSwitchStatusPolling();
  }

  startSwitchStatusPolling() {
    // Stop any existing polling
    this.stopSwitchStatusPolling();

    // Poll every 500ms
    this._switchPollInterval = setInterval(() => {
      this.pollSwitchStatus();
    }, 500);

    // Also poll immediately
    this.pollSwitchStatus();
  }

  stopSwitchStatusPolling() {
    if (this._switchPollInterval) {
      clearInterval(this._switchPollInterval);
      this._switchPollInterval = null;
    }
  }

  async pollSwitchStatus() {
    try {
      const status = await this.apiRequest('/models/switch/status');
      this.updateSwitchProgressUI(status);

      // Check if we're done
      if (status.status === 'ready' || status.status === 'failed' || status.status === 'cancelled') {
        this.stopSwitchStatusPolling();

        if (status.status === 'ready') {
          await this.handleSwitchComplete(status);
        } else if (status.status === 'failed') {
          this.showSwitchError(status.error || 'Switch failed');
        }
      }
    } catch (error) {
      console.error('Failed to poll switch status:', error);
      // Don't stop polling on network errors, might be transient
    }
  }

  updateSwitchProgressUI(status) {
    const progressBar = this.elements.switchProgressFill.parentElement;
    const progressFill = this.elements.switchProgressFill;
    const currentPhase = status.status;

    // Use indeterminate animation for loading phase (no progress available from SDK)
    if (currentPhase === 'loading') {
      progressBar.classList.add('indeterminate');
      // Clear inline width so CSS animation can take over
      progressFill.style.width = '';
    } else {
      progressBar.classList.remove('indeterminate');
      // Update progress bar width
      progressFill.style.width = `${status.progress_percent || 0}%`;
    }

    // Update status text
    this.elements.switchStatusText.textContent = status.phase_message || 'Working...';

    // Reset all phases
    this.elements.phaseUnload.classList.remove('active', 'completed');
    this.elements.phaseDownload.classList.remove('active', 'completed', 'skipped');
    this.elements.phaseLoad.classList.remove('active', 'completed');

    switch (currentPhase) {
      case 'unloading':
        this.elements.phaseUnload.classList.add('active');
        break;

      case 'downloading':
        this.elements.phaseUnload.classList.add('completed');
        this.elements.phaseDownload.classList.add('active');
        // Show download details
        if (status.download_percent !== undefined) {
          this.elements.downloadDetail.textContent = `${status.download_percent.toFixed(0)}%`;
        }
        break;

      case 'loading':
        this.elements.phaseUnload.classList.add('completed');
        // Mark download as completed or skipped based on whether it was needed
        if (status.download_percent !== undefined && status.download_percent > 0) {
          this.elements.phaseDownload.classList.add('completed');
        } else {
          this.elements.phaseDownload.classList.add('skipped');
          this.elements.phaseDownload.querySelector('.phase-label').textContent = 'Download (cached)';
        }
        this.elements.phaseLoad.classList.add('active');
        this.elements.downloadDetail.textContent = '';
        break;

      case 'ready':
        this.elements.phaseUnload.classList.add('completed');
        if (status.download_percent !== undefined && status.download_percent > 0) {
          this.elements.phaseDownload.classList.add('completed');
        } else {
          this.elements.phaseDownload.classList.add('skipped');
          this.elements.phaseDownload.querySelector('.phase-label').textContent = 'Download (cached)';
        }
        this.elements.phaseLoad.classList.add('completed');
        this.elements.downloadDetail.textContent = '';
        // Remove indeterminate when ready
        progressBar.classList.remove('indeterminate');
        this.elements.switchProgressFill.style.width = '100%';
        break;
    }
  }

  async handleSwitchComplete(status) {
    const modal = this.elements.switchProgressModal;
    modal.classList.add('ready');

    // Update header with new model
    const modelNameSpan = this.elements.chatModel.querySelector('.model-name');
    if (modelNameSpan && status.to_model) {
      modelNameSpan.textContent = status.to_model;
    }

    // Hide cancel button
    this.elements.cancelSwitchBtn.style.display = 'none';

    // Update status text
    this.elements.switchStatusText.textContent = `Switched to ${status.to_model}`;

    // Reload model info
    try {
      if (this.elements.modelManagerModal.classList.contains('visible')) {
        await this.loadAllModels();
      }
      await this.loadModels();
    } catch (error) {
      console.warn('Failed to reload models after switch:', error);
    }

    // Reset switch status on backend
    try {
      await this.apiRequest('/models/switch/reset', { method: 'POST' });
    } catch (error) {
      console.warn('Failed to reset switch status:', error);
    }

    // Close modal after a short delay to show completion
    setTimeout(() => {
      this.closeSwitchProgressModal();
      // Reset download phase label
      this.elements.phaseDownload.querySelector('.phase-label').textContent = 'Download model';
    }, 1500);
  }

  showSwitchError(message) {
    const modal = this.elements.switchProgressModal;
    modal.classList.add('failed');

    // Hide cancel, show error
    this.elements.cancelSwitchBtn.style.display = 'none';
    this.elements.switchError.style.display = 'flex';
    this.elements.switchErrorText.textContent = message;
  }

  async cancelModelSwitch() {
    try {
      await this.apiRequest('/models/switch/cancel', { method: 'POST' });
    } catch (error) {
      console.warn('Failed to cancel switch:', error);
    }
    this.closeSwitchProgressModal();

    // Reset switch status
    try {
      await this.apiRequest('/models/switch/reset', { method: 'POST' });
    } catch (error) {
      console.warn('Failed to reset switch status:', error);
    }
  }

  async retryModelSwitch() {
    // Hide error
    this.elements.switchError.style.display = 'none';
    this.elements.switchProgressModal.classList.remove('failed');

    // Reset switch status first
    try {
      await this.apiRequest('/models/switch/reset', { method: 'POST' });
    } catch (error) {
      console.warn('Failed to reset switch status:', error);
    }

    // Retry with the pending model
    if (this._pendingSwitchModel) {
      await this.switchModel(this._pendingSwitchModel);
    }
  }

  async saveSettings() {
    this.settings.temperature = parseFloat(this.elements.temperatureSlider.value);
    this.settings.maxTokens = parseInt(this.elements.maxTokensInput.value);
    this.settings.contextWindow = parseInt(this.elements.contextWindowInput.value);
    this.settings.verbose = this.elements.verboseCheckbox.checked;
    this.settings.theme = this.elements.themeSelect.value;
    this.settings.whisperModel = this.elements.whisperModelSelect.value;
    this.settings.apiPort = parseInt(this.elements.apiPortInput.value);

    // Update API base
    this.apiBase = `http://localhost:${this.settings.apiPort}`;

    // Initialize Whisper model if changed
    try {
      await this.apiRequest('/speech/initialize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `model_size=${this.settings.whisperModel}`,
      });
    } catch (error) {
      console.warn('Failed to initialize Whisper model:', error);
    }

    // Save to Electron store
    if (window.electronAPI) {
      await window.electronAPI.setSettings(this.settings);
    }

    // Apply theme
    if (this.settings.theme === 'system' && window.electronAPI) {
      const actualTheme = await window.electronAPI.getTheme();
      this.applyTheme(actualTheme);
    } else {
      this.applyTheme(this.settings.theme);
    }

    // Apply verbose setting
    if (this.settings.verbose) {
      this.elements.metricsPanel.classList.remove('hidden');
      this.elements.toggleMetricsBtn.classList.add('active');
    } else {
      this.elements.metricsPanel.classList.add('hidden');
      this.elements.toggleMetricsBtn.classList.remove('active');
    }

    // Switch model if changed
    const selectedModel = this.elements.modelSelect.value;
    const currentModelSpan = this.elements.chatModel?.querySelector('.model-name');
    const currentModel = currentModelSpan?.textContent;

    this.closeSettings();

    // Only switch if model actually changed
    if (selectedModel && selectedModel !== currentModel) {
      // Use the async switch with progress modal
      await this.switchModel(selectedModel);
    }
  }

  setTheme(theme) {
    this.settings.theme = theme;
    if (theme === 'system') {
      // Will be handled by Electron
      return;
    }
    this.applyTheme(theme);
  }

  applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }

  // === UI Toggles ===

  toggleSidebar() {
    this.elements.sidebar.classList.toggle('collapsed');
  }

  updatePocketIndicator() {
    const indicator = this.elements.pocketIndicator;
    if (this.currentPocket) {
      indicator.textContent = `Using ${this.currentPocket} pocket`;
    } else {
      indicator.textContent = '';
    }
  }

  // === Audio Recording ===

  async toggleRecording() {
    if (this.isTranscribing) return;

    if (this.isRecording) {
      await this.stopRecording();
    } else {
      await this.startRecording();
    }
  }

  async startRecording() {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        }
      });

      this.audioChunks = [];
      this.mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };

      this.mediaRecorder.start(100); // Collect data every 100ms
      this.isRecording = true;
      this.recordingStartTime = Date.now();

      // Update UI
      this.elements.micBtn.classList.add('recording');
      this.updateRecordingIndicator();

      console.log('Recording started');
    } catch (error) {
      console.error('Failed to start recording:', error);
      this.showRecordingError('Microphone access denied. Please allow microphone access.');
    }
  }

  async stopRecording() {
    if (!this.mediaRecorder || this.mediaRecorder.state !== 'recording') {
      return;
    }

    return new Promise((resolve) => {
      this.mediaRecorder.onstop = async () => {
        this.isRecording = false;
        this.elements.micBtn.classList.remove('recording');
        this.elements.recordingIndicator.textContent = '';

        // Create blob from chunks
        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });

        if (audioBlob.size > 0) {
          await this.transcribeAudio(audioBlob);
        }

        resolve();
      };

      this.mediaRecorder.stop();
      console.log('Recording stopped');
    });
  }

  async transcribeAudio(audioBlob) {
    this.isTranscribing = true;
    this.elements.micBtn.classList.add('transcribing');
    this.elements.recordingIndicator.textContent = 'Transcribing...';

    try {
      // Convert blob to base64
      const reader = new FileReader();
      const base64Promise = new Promise((resolve, reject) => {
        reader.onloadend = () => {
          const base64 = reader.result.split(',')[1];
          resolve(base64);
        };
        reader.onerror = reject;
      });
      reader.readAsDataURL(audioBlob);
      const audioBase64 = await base64Promise;

      // Send to API
      const formData = new FormData();
      formData.append('audio_base64', audioBase64);
      formData.append('filename', 'recording.webm');
      formData.append('language', ''); // Auto-detect

      const response = await fetch(`${this.apiBase}/speech/transcribe/base64`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.status}`);
      }

      const result = await response.json();

      if (result.text && result.text.trim()) {
        // Insert transcribed text into input
        const currentText = this.elements.messageInput.value;
        const newText = currentText
          ? `${currentText} ${result.text.trim()}`
          : result.text.trim();
        this.elements.messageInput.value = newText;
        this.handleInputChange();

        // Show transcription info
        console.log(`Transcribed: "${result.text}" (${result.language}, ${result.processing_time.toFixed(2)}s)`);
      } else {
        console.log('No speech detected');
      }
    } catch (error) {
      console.error('Transcription error:', error);
      this.showRecordingError('Transcription failed. Is the API running?');
    } finally {
      this.isTranscribing = false;
      this.elements.micBtn.classList.remove('transcribing');
      this.elements.recordingIndicator.textContent = '';
    }
  }

  updateRecordingIndicator() {
    if (!this.isRecording) return;

    const elapsed = Math.floor((Date.now() - this.recordingStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    this.elements.recordingIndicator.textContent =
      `Recording ${minutes}:${seconds.toString().padStart(2, '0')}`;

    if (this.isRecording) {
      requestAnimationFrame(() => setTimeout(() => this.updateRecordingIndicator(), 1000));
    }
  }

  showRecordingError(message) {
    // Show error briefly in the recording indicator
    this.elements.recordingIndicator.textContent = message;
    this.elements.recordingIndicator.style.color = 'var(--error-color)';
    setTimeout(() => {
      this.elements.recordingIndicator.textContent = '';
      this.elements.recordingIndicator.style.color = '';
    }, 3000);
  }

  // === Document Manager ===

  async openDocManager() {
    this.elements.docManagerModal.classList.add('visible');
    await this.loadPockets();
    await this.loadDocuments();
  }

  closeDocManager() {
    this.elements.docManagerModal.classList.remove('visible');
  }

  async loadPockets() {
    try {
      this.pockets = await this.apiRequest('/rag/pockets');
      this.renderPocketTabs();

      // Select first pocket if current doesn't exist
      if (!this.pockets.find(p => p.id === this.docManagerPocket) && this.pockets.length > 0) {
        this.docManagerPocket = this.pockets[0].id;
      }
    } catch (error) {
      console.error('Failed to load pockets:', error);
      this.pockets = [];
    }
  }

  renderPocketTabs() {
    const html = this.pockets.map(pocket => `
      <button class="pocket-tab${pocket.id === this.docManagerPocket ? ' active' : ''}" data-pocket="${pocket.id}">
        <span class="pocket-icon" style="background: ${pocket.color || '#808080'};"></span>
        ${this.escapeHtml(pocket.name)}
      </button>
    `).join('');

    this.elements.pocketTabs.innerHTML = html;

    // Rebind click events
    this.elements.pocketTabs.querySelectorAll('.pocket-tab').forEach(tab => {
      tab.addEventListener('click', () => this.selectDocManagerPocket(tab.dataset.pocket));
    });
  }

  selectDocManagerPocket(pocket) {
    this.docManagerPocket = pocket;
    this.renderPocketTabs();
    this.loadDocuments();
  }

  async loadDocuments() {
    const pocket = this.docManagerPocket;
    if (!pocket) {
      this.elements.docList.innerHTML = '<div class="doc-empty">No pocket selected</div>';
      return;
    }

    this.elements.docList.innerHTML = '<div class="doc-loading">Loading documents...</div>';

    try {
      const [docs, stats] = await Promise.all([
        this.apiRequest(`/rag/pockets/${pocket}/documents`),
        this.apiRequest(`/rag/stats/${pocket}`),
      ]);

      this.documents = docs;
      this.pocketStats = stats;

      this.updateDocStats();
      this.renderDocuments();
    } catch (error) {
      console.error('Failed to load documents:', error);
      this.elements.docList.innerHTML = '<div class="doc-empty">Failed to load documents</div>';
      this.resetDocStats();
    }
  }

  updateDocStats() {
    const stats = this.pocketStats;

    this.elements.statDocCount.textContent = this.documents.length;

    const vectorCount = stats.collection_stats?.vector_count || 0;
    this.elements.statChunkCount.textContent = vectorCount;

    const totalSize = this.documents.reduce((sum, doc) => sum + (doc.size || 0), 0);
    this.elements.statTotalSize.textContent = this.formatFileSize(totalSize);

    if (vectorCount > 0) {
      this.elements.statStatus.textContent = 'Ready';
      this.elements.statStatus.style.color = 'var(--success-color)';
    } else if (this.documents.length > 0) {
      this.elements.statStatus.textContent = 'Pending';
      this.elements.statStatus.style.color = 'var(--warning-color)';
    } else {
      this.elements.statStatus.textContent = 'Empty';
      this.elements.statStatus.style.color = 'var(--text-tertiary)';
    }
  }

  resetDocStats() {
    this.elements.statDocCount.textContent = '--';
    this.elements.statChunkCount.textContent = '--';
    this.elements.statTotalSize.textContent = '--';
    this.elements.statStatus.textContent = '--';
    this.elements.statStatus.style.color = '';
  }

  renderDocuments() {
    if (this.documents.length === 0) {
      this.elements.docList.innerHTML = '<div class="doc-empty">No documents in this pocket. Upload files to get started.</div>';
      return;
    }

    const vectorCount = this.pocketStats.collection_stats?.vector_count || 0;

    const html = this.documents.map(doc => {
      const ext = (doc.type || '').replace('.', '');
      const hasVectors = vectorCount > 0;
      const status = hasVectors ? 'embedded' : 'pending';
      const statusText = hasVectors ? 'Embedded' : 'Pending';
      const escapedName = this.escapeHtml(doc.name).replace(/'/g, "\\'");

      return `
        <div class="doc-item" data-filename="${this.escapeHtml(doc.name)}">
          <div class="doc-icon ${ext}">
            ${this.getFileIcon(ext)}
          </div>
          <div class="doc-info">
            <div class="doc-name">${this.escapeHtml(doc.name)}</div>
            <div class="doc-meta">
              <span>${this.formatFileSize(doc.size)}</span>
              <span>${ext.toUpperCase()}</span>
            </div>
          </div>
          <div class="doc-status ${status}">
            <span class="doc-status-dot"></span>
            ${statusText}
          </div>
          <div class="doc-actions-btns">
            <button class="doc-action-btn ingest" onclick="app.ingestDocument('${escapedName}')" title="Re-ingest document">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
            <button class="doc-action-btn move" onclick="app.openMoveDocument('${escapedName}')" title="Move to another pocket">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </button>
            <button class="doc-action-btn delete" onclick="app.deleteDocument('${escapedName}')" title="Delete document">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>
      `;
    }).join('');

    this.elements.docList.innerHTML = html;
  }

  getFileIcon(ext) {
    const icons = {
      pdf: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
      txt: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
      md: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M9 15l2 2 4-4"/></svg>',
      docx: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    };
    return icons[ext] || icons.txt;
  }

  formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
  }

  async handleFileSelect(files) {
    if (!files || files.length === 0) return;

    const pocket = this.docManagerPocket;
    const totalFiles = files.length;
    let uploaded = 0;

    this.elements.uploadProgress.style.display = 'block';
    this.elements.progressFill.style.width = '0%';
    this.elements.progressText.textContent = `Uploading 0/${totalFiles} files...`;

    for (const file of files) {
      try {
        await this.uploadFile(file, pocket);
        uploaded++;
        const progress = (uploaded / totalFiles) * 100;
        this.elements.progressFill.style.width = `${progress}%`;
        this.elements.progressText.textContent = `Uploading ${uploaded}/${totalFiles} files...`;
      } catch (error) {
        console.error(`Failed to upload ${file.name}:`, error);
      }
    }

    this.elements.progressText.textContent = `Uploaded ${uploaded}/${totalFiles} files`;
    setTimeout(() => {
      this.elements.uploadProgress.style.display = 'none';
    }, 2000);

    this.elements.fileInput.value = '';
    await this.loadDocuments();
  }

  async uploadFile(file, pocket) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.apiBase}/rag/pockets/${pocket}/documents/upload?ingest=true`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }

    return await response.json();
  }

  async ingestDocument(filename) {
    const pocket = this.docManagerPocket;
    const docItem = document.querySelector(`.doc-item[data-filename="${filename}"]`);
    if (docItem) docItem.classList.add('ingesting');

    try {
      const pocketPath = await this.apiRequest(`/rag/pockets/${pocket}`);
      const filePath = `${pocketPath.path}/${filename}`;

      const formData = new URLSearchParams();
      formData.append('pocket_id', pocket);
      formData.append('file_path', filePath);
      formData.append('force', 'true');

      const response = await fetch(`${this.apiBase}/rag/ingest/file`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!response.ok) throw new Error('Ingest failed');
      const result = await response.json();

      await this.loadDocuments();
      console.log(`Ingested ${filename}: ${result.chunk_count} chunks`);
    } catch (error) {
      console.error('Failed to ingest document:', error);
      alert(`Failed to ingest ${filename}`);
    } finally {
      if (docItem) docItem.classList.remove('ingesting');
    }
  }

  async deleteDocument(filename) {
    if (!confirm(`Delete "${filename}"? This will also remove its vectors.`)) return;

    const pocket = this.docManagerPocket;

    try {
      await this.apiRequest(`/rag/pockets/${pocket}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });
      await this.loadDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document');
    }
  }

  async ingestAllDocuments() {
    const pocket = this.docManagerPocket;

    this.elements.ingestAllBtn.disabled = true;
    this.elements.ingestAllBtn.textContent = 'Ingesting...';

    try {
      const result = await this.apiRequest('/rag/ingest', {
        method: 'POST',
        body: JSON.stringify({ pocket_id: pocket, force: true }),
      });

      await this.loadDocuments();
      alert(`Ingested ${result.documents_successful}/${result.documents_processed} documents (${result.total_chunks} chunks)`);
    } catch (error) {
      console.error('Failed to ingest documents:', error);
      alert('Failed to ingest documents');
    } finally {
      this.elements.ingestAllBtn.disabled = false;
      this.elements.ingestAllBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
        Re-Ingest All
      `;
    }
  }

  // === Pocket Management ===

  openCreatePocket() {
    this.elements.newPocketId.value = '';
    this.elements.newPocketName.value = '';
    this.elements.newPocketDescription.value = '';
    this.elements.newPocketColor.value = '#778899';
    document.querySelectorAll('.color-option').forEach(b => b.classList.remove('selected'));
    document.querySelector('.color-option[data-color="#778899"]')?.classList.add('selected');
    this.elements.createPocketModal.classList.add('visible');
  }

  closeCreatePocket() {
    this.elements.createPocketModal.classList.remove('visible');
  }

  async createPocket() {
    const id = this.elements.newPocketId.value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
    const name = this.elements.newPocketName.value.trim();
    const description = this.elements.newPocketDescription.value.trim();
    const color = this.elements.newPocketColor.value;

    if (!id || !name) {
      alert('Please enter a pocket ID and name');
      return;
    }

    try {
      await this.apiRequest('/rag/pockets', {
        method: 'POST',
        body: JSON.stringify({
          id,
          name,
          description: description || `Documents for ${name}`,
          color,
        }),
      });

      this.closeCreatePocket();
      await this.loadPockets();
      this.docManagerPocket = id;
      await this.loadDocuments();

      // Update main pocket selector
      this.updateMainPocketSelector();
    } catch (error) {
      console.error('Failed to create pocket:', error);
      alert('Failed to create pocket. ID may already exist.');
    }
  }

  async deletePocket() {
    const pocket = this.docManagerPocket;
    const pocketInfo = this.pockets.find(p => p.id === pocket);

    if (!pocketInfo) return;

    if (!confirm(`Delete pocket "${pocketInfo.name}"?\n\nThis will delete all documents and their embeddings. This cannot be undone.`)) {
      return;
    }

    try {
      await this.apiRequest(`/rag/pockets/${pocket}?delete_files=true`, {
        method: 'DELETE',
      });

      await this.loadPockets();
      if (this.pockets.length > 0) {
        this.docManagerPocket = this.pockets[0].id;
      }
      await this.loadDocuments();

      // Update main pocket selector
      this.updateMainPocketSelector();
    } catch (error) {
      console.error('Failed to delete pocket:', error);
      alert('Failed to delete pocket');
    }
  }

  updateMainPocketSelector() {
    const select = this.elements.pocketSelect;
    const currentValue = select.value;

    // Rebuild options
    select.innerHTML = '<option value="">General (No RAG)</option>';
    this.pockets.forEach(pocket => {
      const option = document.createElement('option');
      option.value = pocket.id;
      option.textContent = pocket.name;
      select.appendChild(option);
    });

    // Restore selection if still valid
    if (this.pockets.find(p => p.id === currentValue)) {
      select.value = currentValue;
    }
  }

  // === Move Document ===

  openMoveDocument(filename) {
    this.moveDocFilename = filename;
    this.elements.moveDocName.textContent = `Move "${filename}" to:`;

    // Populate target pockets (excluding current)
    const options = this.pockets
      .filter(p => p.id !== this.docManagerPocket)
      .map(p => `<option value="${p.id}">${this.escapeHtml(p.name)}</option>`)
      .join('');

    if (!options) {
      alert('No other pockets available. Create another pocket first.');
      return;
    }

    this.elements.moveTargetPocket.innerHTML = options;
    this.elements.moveDocModal.classList.add('visible');
  }

  closeMoveDoc() {
    this.elements.moveDocModal.classList.remove('visible');
    this.moveDocFilename = null;
  }

  async confirmMoveDocument() {
    const filename = this.moveDocFilename;
    const targetPocket = this.elements.moveTargetPocket.value;
    const sourcePocket = this.docManagerPocket;

    if (!filename || !targetPocket) return;

    try {
      // Get file from source pocket
      const sourceDoc = this.documents.find(d => d.name === filename);
      if (!sourceDoc) throw new Error('Document not found');

      // Download the file content
      const response = await fetch(sourceDoc.path);
      if (!response.ok) throw new Error('Failed to read file');
      const blob = await response.blob();
      const file = new File([blob], filename);

      // Upload to target pocket
      await this.uploadFile(file, targetPocket);

      // Delete from source pocket
      await this.apiRequest(`/rag/pockets/${sourcePocket}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });

      this.closeMoveDoc();
      await this.loadDocuments();
      alert(`Moved "${filename}" to ${this.pockets.find(p => p.id === targetPocket)?.name}`);
    } catch (error) {
      console.error('Failed to move document:', error);
      alert('Failed to move document. Try manually uploading to the target pocket.');
    }
  }

  // === Folders & Tags ===

  async loadFolders() {
    try {
      // Build query params to filter by project
      const params = new URLSearchParams();
      if (this.currentProjectId) {
        params.append('project_id', this.currentProjectId);
        params.append('include_global', 'true');  // Show global folders too
      }
      const queryString = params.toString();
      const url = `/organize/folders${queryString ? `?${queryString}` : ''}`;

      this.folders = await this.apiRequest(url);
      this.renderFolders();
    } catch (error) {
      console.error('Failed to load folders:', error);
      this.folders = [];
    }
  }

  async loadTags() {
    try {
      this.tags = await this.apiRequest('/organize/tags');
      this.renderTags();
    } catch (error) {
      console.error('Failed to load tags:', error);
      this.tags = [];
    }
  }

  renderFolders() {
    const container = this.elements.foldersList;
    if (!container) return;

    container.innerHTML = '';

    if (this.folders.length === 0) {
      container.innerHTML = '<p class="no-items">No folders yet</p>';
      return;
    }

    this.folders.forEach(folder => {
      const isExpanded = this.expandedFolders.has(folder.id);

      // Get sessions in this folder
      const folderSessions = this.sessions.filter(s => s.folder_id === folder.id);
      const sessionCount = folderSessions.length;

      const item = document.createElement('div');
      item.className = `folder-item${isExpanded ? ' expanded' : ''}`;
      item.dataset.folderId = folder.id;

      // Show global badge when viewing a project and folder is global
      const isGlobal = !folder.project_id;
      const showGlobalBadge = isGlobal && this.currentProjectId;
      const badge = showGlobalBadge
        ? '<span class="folder-global-badge" title="Global folder">G</span>'
        : '';

      item.innerHTML = `
        <span class="folder-toggle">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="${isExpanded ? '6 9 12 15 18 9' : '9 6 15 12 9 18'}"/>
          </svg>
        </span>
        <span class="folder-icon" style="color: ${folder.color || '#808080'}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none">
            <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
          </svg>
        </span>
        <span class="folder-name">${this.escapeHtml(folder.name)}</span>
        ${badge}
        <span class="folder-count">${sessionCount}</span>
      `;
      // Click to expand/collapse the folder
      item.addEventListener('click', () => this.toggleFolderExpand(folder.id));
      item.addEventListener('contextmenu', (e) => this.showFolderContextMenu(e, folder.id));
      container.appendChild(item);

      // Render nested sessions when expanded
      if (isExpanded && folderSessions.length > 0) {
        const folderContent = document.createElement('div');
        folderContent.className = 'folder-content';

        folderSessions.forEach(session => {
          folderContent.appendChild(this.createSessionItem(session, true));
        });

        container.appendChild(folderContent);
      }
    });
  }

  renderTags() {
    const container = this.elements.tagsList;
    if (!container) return;

    container.innerHTML = '';

    if (this.tags.length === 0) {
      container.innerHTML = '<p class="no-items">No tags yet</p>';
      return;
    }

    this.tags.forEach(tag => {
      const item = document.createElement('div');
      item.className = `tag-item${tag.id === this.currentTagId ? ' active' : ''}`;
      item.dataset.tagId = tag.id;
      item.innerHTML = `
        <span class="tag-dot" style="background: ${tag.color || '#007AFF'}"></span>
        <span class="tag-name">${this.escapeHtml(tag.name)}</span>
      `;
      item.addEventListener('click', () => this.filterByTag(tag.id));
      container.appendChild(item);
    });
  }

  // === Create Folder Modal ===

  openCreateFolderModal() {
    this.elements.folderModalTitle.textContent = 'Create Folder';
    this.elements.folderNameInput.value = '';
    this.elements.folderColorInput.value = '#007AFF';

    // Reset color picker
    const picker = this.elements.folderColorPicker;
    if (picker) {
      picker.querySelectorAll('.color-option').forEach(btn => btn.classList.remove('selected'));
      picker.querySelector('.color-option[data-color="#007AFF"]')?.classList.add('selected');
    }

    this.elements.createFolderModal.classList.add('visible');
  }

  closeCreateFolderModal() {
    this.elements.createFolderModal.classList.remove('visible');
  }

  async createFolder() {
    const name = this.elements.folderNameInput.value.trim();
    const color = this.elements.folderColorInput.value;

    if (!name) {
      alert('Please enter a folder name');
      return;
    }

    try {
      await this.apiRequest('/organize/folders', {
        method: 'POST',
        body: JSON.stringify({ name, color }),
      });

      this.closeCreateFolderModal();
      await this.loadFolders();
    } catch (error) {
      console.error('Failed to create folder:', error);
      alert('Failed to create folder');
    }
  }

  // === Create Tag Modal ===

  openCreateTagModal() {
    this.elements.tagModalTitle.textContent = 'Create Tag';
    this.elements.tagNameInput.value = '';
    this.elements.tagColorInput.value = '#007AFF';

    // Reset color picker
    const picker = this.elements.tagColorPicker;
    if (picker) {
      picker.querySelectorAll('.color-option').forEach(btn => btn.classList.remove('selected'));
      picker.querySelector('.color-option[data-color="#007AFF"]')?.classList.add('selected');
    }

    this.elements.createTagModal.classList.add('visible');
  }

  closeCreateTagModal() {
    this.elements.createTagModal.classList.remove('visible');
  }

  async createTag() {
    const name = this.elements.tagNameInput.value.trim();
    const color = this.elements.tagColorInput.value;

    if (!name) {
      alert('Please enter a tag name');
      return;
    }

    try {
      await this.apiRequest('/organize/tags', {
        method: 'POST',
        body: JSON.stringify({ name, color }),
      });

      this.closeCreateTagModal();
      await this.loadTags();
    } catch (error) {
      console.error('Failed to create tag:', error);
      alert('Failed to create tag. Tag name may already exist.');
    }
  }

  // === Session Filtering ===

  filterByTag(tagId) {
    if (this.currentTagId === tagId) {
      // Toggle off
      this.currentTagId = null;
    } else {
      this.currentTagId = tagId;
    }
    this.updateFilterLabel();
    this.renderTags();
    this.loadSessions();
  }

  clearFilter() {
    this.currentTagId = null;
    this.updateFilterLabel();
    this.renderTags();
    this.loadSessions();
  }

  updateFilterLabel() {
    const label = this.elements.sessionsLabel;
    const clearBtn = this.elements.clearFilterBtn;

    if (!label) return;

    if (this.currentTagId) {
      const tag = this.tags.find(t => t.id === this.currentTagId);
      label.textContent = tag ? `🏷️ ${tag.name}` : 'Filtered';
      if (clearBtn) clearBtn.style.display = 'block';
    } else {
      label.textContent = 'Recent Chats';
      if (clearBtn) clearBtn.style.display = 'none';
    }
  }

  // === Context Menu ===

  showContextMenu(event, sessionId) {
    event.preventDefault();
    event.stopPropagation();

    this.contextMenuSessionId = sessionId;
    const session = this.sessions.find(s => s.id === sessionId);

    if (!session) return;

    // Update pin menu text based on current state
    const pinText = this.elements.pinMenuText;
    if (pinText) {
      pinText.textContent = session.is_pinned ? 'Unpin' : 'Pin';
    }

    // Position the menu
    const menu = this.elements.sessionContextMenu;
    if (!menu) return;

    menu.style.display = 'block';

    // Get viewport dimensions
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const menuRect = menu.getBoundingClientRect();

    // Calculate position
    let x = event.clientX;
    let y = event.clientY;

    // Adjust if menu would go off-screen
    if (x + menuRect.width > viewportWidth) {
      x = viewportWidth - menuRect.width - 10;
    }
    if (y + menuRect.height > viewportHeight) {
      y = viewportHeight - menuRect.height - 10;
    }

    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
  }

  hideContextMenu() {
    const menu = this.elements.sessionContextMenu;
    if (menu) {
      menu.style.display = 'none';
    }
    // Don't clear contextMenuSessionId here - it's needed by modals that open from context menu
    // It will be cleared when the modals close
  }

  async handleContextMenuAction(action) {
    const sessionId = this.contextMenuSessionId;
    if (!sessionId) return;

    this.hideContextMenu();

    switch (action) {
      case 'pin':
        await this.toggleSessionPin(sessionId);
        break;
      case 'move':
        this.openMoveToFolderModal(sessionId);
        break;
      case 'project':
        this.openMoveToProjectModal(sessionId);
        break;
      case 'tags':
        this.openEditTagsModal(sessionId);
        break;
      case 'rename':
        await this.renameSession(sessionId);
        break;
      case 'delete':
        await this.deleteSession(sessionId);
        break;
    }
  }

  async toggleSessionPin(sessionId) {
    const session = this.sessions.find(s => s.id === sessionId);
    if (!session) return;

    try {
      await this.apiRequest(`/organize/sessions/${sessionId}/pin`, {
        method: 'PUT',
        body: JSON.stringify({ is_pinned: !session.is_pinned }),
      });
      await this.loadSessions();
    } catch (error) {
      console.error('Failed to toggle pin:', error);
    }
  }

  async renameSession(sessionId) {
    const session = this.sessions.find(s => s.id === sessionId);
    if (!session) return;

    const newTitle = prompt('Enter new name:', session.title);
    if (!newTitle || newTitle === session.title) return;

    try {
      await this.apiRequest(`/chat/sessions/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: newTitle }),
      });
      await this.loadSessions();

      // Update chat title if this is current session
      if (sessionId === this.currentSessionId) {
        this.elements.chatTitle.textContent = newTitle;
      }
    } catch (error) {
      console.error('Failed to rename session:', error);
      alert('Failed to rename chat');
    }
  }

  // === Move to Folder Modal ===

  openMoveToFolderModal(sessionId) {
    this.contextMenuSessionId = sessionId;
    const session = this.sessions.find(s => s.id === sessionId);

    const list = this.elements.folderSelectList;
    if (!list) return;

    // Clear existing items
    list.innerHTML = '';

    // Create "No Folder" option
    const noFolderItem = document.createElement('div');
    noFolderItem.className = `folder-select-item${!session?.folder_id ? ' selected' : ''}`;
    noFolderItem.dataset.folderId = '';
    noFolderItem.innerHTML = `
      <span class="folder-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
      </span>
      <span>No Folder</span>
    `;
    noFolderItem.addEventListener('click', (e) => {
      console.log('No Folder item clicked!');
      e.stopPropagation();
      this.moveSessionToFolder('');
    });
    list.appendChild(noFolderItem);

    // Create folder options (show global badge for global folders when in project view)
    console.log('Creating folder items, folders count:', this.folders.length);
    this.folders.forEach(folder => {
      const item = document.createElement('div');
      item.className = `folder-select-item${session?.folder_id === folder.id ? ' selected' : ''}`;
      item.dataset.folderId = folder.id;

      // Show global badge if folder is global and we're viewing a specific project
      const isGlobal = !folder.project_id;
      const showGlobalBadge = isGlobal && this.currentProjectId;
      const globalBadge = showGlobalBadge ? '<span class="folder-global-badge">Global</span>' : '';

      item.innerHTML = `
        <span class="folder-icon" style="color: ${folder.color || '#808080'}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none">
            <path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/>
          </svg>
        </span>
        <span>${this.escapeHtml(folder.name)}</span>
        ${globalBadge}
      `;
      console.log('Adding click listener for folder:', folder.id, folder.name);
      item.addEventListener('click', (e) => {
        console.log('Folder item clicked!', folder.id);
        e.stopPropagation();
        this.moveSessionToFolder(folder.id);
      });
      list.appendChild(item);
    });

    this.elements.moveToFolderModal.classList.add('visible');
  }

  closeMoveToFolderModal() {
    this.elements.moveToFolderModal.classList.remove('visible');
    this.contextMenuSessionId = null;
  }

  async moveSessionToFolder(folderId) {
    console.log('moveSessionToFolder called with folderId:', folderId);
    const sessionId = this.contextMenuSessionId;
    console.log('contextMenuSessionId:', sessionId);
    if (!sessionId) {
      console.error('No sessionId - returning early');
      return;
    }

    try {
      console.log('Making API request...');
      await this.apiRequest(`/organize/sessions/${sessionId}/folder`, {
        method: 'PUT',
        body: JSON.stringify({ folder_id: folderId || null }),
      });

      console.log('API request succeeded');
      this.closeMoveToFolderModal();
      await this.loadFolders();
      await this.loadSessions();
    } catch (error) {
      console.error('Failed to move session:', error);
      alert('Failed to move chat to folder');
    }
  }

  // === Move to Project Modal ===

  openMoveToProjectModal(sessionId) {
    this.contextMenuSessionId = sessionId;
    const session = this.sessions.find(s => s.id === sessionId);

    const list = this.elements.projectSelectList;
    if (!list) return;

    // Clear existing items
    list.innerHTML = '';

    // Create "No Project (All Chats)" option
    const noProjectItem = document.createElement('div');
    noProjectItem.className = `folder-select-item${!session?.project_id ? ' selected' : ''}`;
    noProjectItem.dataset.projectId = '';
    noProjectItem.innerHTML = `
      <span class="folder-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
      </span>
      <span>All Chats (No Project)</span>
    `;
    noProjectItem.addEventListener('click', (e) => {
      console.log('No Project item clicked!');
      e.stopPropagation();
      this.moveSessionToProject('');
    });
    list.appendChild(noProjectItem);

    // Create project options
    console.log('Creating project items, projects count:', this.projects.length);
    this.projects.forEach(project => {
      const item = document.createElement('div');
      item.className = `folder-select-item${session?.project_id === project.id ? ' selected' : ''}`;
      item.dataset.projectId = project.id;
      item.innerHTML = `
        <span class="folder-icon" style="color: ${project.color || '#007AFF'}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
          </svg>
        </span>
        <span>${this.escapeHtml(project.name)}</span>
      `;
      console.log('Adding click listener for project:', project.id, project.name);
      item.addEventListener('click', (e) => {
        console.log('Project item clicked!', project.id);
        e.stopPropagation();
        this.moveSessionToProject(project.id);
      });
      list.appendChild(item);
    });

    this.elements.moveToProjectModal.classList.add('visible');
  }

  closeMoveToProjectModal() {
    this.elements.moveToProjectModal.classList.remove('visible');
    this.contextMenuSessionId = null;
  }

  async moveSessionToProject(projectId) {
    console.log('moveSessionToProject called with projectId:', projectId);
    const sessionId = this.contextMenuSessionId;
    console.log('contextMenuSessionId:', sessionId);
    if (!sessionId) {
      console.error('No sessionId - returning early');
      return;
    }

    try {
      console.log('Making API request to move session to project...');
      await this.apiRequest(`/chat/sessions/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ project_id: projectId || null }),
      });

      console.log('API request succeeded');
      this.closeMoveToProjectModal();
      await this.loadSessions();
    } catch (error) {
      console.error('Failed to move session to project:', error);
      alert('Failed to move chat to project');
    }
  }

  // === Edit Tags Modal ===

  async openEditTagsModal(sessionId) {
    this.contextMenuSessionId = sessionId;

    // Get current tags for this session
    let sessionTags = [];
    try {
      sessionTags = await this.apiRequest(`/organize/sessions/${sessionId}/tags`);
    } catch (error) {
      console.error('Failed to get session tags:', error);
    }

    const sessionTagIds = sessionTags.map(t => t.id);
    const list = this.elements.tagsSelectList;
    if (!list) return;

    if (this.tags.length === 0) {
      list.innerHTML = '<p class="no-items">No tags available. Create one first.</p>';
    } else {
      list.innerHTML = this.tags.map(tag => `
        <label class="tag-select-item">
          <input type="checkbox" value="${tag.id}" ${sessionTagIds.includes(tag.id) ? 'checked' : ''}>
          <span class="tag-dot" style="background: ${tag.color || '#007AFF'}"></span>
          <span>${this.escapeHtml(tag.name)}</span>
        </label>
      `).join('');
    }

    this.elements.editTagsModal.classList.add('visible');
  }

  async closeEditTagsModal() {
    // Save selected tags
    const sessionId = this.contextMenuSessionId;
    if (sessionId) {
      const list = this.elements.tagsSelectList;
      const checkboxes = list?.querySelectorAll('input[type="checkbox"]');
      const selectedTagIds = [];

      checkboxes?.forEach(cb => {
        if (cb.checked) {
          selectedTagIds.push(cb.value);
        }
      });

      try {
        await this.apiRequest(`/organize/sessions/${sessionId}/tags`, {
          method: 'PUT',
          body: JSON.stringify({ tag_ids: selectedTagIds }),
        });
        await this.loadSessions();
      } catch (error) {
        console.error('Failed to update session tags:', error);
      }
    }

    this.elements.editTagsModal.classList.remove('visible');
    this.contextMenuSessionId = null;
  }

  // === Folder Context Menu ===

  showFolderContextMenu(event, folderId) {
    event.preventDefault();
    event.stopPropagation();

    this.contextMenuFolderId = folderId;

    const menu = this.elements.folderContextMenu;
    if (!menu) return;

    // Position the menu
    const x = event.clientX;
    const y = event.clientY;

    menu.style.display = 'block';
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;

    // Ensure menu stays within viewport
    const rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = `${window.innerWidth - rect.width - 10}px`;
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = `${window.innerHeight - rect.height - 10}px`;
    }
  }

  hideFolderContextMenu() {
    const menu = this.elements.folderContextMenu;
    if (menu) {
      menu.style.display = 'none';
    }
  }

  async handleFolderContextMenuAction(action) {
    const folderId = this.contextMenuFolderId;
    if (!folderId) return;

    this.hideFolderContextMenu();

    switch (action) {
      case 'assignProject':
        this.openAssignFolderToProjectModal(folderId);
        break;
      case 'editFolder':
        this.openEditFolderModal(folderId);
        break;
      case 'deleteFolder':
        await this.deleteFolder(folderId);
        break;
    }
  }

  // === Assign Folder to Project Modal ===

  openAssignFolderToProjectModal(folderId) {
    this.contextMenuFolderId = folderId;
    const folder = this.folders.find(f => f.id === folderId);

    const list = this.elements.folderProjectSelectList;
    if (!list) return;

    // Clear existing items
    list.innerHTML = '';

    // Create "Global (No Project)" option
    const globalItem = document.createElement('div');
    globalItem.className = `folder-select-item${!folder?.project_id ? ' selected' : ''}`;
    globalItem.dataset.projectId = '';
    globalItem.innerHTML = `
      <span class="folder-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>
      </span>
      <span>Global (Visible in all projects)</span>
    `;
    globalItem.addEventListener('click', () => this.assignFolderToProject(''));
    list.appendChild(globalItem);

    // Create project options
    this.projects.forEach(project => {
      const item = document.createElement('div');
      item.className = `folder-select-item${folder?.project_id === project.id ? ' selected' : ''}`;
      item.dataset.projectId = project.id;
      item.innerHTML = `
        <span class="folder-icon" style="color: ${project.color || '#007AFF'}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none">
            <rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>
          </svg>
        </span>
        <span>${this.escapeHtml(project.name)}</span>
      `;
      item.addEventListener('click', () => this.assignFolderToProject(project.id));
      list.appendChild(item);
    });

    this.elements.assignFolderToProjectModal.classList.add('visible');
  }

  closeAssignFolderToProjectModal() {
    this.elements.assignFolderToProjectModal.classList.remove('visible');
  }

  async assignFolderToProject(projectId) {
    const folderId = this.contextMenuFolderId;
    if (!folderId) return;

    try {
      await this.apiRequest(`/organize/folders/${folderId}/project`, {
        method: 'PUT',
        body: JSON.stringify({ project_id: projectId || null }),
      });

      this.closeAssignFolderToProjectModal();
      await this.loadFolders();
    } catch (error) {
      console.error('Failed to assign folder to project:', error);
      alert('Failed to assign folder to project');
    }
  }

  openEditFolderModal(folderId) {
    const folder = this.folders.find(f => f.id === folderId);
    if (!folder) return;

    this.editingFolderId = folderId;
    this.elements.folderModalTitle.textContent = 'Edit Folder';
    this.elements.folderNameInput.value = folder.name;
    this.elements.folderColorInput.value = folder.color || '#007AFF';

    // Set color picker
    const picker = this.elements.folderColorPicker;
    if (picker) {
      picker.querySelectorAll('.color-option').forEach(btn => btn.classList.remove('selected'));
      const colorBtn = picker.querySelector(`.color-option[data-color="${folder.color}"]`);
      if (colorBtn) {
        colorBtn.classList.add('selected');
      }
    }

    this.elements.createFolderModal.classList.add('visible');
  }

  async deleteFolder(folderId) {
    const folder = this.folders.find(f => f.id === folderId);
    if (!folder) return;

    const confirmMsg = folder.session_count > 0
      ? `Delete folder "${folder.name}"? ${folder.session_count} chat(s) will be moved to root.`
      : `Delete folder "${folder.name}"?`;

    if (!confirm(confirmMsg)) return;

    try {
      await this.apiRequest(`/organize/folders/${folderId}`, {
        method: 'DELETE',
      });
      await this.loadFolders();
      await this.loadSessions();
    } catch (error) {
      console.error('Failed to delete folder:', error);
      alert('Failed to delete folder');
    }
  }

  // === Chat Attachments ===

  handleChatAttachments(files) {
    if (!files || files.length === 0) return;

    const allowedTypes = [
      '.txt', '.md', '.pdf', '.docx', '.doc', '.csv', '.json',
      '.py', '.js', '.ts', '.html', '.css', '.xml', '.yaml', '.yml'
    ];

    for (const file of files) {
      const ext = '.' + file.name.split('.').pop().toLowerCase();

      if (!allowedTypes.includes(ext)) {
        console.warn(`Unsupported file type: ${file.name}`);
        continue;
      }

      // Check for duplicates
      if (this.attachments.some(a => a.name === file.name)) {
        continue;
      }

      // Add to attachments
      this.attachments.push({
        file,
        name: file.name,
        type: ext,
        size: file.size,
      });
    }

    this.renderAttachments();
    this.updateAttachmentIndicator();
  }

  removeAttachment(filename) {
    this.attachments = this.attachments.filter(a => a.name !== filename);
    this.renderAttachments();
    this.updateAttachmentIndicator();
  }

  clearAttachments() {
    this.attachments = [];
    this.renderAttachments();
    this.updateAttachmentIndicator();
  }

  renderAttachments() {
    const container = this.elements.attachmentsList;
    const area = this.elements.attachmentsArea;

    if (!container || !area) return;

    if (this.attachments.length === 0) {
      area.style.display = 'none';
      this.elements.attachBtn?.classList.remove('has-attachments');
      return;
    }

    area.style.display = 'block';
    this.elements.attachBtn?.classList.add('has-attachments');

    container.innerHTML = this.attachments.map(att => `
      <div class="attachment-chip" data-filename="${this.escapeHtml(att.name)}">
        <span class="attachment-icon">${this.getAttachmentIcon(att.type)}</span>
        <span class="attachment-name">${this.escapeHtml(att.name)}</span>
        <button class="attachment-remove" onclick="app.removeAttachment('${this.escapeHtml(att.name).replace(/'/g, "\\'")}')">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    `).join('');
  }

  updateAttachmentIndicator() {
    const indicator = this.elements.attachmentIndicator;
    if (!indicator) return;

    if (this.attachments.length > 0) {
      const totalSize = this.attachments.reduce((sum, a) => sum + a.size, 0);
      indicator.textContent = `${this.attachments.length} file${this.attachments.length > 1 ? 's' : ''} attached (${this.formatFileSize(totalSize)})`;
    } else {
      indicator.textContent = '';
    }
  }

  getAttachmentIcon(type) {
    const iconMap = {
      '.pdf': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
      '.txt': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
      '.md': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>',
      '.json': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><polyline points="4 17 4 20 20 20 20 17"/><line x1="9" y1="4" x2="9" y2="20"/></svg>',
      '.py': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
      '.js': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
      '.ts': '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    };
    return iconMap[type] || '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>';
  }

  async readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  async readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  }

  // === Projects ===

  async loadProjects() {
    try {
      this.projects = await this.apiRequest('/projects');
      this.renderProjects();
    } catch (error) {
      console.error('Failed to load projects:', error);
      this.projects = [];
    }
  }

  renderProjects() {
    const list = this.elements.projectDropdownList;
    const current = this.elements.projectCurrent;

    if (!list || !current) return;

    // Update current project display
    const currentProject = this.projects.find(p => p.id === this.currentProjectId);
    const projectName = current.querySelector('.project-name');
    const projectIcon = current.querySelector('.project-icon');

    if (currentProject) {
      projectName.textContent = currentProject.name;
      projectIcon.innerHTML = `<span class="project-color" style="background: ${currentProject.color}; width: 10px; height: 10px; border-radius: 50%;"></span>`;
    } else {
      projectName.textContent = 'All Chats';
      projectIcon.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      </svg>`;
    }

    // Clear existing items
    list.innerHTML = '';

    // Create "All Chats" item
    const allChatsItem = document.createElement('div');
    allChatsItem.className = `project-dropdown-item${!this.currentProjectId ? ' active' : ''}`;
    allChatsItem.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      </svg>
      <span>All Chats</span>
    `;
    allChatsItem.addEventListener('click', () => this.switchProject(null));
    list.appendChild(allChatsItem);

    // Create project items
    this.projects.forEach(project => {
      const item = document.createElement('div');
      item.className = `project-dropdown-item${project.id === this.currentProjectId ? ' active' : ''}`;
      item.innerHTML = `
        <span class="project-color" style="background: ${project.color || '#007AFF'}"></span>
        <span>${this.escapeHtml(project.name)}</span>
        <span style="font-size: 11px; color: var(--text-tertiary); margin-left: auto;">${project.session_count || 0}</span>
      `;
      item.addEventListener('click', () => this.switchProject(project.id));
      list.appendChild(item);
    });
  }

  async switchProject(projectId) {
    this.currentProjectId = projectId;
    this.elements.projectSwitcher?.classList.remove('open');
    this.renderProjects();

    // Clear tag filter when switching projects
    this.currentTagId = null;
    this.updateFilterLabel();

    // Reload folders filtered by the new project
    await this.loadFolders();
    this.renderTags();

    // Reload sessions for the new project
    await this.loadSessions();
  }

  openCreateProjectModal() {
    this.elements.projectNameInput.value = '';
    this.elements.projectDescInput.value = '';
    this.elements.projectColorInput.value = '#007AFF';
    this.elements.projectPromptInput.value = '';

    // Reset color picker
    this.elements.projectColorPicker?.querySelectorAll('.color-option').forEach(btn => btn.classList.remove('selected'));
    this.elements.projectColorPicker?.querySelector('.color-option[data-color="#007AFF"]')?.classList.add('selected');

    // Populate pocket select
    if (this.elements.projectPocketSelect && this.pockets) {
      this.elements.projectPocketSelect.innerHTML = '<option value="">None</option>' +
        this.pockets.map(p => `<option value="${p.id}">${this.escapeHtml(p.name)}</option>`).join('');
    }

    this.elements.createProjectModal?.classList.add('visible');
  }

  closeCreateProjectModal() {
    this.elements.createProjectModal?.classList.remove('visible');
  }

  async createProject() {
    const name = this.elements.projectNameInput.value.trim();
    const description = this.elements.projectDescInput.value.trim();
    const color = this.elements.projectColorInput.value;
    const defaultPocket = this.elements.projectPocketSelect?.value || null;
    const systemPrompt = this.elements.projectPromptInput.value.trim();

    if (!name) {
      alert('Please enter a project name');
      return;
    }

    try {
      await this.apiRequest('/projects', {
        method: 'POST',
        body: JSON.stringify({
          name,
          description: description || null,
          color,
          default_rag_pocket: defaultPocket,
          system_prompt: systemPrompt || null,
        }),
      });

      this.closeCreateProjectModal();
      await this.loadProjects();
    } catch (error) {
      console.error('Failed to create project:', error);
      alert('Failed to create project');
    }
  }

  // === Folder Watchers ===

  async openWatchersModal() {
    await this.loadWatchers();
    await this.loadWatcherStatus();
    this.elements.watchersModal?.classList.add('visible');
  }

  closeWatchersModal() {
    this.elements.watchersModal?.classList.remove('visible');
  }

  async loadWatchers() {
    try {
      this.watchers = await this.apiRequest('/watchers');
      this.renderWatchers();
    } catch (error) {
      console.error('Failed to load watchers:', error);
      this.watchers = [];
      this.renderWatchers();
    }
  }

  async loadWatcherStatus() {
    try {
      const status = await this.apiRequest('/watchers/status');
      const isRunning = status.running;

      this.elements.watcherStatus?.classList.toggle('running', isRunning);
      this.elements.watcherStatus?.classList.toggle('stopped', !isRunning);

      if (this.elements.watcherServiceStatus) {
        this.elements.watcherServiceStatus.textContent = isRunning
          ? `Running (${status.active_watchers} active)`
          : 'Stopped';
      }
    } catch (error) {
      console.error('Failed to load watcher status:', error);
      if (this.elements.watcherServiceStatus) {
        this.elements.watcherServiceStatus.textContent = 'Unknown';
      }
    }
  }

  renderWatchers() {
    const container = this.elements.watchersList;
    if (!container) return;

    container.innerHTML = '';

    if (this.watchers.length === 0) {
      container.innerHTML = `<div class="watcher-empty">No folder watchers configured</div>`;
      return;
    }

    this.watchers.forEach(watcher => {
      const item = document.createElement('div');
      item.className = `watcher-item ${watcher.is_active ? '' : 'inactive'}`;
      item.dataset.id = watcher.id;
      item.innerHTML = `
        <div class="watcher-toggle">
          <input type="checkbox" ${watcher.is_active ? 'checked' : ''}>
        </div>
        <div class="watcher-info">
          <div class="watcher-name">
            ${this.escapeHtml(watcher.name)}
            <span class="watcher-badge ${watcher.is_active ? '' : 'inactive'}">
              ${watcher.is_active ? 'Active' : 'Paused'}
            </span>
          </div>
          <div class="watcher-path" title="${this.escapeHtml(watcher.path)}">${this.escapeHtml(watcher.path)}</div>
          <div class="watcher-meta">
            <span>Pocket: ${this.escapeHtml(watcher.pocket_id)}</span>
            <span>${watcher.recursive ? 'Recursive' : 'Single folder'}</span>
            <span>${watcher.file_count || 0} files</span>
          </div>
        </div>
        <div class="watcher-actions">
          <button class="watcher-action-btn scan" title="Scan now">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
          <button class="watcher-action-btn edit" title="Edit">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </button>
          <button class="watcher-action-btn delete" title="Delete">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      `;

      // Add event listeners
      const checkbox = item.querySelector('input[type="checkbox"]');
      checkbox?.addEventListener('change', (e) => this.toggleWatcher(watcher.id, e.target.checked));

      const scanBtn = item.querySelector('.watcher-action-btn.scan');
      scanBtn?.addEventListener('click', () => this.scanWatcher(watcher.id));

      const editBtn = item.querySelector('.watcher-action-btn.edit');
      editBtn?.addEventListener('click', () => this.editWatcher(watcher.id));

      const deleteBtn = item.querySelector('.watcher-action-btn.delete');
      deleteBtn?.addEventListener('click', () => this.deleteWatcher(watcher.id));

      container.appendChild(item);
    });
  }

  async openWatcherForm(watcherId = null) {
    // Reset form
    this.elements.watcherEditId.value = watcherId || '';
    this.elements.watcherNameInput.value = '';
    this.elements.watcherPathInput.value = '';
    this.elements.watcherPatternsInput.value = '*.txt,*.md,*.pdf,*.docx';
    this.elements.watcherRecursiveCheck.checked = false;
    this.elements.watcherInitialScanCheck.checked = true;

    // Populate pocket select
    if (this.elements.watcherPocketSelect && this.pockets) {
      this.elements.watcherPocketSelect.innerHTML = this.pockets
        .map(p => `<option value="${p.id}">${this.escapeHtml(p.name)}</option>`)
        .join('');
    }

    // If editing, load watcher data
    if (watcherId) {
      this.elements.watcherFormTitle.textContent = 'Edit Folder Watcher';
      this.elements.saveWatcherBtn.textContent = 'Save Changes';

      const watcher = this.watchers.find(w => w.id === watcherId);
      if (watcher) {
        this.elements.watcherNameInput.value = watcher.name;
        this.elements.watcherPathInput.value = watcher.path;
        this.elements.watcherPocketSelect.value = watcher.pocket_id;
        this.elements.watcherPatternsInput.value = Array.isArray(watcher.file_patterns)
          ? watcher.file_patterns.join(',')
          : watcher.file_patterns;
        this.elements.watcherRecursiveCheck.checked = watcher.recursive;
        this.elements.watcherInitialScanCheck.checked = false;
      }
    } else {
      this.elements.watcherFormTitle.textContent = 'Add Folder Watcher';
      this.elements.saveWatcherBtn.textContent = 'Add Watcher';
    }

    this.elements.watcherFormModal?.classList.add('visible');
  }

  closeWatcherForm() {
    this.elements.watcherFormModal?.classList.remove('visible');
  }

  editWatcher(watcherId) {
    this.openWatcherForm(watcherId);
  }

  async saveWatcher() {
    const watcherId = this.elements.watcherEditId.value;
    const name = this.elements.watcherNameInput.value.trim();
    const path = this.elements.watcherPathInput.value.trim();
    const pocketId = this.elements.watcherPocketSelect?.value;
    const patterns = this.elements.watcherPatternsInput.value.trim()
      .split(',')
      .map(p => p.trim())
      .filter(p => p);
    const recursive = this.elements.watcherRecursiveCheck.checked;
    const initialScan = this.elements.watcherInitialScanCheck.checked;

    if (!name || !path || !pocketId) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      if (watcherId) {
        // Update existing watcher
        await this.apiRequest(`/watchers/${watcherId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            name,
            path,
            pocket_id: pocketId,
            file_patterns: patterns,
            recursive,
          }),
        });
      } else {
        // Create new watcher
        await this.apiRequest('/watchers', {
          method: 'POST',
          body: JSON.stringify({
            name,
            path,
            pocket_id: pocketId,
            file_patterns: patterns,
            recursive,
            initial_scan: initialScan,
          }),
        });
      }

      this.closeWatcherForm();
      await this.loadWatchers();
      await this.loadWatcherStatus();
    } catch (error) {
      console.error('Failed to save watcher:', error);
      alert('Failed to save watcher');
    }
  }

  async toggleWatcher(watcherId, active) {
    try {
      await this.apiRequest(`/watchers/${watcherId}/active`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: active }),
      });
      await this.loadWatchers();
      await this.loadWatcherStatus();
    } catch (error) {
      console.error('Failed to toggle watcher:', error);
    }
  }

  async scanWatcher(watcherId) {
    try {
      const result = await this.apiRequest(`/watchers/${watcherId}/scan`, {
        method: 'POST',
      });

      alert(`Scan complete: ${result.files_ingested}/${result.files_found} files ingested`);
      await this.loadWatchers();
    } catch (error) {
      console.error('Failed to scan watcher:', error);
      alert('Failed to scan watcher');
    }
  }

  async deleteWatcher(watcherId) {
    if (!confirm('Are you sure you want to delete this folder watcher?')) {
      return;
    }

    try {
      await this.apiRequest(`/watchers/${watcherId}`, {
        method: 'DELETE',
      });
      await this.loadWatchers();
      await this.loadWatcherStatus();
    } catch (error) {
      console.error('Failed to delete watcher:', error);
      alert('Failed to delete watcher');
    }
  }
}

// Initialize app
const app = new MacAssistant();
