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

    // Initialize
    this.init();
  }

  async init() {
    this.cacheElements();
    this.bindEvents();
    await this.loadSettings();
    await this.checkConnection();
    await this.loadSessions();
    this.setupElectronListeners();
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
    };
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
      });
    });

    // Message input
    this.elements.messageInput.addEventListener('input', () => this.handleInputChange());
    this.elements.messageInput.addEventListener('keydown', (e) => this.handleInputKeydown(e));
    this.elements.sendBtn.addEventListener('click', () => this.sendMessage());

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
      const data = await this.apiRequest('/models/available');

      this.elements.modelSelect.innerHTML = '';
      data.models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.alias || model.model_id;
        option.textContent = `${model.alias || model.model_id} (${model.model_id})`;
        option.selected = model.alias === data.current_model;
        this.elements.modelSelect.appendChild(option);
      });
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  }

  // === Session Management ===

  async loadSessions() {
    try {
      this.sessions = await this.apiRequest('/chat/sessions');
      this.renderSessions();
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }

  renderSessions() {
    const container = this.elements.sessionsContainer;
    container.innerHTML = '';

    if (this.sessions.length === 0) {
      container.innerHTML = '<p class="no-sessions">No recent chats</p>';
      return;
    }

    this.sessions.forEach(session => {
      const item = document.createElement('div');
      item.className = `session-item${session.id === this.currentSessionId ? ' active' : ''}`;
      item.dataset.sessionId = session.id;

      const date = new Date(session.updated_at);
      const timeStr = date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      item.innerHTML = `
        <div class="session-title">${this.escapeHtml(session.title)}</div>
        <div class="session-meta">
          <span>${timeStr}</span>
          ${session.rag_pocket ? `<span class="session-pocket">${session.rag_pocket}</span>` : ''}
        </div>
      `;

      item.addEventListener('click', () => this.loadSession(session.id));
      container.appendChild(item);
    });
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
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      this.sendMessage();
    }
  }

  async sendMessage() {
    const message = this.elements.messageInput.value.trim();
    if (!message || this.isStreaming) return;

    // Clear input
    this.elements.messageInput.value = '';
    this.handleInputChange();

    // Hide welcome message
    this.elements.welcomeMessage.style.display = 'none';

    // Add user message to UI
    this.addMessageToUI('user', message);

    // Create assistant message placeholder
    const assistantDiv = this.addMessageToUI('assistant', '', true);
    const bubbleDiv = assistantDiv.querySelector('.message-bubble');

    this.isStreaming = true;
    this.elements.sendBtn.disabled = true;

    try {
      await this.streamResponse(message, bubbleDiv);
    } catch (error) {
      console.error('Stream error:', error);
      bubbleDiv.innerHTML = `<span style="color: var(--error-color)">Error: ${error.message}</span>`;
    } finally {
      this.isStreaming = false;
      this.handleInputChange();
    }

    // Refresh sessions list
    await this.loadSessions();
  }

  async streamResponse(message, bubbleDiv) {
    const body = {
      message,
      session_id: this.currentSessionId,
      rag_pocket: this.currentPocket,
      temperature: this.settings.temperature,
      max_tokens: this.settings.maxTokens,
      include_history: true,
    };

    const response = await fetch(`${this.apiBase}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
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

  addMessageToUI(role, content, isStreaming = false) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (isStreaming) {
      bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    } else {
      bubble.innerHTML = this.formatMessage(content);
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
    if (selectedModel) {
      try {
        await this.apiRequest('/models/switch', {
          method: 'POST',
          body: JSON.stringify({ model: selectedModel }),
        });
      } catch (error) {
        console.error('Failed to switch model:', error);
      }
    }

    this.closeSettings();
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
}

// Initialize app
const app = new MacAssistant();
