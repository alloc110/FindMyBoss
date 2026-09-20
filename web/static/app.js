/**
 * FindMyBoss Frontend Application Logic
 * Manages job browsing, search/filter, status tracking, job deletion,
 * Gemini AI tailoring, master CV PDF upload, ATS/CV rules, Overleaf LaTeX Studio,
 * unified Settings (AI Models, API Key, Theme, Profile, Scraper), and State Persistence.
 */

// Application State with Persistence
const state = {
  jobs: [],
  selectedJobId: parseInt(localStorage.getItem('findmyboss_selected_job_id'), 10) || null,
  activeFilter: localStorage.getItem('findmyboss_active_filter') || 'all',
  searchQuery: localStorage.getItem('findmyboss_search_query') || '',
  currentTab: localStorage.getItem('findmyboss_current_tab') || 'jd',
  profile: null,
  settings: {
    ai_provider: 'gemini',
    ai_model: 'gemini-2.5-flash',
    gemini_model: 'gemini-2.5-flash',
    has_api_key: false,
    masked_api_key: '',
    theme: 'dark',
  },
  modelCatalog: null,
};

const FALLBACK_MODEL_CATALOG = {
  gemini: {
    name: 'Google Gemini',
    key_label: 'Google Gemini API Key',
    placeholder: 'Dán mã API Key của bạn (bắt đầu bằng AIzaSy...)',
    hint: 'Lấy API Key miễn phí tại Google AI Studio (aistudio.google.com). Nếu để trống, hệ thống sẽ chạy ở Chế độ Mô phỏng Thông minh.',
    models: [
      { id: 'gemini-3.8-flash', name: 'Gemini 3.8 Flash (High)', desc: 'Mô hình Gemini 3.8 Flash thế hệ mới - Siêu tốc độ, suy luận logic vượt trội', tag: 'Mới nhất 3.8' },
      { id: 'gemini-3.0-pro', name: 'Gemini 3.0 Pro', desc: 'Mô hình Gemini 3.0 Pro Flagship - Tư duy chiều sâu, giải quyết vấn đề phức tạp', tag: 'Flagship 3.0' },
      { id: 'gemini-3.0-flash', name: 'Gemini 3.0 Flash', desc: 'Mô hình Gemini 3.0 Flash - Cân bằng hoàn hảo tốc độ và độ chính xác', tag: 'Mới nhất 3.0' },
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', desc: 'Khuyên dùng - Cực nhanh, thông minh & chuẩn xác nhất', tag: 'Khuyên dùng' },
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', desc: 'Lập luận sâu, phân tích JD học thuật & tối ưu CV toàn diện', tag: 'Lý luận sâu' },
      { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', desc: 'Tốc độ cao thế hệ mới, đa phương thức tối ưu', tag: 'Tốc độ cao' },
      { id: 'gemini-2.0-flash-thinking-exp-01-21', name: 'Gemini 2.0 Flash Thinking', desc: 'Suy luận logic từng bước, tối ưu từ khóa ATS chuyên sâu', tag: 'Tư duy AI' },
      { id: 'gemini-2.0-pro-exp-02-05', name: 'Gemini 2.0 Pro Experimental', desc: 'Mô hình lập trình & coding mạnh mẽ nhất của Google', tag: 'Chuyên gia Tech' },
      { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', desc: 'Cửa sổ ngữ cảnh 2M token siêu lớn cho JD dài', tag: 'Ngữ cảnh lớn' },
      { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', desc: 'Tiết kiệm token & phản hồi nhanh', tag: 'Tiết kiệm' },
      { id: 'custom', name: 'Mô hình Gemini tùy chỉnh...', desc: 'Tự nhập ID mô hình (VD: gemini-3.0-ultra, preview...)', tag: 'Tùy biến' }
    ]
  },
  openai: {
    name: 'OpenAI / ChatGPT',
    key_label: 'OpenAI API Key',
    placeholder: 'Dán mã OpenAI API Key của bạn (bắt đầu bằng sk-...)',
    hint: 'Lấy API Key tại platform.openai.com/api-keys. Hỗ trợ các dòng GPT-4o, GPT-3.5-Turbo và dòng suy luận o1/o3.',
    models: [
      { id: 'gpt-4o', name: 'GPT-4o', desc: 'Mô hình đa phương thức hàng đầu, hiểu sâu JD và gợi ý ATS xuất sắc', tag: 'Flagship' },
      { id: 'gpt-4o-mini', name: 'GPT-4o Mini', desc: 'Chi phí cực rẻ, tốc độ cao, hoàn hảo cho tạo gợi ý CV', tag: 'Tiết kiệm' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', desc: 'Dòng mô hình ChatGPT kinh điển, tốc độ ổn định', tag: 'Kinh điển' },
      { id: 'o1-mini', name: 'o1-mini (Reasoning)', desc: 'Mô hình tư duy chuyên sâu cho CV Tech & Kỹ thuật cao', tag: 'Suy luận' },
      { id: 'o3-mini', name: 'o3-mini (Reasoning)', desc: 'Thế hệ mô hình lý luận mới nhất của OpenAI', tag: 'Lý luận cao cấp' },
      { id: 'custom', name: 'Tùy chỉnh mã model khác...', desc: 'Nhập model OpenAI tùy chỉnh (vd: ft:gpt-4o-mini...)', tag: 'Tùy biến' }
    ]
  },
  claude: {
    name: 'Anthropic Claude',
    key_label: 'Anthropic Claude API Key',
    placeholder: 'Dán mã Anthropic API Key của bạn (bắt đầu bằng sk-ant-...)',
    hint: 'Lấy API Key tại console.anthropic.com. Claude nổi tiếng về chất lượng viết văn tự nhiên, học thuật và chính xác.',
    models: [
      { id: 'claude-3-7-sonnet-latest', name: 'Claude 3.7 Sonnet', desc: 'Mô hình thông minh nhất của Anthropic với khả năng Hybrid Reasoning', tag: 'Mới nhất' },
      { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet (v2)', desc: 'Chuẩn mực ngành về viết CV, ngữ điệu chuyên nghiệp và chuẩn ATS', tag: 'Khuyên dùng' },
      { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', desc: 'Tốc độ phản hồi tức thì với chi phí tối ưu', tag: 'Tốc độ' },
      { id: 'claude-3-opus-20240229', name: 'Claude 3 Opus', desc: 'Khả năng viết sâu, tinh tế và xử lý ngôn từ phức tạp', tag: 'Chuyên sâu' },
      { id: 'custom', name: 'Tùy chỉnh mã model khác...', desc: 'Nhập mã model Claude tùy chỉnh', tag: 'Tùy biến' }
    ]
  },
  custom: {
    name: 'Tùy biến / DeepSeek / Local LLM',
    key_label: 'Custom API Key (Tùy chọn)',
    placeholder: 'Dán mã API Key (sk-...) hoặc để trống nếu chạy Ollama local',
    hint: 'Tương thích với mọi API chuẩn OpenAI: DeepSeek (api.deepseek.com), Ollama (localhost:11434), vLLM, OpenRouter.',
    models: [
      { id: 'deepseek-chat', name: 'DeepSeek-V3 (deepseek-chat)', desc: 'Chi phí siêu rẻ, năng lực tương đương GPT-4o', tag: 'Hiệu năng cao' },
      { id: 'deepseek-reasoner', name: 'DeepSeek-R1 (deepseek-reasoner)', desc: 'Mô hình suy luận mã nguồn mở hàng đầu', tag: 'Suy luận' },
      { id: 'qwen-2.5-72b', name: 'Qwen 2.5 72B', desc: 'Đa ngôn ngữ vượt trội, viết tiếng Việt cực kỳ tự nhiên', tag: 'Mã nguồn mở' },
      { id: 'llama-3.3-70b', name: 'Llama 3.3 70B', desc: 'Mô hình mã nguồn mở mạnh mẽ từ Meta', tag: 'Mã nguồn mở' },
      { id: 'custom', name: 'Tùy chỉnh mã model khác...', desc: 'Nhập mã model theo endpoint của bạn', tag: 'Tùy biến' }
    ]
  }
};

const STATUS_LABELS = {
  saved: 'Chưa nộp',
  applied: 'Đã nộp CV',
  interviewing: 'Đang phỏng vấn',
  offered: 'Nhận Offer',
  rejected: 'Bị từ chối',
};

// DOM Elements
const elements = {
  // Stats & Brand
  statTotalJobs: document.getElementById('statTotalJobs'),
  statTotalCvs: document.getElementById('statTotalCvs'),
  geminiStatusPill: document.getElementById('geminiStatusPill'),
  geminiStatusText: document.getElementById('geminiStatusText'),

  // Search & List
  searchInput: document.getElementById('searchInput'),
  jobsList: document.getElementById('jobsList'),
  filterChips: document.querySelectorAll('.filter-chip'),

  // Detail Pane
  detailPane: document.getElementById('detailPane'),
  emptyDetail: document.getElementById('emptyDetail'),
  detailJobTitle: document.getElementById('detailJobTitle'),
  detailJobCompany: document.getElementById('detailJobCompany'),
  detailJobLink: document.getElementById('detailJobLink'),
  detailJobSalary: document.getElementById('detailJobSalary'),
  detailJobAddress: document.getElementById('detailJobAddress'),

  // Status & Delete Actions
  detailJobStatusSelect: document.getElementById('detailJobStatusSelect'),
  btnDeleteJob: document.getElementById('btnDeleteJob'),

  // AI Tailor Actions
  btnTailorCv: document.getElementById('btnTailorCv'),
  btnTailorText: document.getElementById('btnTailorText'),
  btnTailorSpinner: document.getElementById('btnTailorSpinner'),

  // Main Tabs
  tabButtons: document.querySelectorAll('.tab-btn'),
  tabPanes: document.querySelectorAll('.tab-pane'),

  // Tab 1: JD
  jdSkillsCard: document.getElementById('jdSkillsCard'),
  jdSkillsRow: document.getElementById('jdSkillsRow'),
  jdDescriptionCard: document.getElementById('jdDescriptionCard'),
  jdDescription: document.getElementById('jdDescription'),
  jdRequirementsCard: document.getElementById('jdRequirementsCard'),
  jdRequirements: document.getElementById('jdRequirements'),
  jdBenefitsCard: document.getElementById('jdBenefitsCard'),
  jdBenefits: document.getElementById('jdBenefits'),
  jdFullRaw: document.getElementById('jdFullRaw'),

  // Tab 2: AI CV Studio
  aiMatchScore: document.getElementById('aiMatchScore'),
  aiMatchAnalysis: document.getElementById('aiMatchAnalysis'),
  missingKeywordsList: document.getElementById('missingKeywordsList'),
  tailoredSummaryText: document.getElementById('tailoredSummaryText'),
  tailoredBulletsList: document.getElementById('tailoredBulletsList'),

  // Tab 3: Overleaf LaTeX Studio & PDF Preview
  pdfFrame: document.getElementById('pdfFrame'),
  btnDownloadPdf: document.getElementById('btnDownloadPdf'),
  btnOpenPdfNewTab: document.getElementById('btnOpenPdfNewTab'),
  latexSourceText: document.getElementById('latexSourceText'),
  btnRecompileLatex: document.getElementById('btnRecompileLatex'),
  btnRecompileText: document.getElementById('btnRecompileText'),
  templateSelector: document.getElementById('templateSelector'),
  overleafCompileStatus: document.getElementById('overleafCompileStatus'),
  overleafCharCount: document.getElementById('overleafCharCount'),

  // AI Sync Banner
  aiSyncBanner: document.getElementById('aiSyncBanner'),
  aiSyncStatusText: document.getElementById('aiSyncStatusText'),
  btnQuickEditRules: document.getElementById('btnQuickEditRules'),

  // Unified Settings Modal
  btnOpenSettings: document.getElementById('btnOpenSettings'),
  settingsModal: document.getElementById('settingsModal'),
  btnCloseSettings: document.getElementById('btnCloseSettings'),
  btnCancelSettings: document.getElementById('btnCancelSettings'),
  btnSaveSettings: document.getElementById('btnSaveSettings'),
  modalTabButtons: document.querySelectorAll('.modal-tab-btn'),
  modalTabPanes: document.querySelectorAll('.modal-tab-pane'),

  // Quick Scrape Modal & Live Status
  btnQuickScrape: document.getElementById('btnQuickScrape'),
  scrapeModal: document.getElementById('scrapeModal'),
  btnCloseScrapeModal: document.getElementById('btnCloseScrapeModal'),
  btnCancelScrapeModal: document.getElementById('btnCancelScrapeModal'),
  btnStartScrape: document.getElementById('btnStartScrape'),
  btnStartScrapeSpinner: document.getElementById('btnStartScrapeSpinner'),
  btnStartScrapeText: document.getElementById('btnStartScrapeText'),
  btnSelectAllPortals: document.getElementById('btnSelectAllPortals'),
  btnDeselectAllPortals: document.getElementById('btnDeselectAllPortals'),
  scrapeModalStatusBox: document.getElementById('scrapeModalStatusBox'),
  scrapeModalStatusTitle: document.getElementById('scrapeModalStatusTitle'),
  scrapeModalStatusDetail: document.getElementById('scrapeModalStatusDetail'),
  scrapeModalTimer: document.getElementById('scrapeModalTimer'),
  scraperStatusPill: document.getElementById('scraperStatusPill'),
  scraperStatusText: document.getElementById('scraperStatusText'),
  quickScrapeToday: document.getElementById('quickScrapeToday'),
  quickScrapeMaxPages: document.getElementById('quickScrapeMaxPages'),

  // Settings Tab 1: AI Model & API Key
  settingAiProvider: document.getElementById('settingAiProvider'),
  settingAiModel: document.getElementById('settingAiModel'),
  groupCustomModel: document.getElementById('groupCustomModel'),
  settingCustomModel: document.getElementById('settingCustomModel'),
  groupCustomBaseUrl: document.getElementById('groupCustomBaseUrl'),
  settingCustomBaseUrl: document.getElementById('settingCustomBaseUrl'),
  lblApiKey: document.getElementById('lblApiKey'),
  settingApiKey: document.getElementById('settingApiKey'),
  btnToggleApiKey: document.getElementById('btnToggleApiKey'),
  btnTestApiKey: document.getElementById('btnTestApiKey'),
  btnTestApiKeyIcon: document.getElementById('btnTestApiKeyIcon'),
  hintApiKey: document.getElementById('hintApiKey'),
  testApiKeyResult: document.getElementById('testApiKeyResult'),
  settingAiStatusBox: document.getElementById('settingAiStatusBox'),
  settingStatusDot: document.getElementById('settingStatusDot'),
  settingAiStatusDetail: document.getElementById('settingAiStatusDetail'),
  // Backward-compatibility aliases
  settingGeminiModel: document.getElementById('settingAiModel'),
  settingGeminiApiKey: document.getElementById('settingApiKey'),

  // Settings Tab 2: Theme Options
  themeOptDark: document.getElementById('themeOptDark'),
  themeOptLight: document.getElementById('themeOptLight'),
  checkDark: document.getElementById('checkDark'),
  checkLight: document.getElementById('checkLight'),

  // Settings Tab 3: Master PDF & Profile
  dropzoneCv: document.getElementById('dropzoneCv'),
  fileMasterCv: document.getElementById('fileMasterCv'),
  masterCvInfoBox: document.getElementById('masterCvInfoBox'),
  badgeFileName: document.getElementById('badgeFileName'),
  badgeFileMeta: document.getElementById('badgeFileMeta'),
  btnChangePdf: document.getElementById('btnChangePdf'),
  extractedTextPreview: document.getElementById('extractedTextPreview'),
  inputProfileName: document.getElementById('inputProfileName'),
  inputProfileTitle: document.getElementById('inputProfileTitle'),
  inputProfileEmail: document.getElementById('inputProfileEmail'),
  inputProfilePhone: document.getElementById('inputProfilePhone'),
  inputProfileLocation: document.getElementById('inputProfileLocation'),
  inputProfileSummary: document.getElementById('inputProfileSummary'),

  // Settings Tab 4: Rules
  inputAtsRules: document.getElementById('inputAtsRules'),
  inputCvRules: document.getElementById('inputCvRules'),

  // Settings Tab 5: Scraper
  btnRunScraper: document.getElementById('btnRunScraper'),
  scraperKeywords: document.getElementById('scraperKeywords'),
  scraperBlacklist: document.getElementById('scraperBlacklist'),
  scraperMaxPages: document.getElementById('scraperMaxPages'),
  scraperDelay: document.getElementById('scraperDelay'),
  portalCheckboxes: {
    itviec: document.getElementById('portalItviec'),
    topdev: document.getElementById('portalTopdev'),
    topcv: document.getElementById('portalTopcv'),
    vietnamworks: document.getElementById('portalVietnamworks'),
    jobsgo: document.getElementById('portalJobsgo'),
    indeed: document.getElementById('portalIndeed'),
  },
};

// -------------------------------------------------------------
// Initialization
// -------------------------------------------------------------
async function initApp() {
  initTheme();
  restoreSavedUiState();
  setupEventListeners();
  await loadSettings();
  await loadStats();
  await loadJobs();
  await loadProfileData();
  await loadScraperConfig();
  checkScraperStatus();
}

function restoreSavedUiState() {
  // Restore search query
  if (state.searchQuery && elements.searchInput) {
    elements.searchInput.value = state.searchQuery;
  }

  // Restore active filter chip
  if (elements.filterChips) {
    elements.filterChips.forEach((chip) => {
      if (chip.dataset.filter === state.activeFilter) {
        chip.classList.add('active');
      } else {
        chip.classList.remove('active');
      }
    });
  }

  // Restore active tab
  if (state.currentTab) {
    switchTab(state.currentTab, false);
  }
}

function initTheme() {
  const savedTheme = localStorage.getItem('findmyboss_theme') || 'dark';
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  if (theme === 'light') {
    document.body.classList.add('theme-light');
    if (elements.checkDark) elements.checkDark.style.display = 'none';
    if (elements.checkLight) elements.checkLight.style.display = 'inline-block';
    if (elements.themeOptDark) elements.themeOptDark.classList.remove('active');
    if (elements.themeOptLight) elements.themeOptLight.classList.add('active');
  } else {
    document.body.classList.remove('theme-light');
    if (elements.checkDark) elements.checkDark.style.display = 'inline-block';
    if (elements.checkLight) elements.checkLight.style.display = 'none';
    if (elements.themeOptDark) elements.themeOptDark.classList.add('active');
    if (elements.themeOptLight) elements.themeOptLight.classList.remove('active');
  }
  state.settings.theme = theme;
  localStorage.setItem('findmyboss_theme', theme);
}

function setupEventListeners() {
  // Search with debounce & state persistence
  let debounceTimeout;
  elements.searchInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(() => {
      state.searchQuery = e.target.value.trim();
      localStorage.setItem('findmyboss_search_query', state.searchQuery);
      loadJobs();
    }, 250);
  });

  // Filter Chips & persistence
  elements.filterChips.forEach((chip) => {
    chip.addEventListener('click', () => {
      elements.filterChips.forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      state.activeFilter = chip.dataset.filter;
      localStorage.setItem('findmyboss_active_filter', state.activeFilter);
      loadJobs();
    });
  });

  // Main Tab Switching & persistence
  elements.tabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  // Tailor CV Button
  elements.btnTailorCv.addEventListener('click', () => {
    if (state.selectedJobId) {
      triggerTailorCv(state.selectedJobId);
    }
  });

  // Status Change Listener
  if (elements.detailJobStatusSelect) {
    elements.detailJobStatusSelect.addEventListener('change', async (e) => {
      if (!state.selectedJobId) return;
      const newStatus = e.target.value;
      try {
        const res = await fetch(`/api/jobs/${state.selectedJobId}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Không thể cập nhật trạng thái');
        }

        const currentJob = state.jobs.find((j) => j.id === state.selectedJobId);
        if (currentJob) {
          currentJob.status = newStatus;
        }
        renderJobsList(state.jobs);
      } catch (err) {
        alert('Lỗi cập nhật trạng thái: ' + err.message);
      }
    });
  }

  // Delete Job Listener
  if (elements.btnDeleteJob) {
    elements.btnDeleteJob.addEventListener('click', async () => {
      if (!state.selectedJobId) return;
      const currentJob = state.jobs.find((j) => j.id === state.selectedJobId);
      const jobTitle = currentJob ? currentJob.title : 'công việc này';
      const confirmed = confirm(`Bạn có chắc chắn muốn xóa "${jobTitle}" khỏi danh sách? Thao tác này sẽ xóa công việc và toàn bộ CV đã tạo liên quan.`);
      if (!confirmed) return;

      try {
        const res = await fetch(`/api/jobs/${state.selectedJobId}`, {
          method: 'DELETE',
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Không thể xóa công việc');
        }

        const deletedId = state.selectedJobId;
        localStorage.removeItem('findmyboss_draft_latex_' + deletedId);
        state.jobs = state.jobs.filter((j) => j.id !== deletedId);
        state.selectedJobId = null;
        localStorage.removeItem('findmyboss_selected_job_id');

        await loadStats();
        renderJobsList(state.jobs);

        if (state.jobs.length > 0) {
          selectJob(state.jobs[0].id);
        } else {
          renderEmptyState();
        }
      } catch (err) {
        alert('Lỗi khi xóa công việc: ' + err.message);
      }
    });
  }

  // Overleaf LaTeX Recompile Button
  if (elements.btnRecompileLatex) {
    elements.btnRecompileLatex.addEventListener('click', () => {
      if (state.selectedJobId) {
        triggerRecompileLatex(state.selectedJobId);
      }
    });
  }

  // LaTeX Source Textarea live count & draft auto-save
  if (elements.latexSourceText) {
    elements.latexSourceText.addEventListener('input', () => {
      updateLatexCharCount();
      if (state.selectedJobId) {
        localStorage.setItem('findmyboss_draft_latex_' + state.selectedJobId, elements.latexSourceText.value);
      }
    });
  }

  // Quick Edit Rules in AI Banner
  if (elements.btnQuickEditRules) {
    elements.btnQuickEditRules.addEventListener('click', () => {
      openSettingsModal('rules');
    });
  }

  // Settings Modal Handlers
  if (elements.btnOpenSettings) {
    elements.btnOpenSettings.addEventListener('click', () => openSettingsModal('ai-model'));
  }
  if (elements.btnCloseSettings) {
    elements.btnCloseSettings.addEventListener('click', closeSettingsModal);
  }
  if (elements.btnCancelSettings) {
    elements.btnCancelSettings.addEventListener('click', closeSettingsModal);
  }
  if (elements.btnSaveSettings) {
    elements.btnSaveSettings.addEventListener('click', () => saveAllSettings(true));
  }
  if (elements.settingsModal) {
    elements.settingsModal.addEventListener('click', (e) => {
      if (e.target === elements.settingsModal) closeSettingsModal();
    });
  }

  // Quick Scrape Modal Handlers
  if (elements.btnQuickScrape) {
    elements.btnQuickScrape.addEventListener('click', openScrapeModal);
  }
  if (elements.btnCloseScrapeModal) {
    elements.btnCloseScrapeModal.addEventListener('click', closeScrapeModal);
  }
  if (elements.btnCancelScrapeModal) {
    elements.btnCancelScrapeModal.addEventListener('click', closeScrapeModal);
  }
  if (elements.scrapeModal) {
    elements.scrapeModal.addEventListener('click', (e) => {
      if (e.target === elements.scrapeModal) closeScrapeModal();
    });
  }
  if (elements.btnStartScrape) {
    elements.btnStartScrape.addEventListener('click', startQuickScrape);
  }
  if (elements.btnSelectAllPortals) {
    elements.btnSelectAllPortals.addEventListener('click', () => {
      document.querySelectorAll('.portal-checkbox-grid input[type="checkbox"]').forEach((cb) => (cb.checked = true));
    });
  }
  if (elements.btnDeselectAllPortals) {
    elements.btnDeselectAllPortals.addEventListener('click', () => {
      document.querySelectorAll('.portal-checkbox-grid input[type="checkbox"]').forEach((cb) => (cb.checked = false));
    });
  }

  // Settings Tab Switching
  elements.modalTabButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      switchSettingsTab(btn.dataset.modaltab);
    });
  });

  // Settings: Provider dropdown change
  if (elements.settingAiProvider) {
    elements.settingAiProvider.addEventListener('change', () => {
      onProviderChanged();
    });
  }

  // Settings: Model Dropdown change
  if (elements.settingAiModel) {
    elements.settingAiModel.addEventListener('change', () => {
      onModelChanged();
    });
  }

  // Settings: Toggle API Key visibility
  if (elements.btnToggleApiKey && elements.settingApiKey) {
    elements.btnToggleApiKey.addEventListener('click', () => {
      const isPassword = elements.settingApiKey.type === 'password';
      elements.settingApiKey.type = isPassword ? 'text' : 'password';
      elements.btnToggleApiKey.textContent = isPassword ? 'Ẩn' : 'Hiện';
    });
  }

  // Settings: Test API Key Connection
  if (elements.btnTestApiKey) {
    elements.btnTestApiKey.addEventListener('click', async () => {
      await testApiKeyConnection();
    });
  }

  // Settings: Theme card options
  if (elements.themeOptDark) {
    elements.themeOptDark.addEventListener('click', () => applyTheme('dark'));
  }
  if (elements.themeOptLight) {
    elements.themeOptLight.addEventListener('click', () => applyTheme('light'));
  }

  // Settings: Scraper Run button
  if (elements.btnRunScraper) {
    elements.btnRunScraper.addEventListener('click', async () => {
      await saveScraperConfig(true);
    });
  }

  // Master PDF File Upload Handlers
  setupPdfUploadHandlers();
}

// -------------------------------------------------------------
// Settings Management (AI Model, Multi-Provider, API Test, Key, Theme, Profile, Scraper)
// -------------------------------------------------------------
function onProviderChanged() {
  const provider = elements.settingAiProvider ? elements.settingAiProvider.value : 'gemini';
  const info = (state.modelCatalog && state.modelCatalog[provider]) || FALLBACK_MODEL_CATALOG[provider] || FALLBACK_MODEL_CATALOG.gemini;

  // 1. Populate Model Selector
  if (elements.settingAiModel) {
    const currentVal = elements.settingAiModel.value;
    elements.settingAiModel.innerHTML = '';
    info.models.forEach((m) => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = `${m.name} ${m.tag ? `[${m.tag}]` : ''} - ${m.desc}`;
      elements.settingAiModel.appendChild(opt);
    });
    // Set to previous value if exists in this provider, else default to first
    const match = info.models.some((m) => m.id === currentVal);
    elements.settingAiModel.value = match ? currentVal : info.models[0].id;
  }

  // 2. Custom Model & Base URL inputs
  if (elements.groupCustomBaseUrl) {
    elements.groupCustomBaseUrl.style.display = provider === 'custom' ? 'block' : 'none';
  }
  onModelChanged();

  // 3. API Key label, placeholder, hint
  if (elements.lblApiKey) elements.lblApiKey.textContent = info.key_label || 'API Key';
  if (elements.hintApiKey) elements.hintApiKey.textContent = info.hint || '';
  if (elements.settingApiKey) {
    elements.settingApiKey.value = '';
    const maskedMap = {
      gemini: state.settings?.masked_api_key,
      openai: state.settings?.masked_openai_key,
      claude: state.settings?.masked_anthropic_key,
      custom: state.settings?.masked_custom_key,
    };
    const savedMask = maskedMap[provider];
    if (savedMask) {
      elements.settingApiKey.placeholder = `Khóa hiện tại: ${savedMask} (Nhập mã mới nếu muốn đổi)`;
    } else {
      elements.settingApiKey.placeholder = info.placeholder || 'Dán mã API Key...';
    }
  }

  // 4. Reset test result box
  if (elements.testApiKeyResult) {
    elements.testApiKeyResult.style.display = 'none';
    elements.testApiKeyResult.className = 'test-result-box';
    elements.testApiKeyResult.innerHTML = '';
  }
}

function onModelChanged() {
  const isCustom = elements.settingAiModel && elements.settingAiModel.value === 'custom';
  if (elements.groupCustomModel) {
    elements.groupCustomModel.style.display = isCustom ? 'block' : 'none';
  }
}

async function testApiKeyConnection() {
  const provider = elements.settingAiProvider ? elements.settingAiProvider.value : 'gemini';
  let model = elements.settingAiModel ? elements.settingAiModel.value : '';
  if (model === 'custom' && elements.settingCustomModel) {
    model = elements.settingCustomModel.value.trim() || 'default';
  }
  const apiKey = elements.settingApiKey ? elements.settingApiKey.value.trim() : '';
  const baseUrl = elements.settingCustomBaseUrl ? elements.settingCustomBaseUrl.value.trim() : '';

  if (!elements.testApiKeyResult) return;

  // Show loading state
  elements.testApiKeyResult.style.display = 'block';
  elements.testApiKeyResult.className = 'test-result-box testing';
  elements.testApiKeyResult.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span class="spinner" style="width: 14px; height: 14px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; display: inline-block; animation: spin 0.8s linear infinite;"></span>
      <span>Đang gửi gói tin kiểm tra kết nối tới <strong>${escapeHtml(provider.toUpperCase())}</strong> (mô hình: <code>${escapeHtml(model)}</code>)...</span>
    </div>
  `;
  if (elements.btnTestApiKey) {
    elements.btnTestApiKey.disabled = true;
  }

  try {
    const res = await fetch('/api/settings/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: provider,
        api_key: apiKey,
        model_name: model,
        base_url: baseUrl,
      }),
    });

    const data = await res.json();

    if (data.ok) {
      elements.testApiKeyResult.className = 'test-result-box success';
      elements.testApiKeyResult.innerHTML = `
        <div class="test-result-header">
          <span>⚡ Kết nối thành công!</span>
          <span class="test-result-badge">${data.latency_ms} ms</span>
        </div>
        <div class="test-result-detail">
          ${escapeHtml(data.message)}
          <br><small style="opacity: 0.85;">Mô hình phản hồi: <code>${escapeHtml(data.model || model)}</code></small>
        </div>
      `;
    } else {
      elements.testApiKeyResult.className = 'test-result-box error';
      elements.testApiKeyResult.innerHTML = `
        <div class="test-result-header">
          <span>❌ Kết nối thất bại ${data.status_code ? `(Mã lỗi: ${data.status_code})` : ''}</span>
          ${data.latency_ms ? `<span class="test-result-badge">${data.latency_ms} ms</span>` : ''}
        </div>
        <div class="test-result-detail">
          ${escapeHtml(data.message || 'Không thể kết nối tới nhà cung cấp AI.')}
        </div>
      `;
    }
  } catch (err) {
    elements.testApiKeyResult.className = 'test-result-box error';
    elements.testApiKeyResult.innerHTML = `
      <div class="test-result-header"><span>❌ Lỗi mạng / Không thể kết nối</span></div>
      <div class="test-result-detail">${escapeHtml(err.message)}</div>
    `;
  } finally {
    if (elements.btnTestApiKey) {
      elements.btnTestApiKey.disabled = false;
    }
  }
}

async function loadSettings() {
  try {
    // 1. Fetch Model Catalog if not yet loaded
    if (!state.modelCatalog) {
      try {
        const catRes = await fetch('/api/settings/models');
        if (catRes.ok) {
          state.modelCatalog = await catRes.json();
        }
      } catch (e) {
        console.warn('Could not fetch model catalog:', e);
      }
      if (!state.modelCatalog) state.modelCatalog = FALLBACK_MODEL_CATALOG;
    }

    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const data = await res.json();
    state.settings = data;

    // 2. Select Provider
    const activeProvider = data.ai_provider || 'gemini';
    if (elements.settingAiProvider) {
      elements.settingAiProvider.value = activeProvider;
    }
    onProviderChanged();

    // 3. Select Model
    const currentModel = data.ai_model || data.gemini_model || 'gemini-2.5-flash';
    const currentCatalog = (state.modelCatalog && state.modelCatalog[activeProvider]) || FALLBACK_MODEL_CATALOG[activeProvider];
    const knownModels = currentCatalog ? currentCatalog.models.map((m) => m.id) : [];

    if (elements.settingAiModel) {
      if (knownModels.includes(currentModel)) {
        elements.settingAiModel.value = currentModel;
        if (elements.groupCustomModel) elements.groupCustomModel.style.display = 'none';
      } else {
        elements.settingAiModel.value = 'custom';
        if (elements.groupCustomModel) {
          elements.groupCustomModel.style.display = 'block';
          if (elements.settingCustomModel) elements.settingCustomModel.value = currentModel;
        }
      }
    }

    // 4. Custom Base URL
    if (elements.settingCustomBaseUrl && data.custom_base_url) {
      elements.settingCustomBaseUrl.value = data.custom_base_url;
    }

    // 5. Update AI Status badge
    updateAiStatusIndicator(data.has_api_key, currentModel, activeProvider);

    // 6. Apply saved theme
    if (data.theme) {
      applyTheme(data.theme);
    }
  } catch (err) {
    console.warn('Could not load settings:', err);
  }
}

function updateAiStatusIndicator(hasKey, modelName, providerName) {
  const model = modelName || 'gemini-2.5-flash';
  const provider = (providerName || 'gemini').toUpperCase();
  if (elements.geminiStatusText) {
    elements.geminiStatusText.textContent = hasKey ? `${provider}: ${model}` : 'Smart Simulation Mode';
  }
  if (elements.geminiStatusPill) {
    elements.geminiStatusPill.style.background = hasKey ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)';
    elements.geminiStatusPill.style.borderColor = hasKey ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.4)';
  }
  if (elements.settingAiStatusDetail) {
    elements.settingAiStatusDetail.textContent = hasKey
      ? `Đã kích hoạt [${provider}] mô hình ${model} với API Key hợp lệ`
      : `Đang chạy Chế độ Mô phỏng Thông minh (Chưa có API Key cho ${provider})`;
  }
  if (elements.settingStatusDot) {
    elements.settingStatusDot.style.background = hasKey ? '#10b981' : '#f59e0b';
    elements.settingStatusDot.style.boxShadow = hasKey ? '0 0 10px #10b981' : '0 0 10px #f59e0b';
  }
}

function openSettingsModal(initialTab = 'ai-model') {
  loadSettings();
  loadProfileData();
  loadScraperConfig();
  switchSettingsTab(initialTab);
  if (elements.settingsModal) {
    elements.settingsModal.classList.add('open');
  }
}

function closeSettingsModal() {
  if (elements.settingsModal) {
    elements.settingsModal.classList.remove('open');
  }
}

function switchSettingsTab(targetTab) {
  elements.modalTabButtons.forEach((b) => {
    b.classList.toggle('active', b.dataset.modaltab === targetTab);
  });
  elements.modalTabPanes.forEach((pane) => {
    pane.classList.toggle('active', pane.id === `pane-${targetTab}`);
  });
}

async function saveAllSettings(closeOnSave = true) {
  // 1. Save AI & Theme Settings
  const chosenProvider = elements.settingAiProvider ? elements.settingAiProvider.value : 'gemini';
  let chosenModel = elements.settingAiModel ? elements.settingAiModel.value : 'gemini-2.5-flash';
  if (chosenModel === 'custom' && elements.settingCustomModel) {
    chosenModel = elements.settingCustomModel.value.trim() || 'gemini-2.5-flash';
  }

  const apiKeyInput = elements.settingApiKey ? elements.settingApiKey.value.trim() : '';
  const customBaseUrl = elements.settingCustomBaseUrl ? elements.settingCustomBaseUrl.value.trim() : '';
  const currentTheme = document.body.classList.contains('theme-light') ? 'light' : 'dark';

  const settingsPayload = {
    ai_provider: chosenProvider,
    ai_model: chosenModel,
    gemini_model: chosenModel,
    custom_base_url: customBaseUrl,
    theme: currentTheme,
  };
  if (apiKeyInput) {
    if (chosenProvider === 'openai') {
      settingsPayload.openai_api_key = apiKeyInput;
    } else if (chosenProvider === 'claude') {
      settingsPayload.anthropic_api_key = apiKeyInput;
    } else if (chosenProvider === 'custom') {
      settingsPayload.custom_api_key = apiKeyInput;
    } else {
      settingsPayload.gemini_api_key = apiKeyInput;
    }
  }

  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settingsPayload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể lưu cài đặt hệ thống');
    }
    const updated = await res.json();
    state.settings = updated;
    updateAiStatusIndicator(updated.has_api_key, updated.ai_model || updated.gemini_model, updated.ai_provider);
    if (elements.settingApiKey && apiKeyInput) {
      elements.settingApiKey.value = '';
      onProviderChanged();
    }

    // 2. Save Profile & Rules
    await saveProfileData(false);

    // 3. Save Scraper Config
    await saveScraperConfig(false, false);

    if (closeOnSave) {
      closeSettingsModal();
      alert('Đã lưu toàn bộ cài đặt hệ thống, mô hình AI, quy chế và cấu hình thành công!');
    }
    await loadStats();
  } catch (err) {
    alert('Lỗi lưu cài đặt: ' + err.message);
  }
}

// -------------------------------------------------------------
// Tabs & Overleaf LaTeX Studio Logic
// -------------------------------------------------------------
function switchTab(tabName, persist = true) {
  state.currentTab = tabName;
  if (persist) {
    localStorage.setItem('findmyboss_current_tab', tabName);
  }
  elements.tabButtons.forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === tabName);
  });
  elements.tabPanes.forEach((p) => {
    p.classList.toggle('active', p.id === `tab-${tabName}`);
  });
}

function updateLatexCharCount() {
  const text = elements.latexSourceText ? elements.latexSourceText.value : '';
  const lines = text ? text.split('\n').length : 0;
  const chars = text.length;
  if (elements.overleafCharCount) {
    elements.overleafCharCount.textContent = `${lines} dòng • ${chars.toLocaleString()} ký tự`;
  }
}

// -------------------------------------------------------------
// Master PDF File Upload Handlers
// -------------------------------------------------------------
function setupPdfUploadHandlers() {
  const dropzone = elements.dropzoneCv;
  const fileInput = elements.fileMasterCv;
  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());
  if (elements.btnChangePdf) {
    elements.btnChangePdf.addEventListener('click', () => fileInput.click());
  }

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].name.toLowerCase().endsWith('.pdf')) {
      uploadMasterPdf(files[0]);
    } else {
      alert('Vui lòng chọn một file có định dạng .pdf!');
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      uploadMasterPdf(fileInput.files[0]);
    }
  });
}

async function uploadMasterPdf(file) {
  const formData = new FormData();
  formData.append('file', file);

  const dropTextEl = elements.dropzoneCv.querySelector('.dropzone-text');
  const originalDropText = dropTextEl ? dropTextEl.textContent : '';
  if (dropTextEl) dropTextEl.textContent = 'Đang trích xuất dữ liệu từ PDF...';

  try {
    const res = await fetch('/api/profile/upload-pdf', {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload thất bại');
    }

    const data = await res.json();
    displayUploadedPdfInfo(data.filename, data.pages, data.word_count, data.text_preview);
    await loadProfileData();
    alert(`Tải lên thành công: ${data.filename} (${data.pages} trang, ${data.word_count} từ)!`);
  } catch (err) {
    alert(`Lỗi upload PDF: ${err.message}`);
  } finally {
    if (dropTextEl) dropTextEl.textContent = originalDropText;
  }
}

function displayUploadedPdfInfo(filename, pages, wordCount, textPreview) {
  if (!elements.masterCvInfoBox) return;
  elements.masterCvInfoBox.style.display = 'block';
  if (elements.badgeFileName) elements.badgeFileName.textContent = filename || 'master_cv.pdf';
  if (elements.badgeFileMeta) elements.badgeFileMeta.textContent = `${pages || 1} trang • ${wordCount || 0} từ đã trích xuất`;
  if (elements.extractedTextPreview) elements.extractedTextPreview.textContent = textPreview || '(Không có nội dung văn bản)';
}

// -------------------------------------------------------------
// Data Loading & API Calls
// -------------------------------------------------------------
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const stats = await res.json();
    if (elements.statTotalJobs) elements.statTotalJobs.textContent = stats.total_jobs || 0;
    if (elements.statTotalCvs) elements.statTotalCvs.textContent = stats.total_cvs || 0;
    updateAiStatusIndicator(stats.has_gemini_key, stats.gemini_model);
  } catch (err) {
    console.warn('Could not load stats:', err);
  }
}

async function loadJobs() {
  try {
    let url = `/api/jobs?limit=50`;
    if (state.searchQuery) {
      url += `&q=${encodeURIComponent(state.searchQuery)}`;
    }
    if (state.activeFilter === 'has_cv') {
      url += `&has_cv=true`;
    } else if (state.activeFilter === 'no_cv') {
      url += `&has_cv=false`;
    } else if (state.activeFilter && state.activeFilter.startsWith('status:')) {
      const statusVal = state.activeFilter.replace('status:', '');
      url += `&status=${encodeURIComponent(statusVal)}`;
    } else if (['python', 'react', 'intern', 'fresher'].includes(state.activeFilter)) {
      url += `&skill=${encodeURIComponent(state.activeFilter)}`;
    }

    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch jobs');
    const data = await res.json();
    state.jobs = data.jobs || [];

    renderJobsList(state.jobs);

    // State persistence: restore selected job if still present in results
    const matchingJob = state.jobs.find((j) => j.id === state.selectedJobId);
    if (matchingJob) {
      selectJob(matchingJob.id, false);
    } else if (state.jobs.length > 0) {
      selectJob(state.jobs[0].id, false);
    } else {
      renderEmptyState();
    }
  } catch (err) {
    console.error('Error fetching jobs:', err);
  }
}

// Helper for formatting timestamps
function formatScrapedDate(dateStr) {
  if (!dateStr || dateStr === 'N/A') return 'Chưa rõ';
  try {
    let d = new Date(dateStr);
    if (isNaN(d.getTime()) && typeof dateStr === 'string') {
      d = new Date(dateStr.replace(' ', 'T') + 'Z');
    }
    if (isNaN(d.getTime())) return String(dateStr);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} ${hours}:${minutes}`;
  } catch (e) {
    return String(dateStr);
  }
}

function getRelativeTime(dateStr) {
  if (!dateStr || dateStr === 'N/A') return 'Chưa rõ';
  try {
    let d = new Date(dateStr);
    if (isNaN(d.getTime()) && typeof dateStr === 'string') {
      d = new Date(dateStr.replace(' ', 'T') + 'Z');
    }
    if (isNaN(d.getTime())) return String(dateStr);

    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    if (diffMs < 0) return 'Vừa xong';
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return 'Vừa xong';
    if (diffMin < 60) return `${diffMin} phút trước`;
    if (diffHour < 24) return `${diffHour} giờ trước`;
    if (diffDay === 1) return 'Hôm qua';
    if (diffDay < 7) return `${diffDay} ngày trước`;

    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    return `${day}/${month}/${year}`;
  } catch (e) {
    return String(dateStr);
  }
}

function renderJobsList(jobs) {
  elements.jobsList.innerHTML = '';
  if (jobs.length === 0) {
    elements.jobsList.innerHTML = `
      <div class="empty-state">
        <span>Không tìm thấy công việc nào phù hợp.</span>
      </div>
    `;
    return;
  }

  jobs.forEach((job) => {
    const card = document.createElement('div');
    card.className = `job-card ${job.id === state.selectedJobId ? 'active' : ''}`;
    card.id = `job-card-${job.id}`;

    const hasCv = !!job.cv_id;
    const skillsHtml = (job.skills || [])
      .slice(0, 4)
      .map((s) => `<span class="skill-tag">${escapeHtml(s)}</span>`)
      .join('');

    const statusVal = job.status || 'saved';
    const statusLabel = STATUS_LABELS[statusVal] || 'Chưa nộp';

    const rawDate = job.time || job.created_at;
    const exactDate = formatScrapedDate(rawDate);
    const relDate = getRelativeTime(rawDate);

    card.innerHTML = `
      <div class="job-card-header">
        <div class="job-card-title">${escapeHtml(job.title)}</div>
        <span class="status-chip status-${escapeHtml(statusVal)}">${escapeHtml(statusLabel)}</span>
      </div>
      <div class="job-card-body">
        <div class="job-card-company">${escapeHtml(job.company)}</div>
        <div class="job-meta-row">
          <span class="meta-chip salary">${escapeHtml(job.salary || 'Deal')}</span>
          <span class="meta-chip">${escapeHtml(job.address || 'Hồ Chí Minh')}</span>
          ${rawDate ? `<span class="meta-chip meta-date" title="Thời gian cào: ${escapeHtml(exactDate)}">🕒 Cào: ${escapeHtml(relDate)}</span>` : ''}
          ${hasCv ? `<span class="meta-chip has-cv">CV Ready (${job.match_score || 80}%)</span>` : ''}
        </div>
        ${skillsHtml ? `<div class="skills-row">${skillsHtml}</div>` : ''}
      </div>
    `;

    card.addEventListener('click', () => selectJob(job.id));
    elements.jobsList.appendChild(card);
  });
}

function renderEmptyState() {
  elements.emptyDetail.style.display = 'flex';
  elements.detailPane.style.display = 'none';
}

async function selectJob(jobId, shouldScroll = true) {
  state.selectedJobId = jobId;
  localStorage.setItem('findmyboss_selected_job_id', jobId);

  // Update card active class
  document.querySelectorAll('.job-card').forEach((c) => c.classList.remove('active'));
  const activeCard = document.getElementById(`job-card-${jobId}`);
  if (activeCard) {
    activeCard.classList.add('active');
    if (shouldScroll) {
      activeCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // Fetch full details
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) throw new Error('Job not found');
    const job = await res.json();

    elements.emptyDetail.style.display = 'none';
    elements.detailPane.style.display = 'flex';

    // Populate Header
    elements.detailJobTitle.textContent = job.title;
    elements.detailJobCompany.textContent = job.company;
    elements.detailJobSalary.textContent = job.salary || 'Thoả thuận';
    elements.detailJobAddress.textContent = job.address || 'Hồ Chí Minh';
    elements.detailJobLink.href = job.link || '#';

    // Scraped and posted date badges
    const rawDate = job.time || job.created_at;
    const exactDate = formatScrapedDate(rawDate);
    const detailScrapedEl = document.getElementById('detailScrapedAtText');
    if (detailScrapedEl) {
      detailScrapedEl.textContent = exactDate || 'Chưa rõ';
    }
    const detailPostedEl = document.getElementById('detailPostedDateText');
    if (detailPostedEl) {
      detailPostedEl.textContent = job.posted_date || 'N/A';
    }

    // Populate Status Selector
    if (elements.detailJobStatusSelect) {
      elements.detailJobStatusSelect.value = job.status || 'saved';
    }

    // Populate Tab 1: JD (Toàn bộ nội dung cào được gom vào Mô tả công việc)
    let fullDescription = [];
    if (job.description && job.description.trim()) {
      fullDescription.push(job.description.trim());
    }
    if (job.requirements && job.requirements.trim()) {
      const reqSnippet = job.requirements.trim().slice(0, 50);
      if (!job.description || !job.description.includes(reqSnippet)) {
        fullDescription.push('### YÊU CẦU ỨNG VIÊN:\n' + job.requirements.trim());
      }
    }
    if (job.benefits && job.benefits.trim()) {
      const benSnippet = job.benefits.trim().slice(0, 50);
      if (!job.description || !job.description.includes(benSnippet)) {
        fullDescription.push('### QUYỀN LỢI ĐƯỢC HƯỞNG:\n' + job.benefits.trim());
      }
    }

    const finalDesc = fullDescription.length > 0
      ? fullDescription.join('\n\n')
      : (job.full_jd_raw || 'Chưa có thông tin mô tả chi tiết công việc.');

    if (elements.jdDescription) {
      elements.jdDescription.textContent = finalDesc;
    }
    if (elements.jdRequirements) {
      elements.jdRequirements.textContent = job.requirements || '';
    }
    if (elements.jdBenefits) {
      elements.jdBenefits.textContent = job.benefits || '';
    }
    if (elements.jdFullRaw) {
      elements.jdFullRaw.textContent = job.full_jd_raw || job.description || 'N/A';
    }

    // Populate Tab 2 & 3: CV Info & Overleaf Studio
    if (job.cv_id) {
      elements.btnTailorText.textContent = 'Tạo lại CV mới';
      elements.aiMatchScore.textContent = `${job.match_score || 85}%`;
      elements.aiMatchAnalysis.textContent =
        job.tailored_summary || 'Hồ sơ đã được tối ưu hóa chuẩn ATS cho vị trí này.';

      const missing = job.missing_skills || [];
      elements.missingKeywordsList.innerHTML = missing.length
        ? missing.map((k) => `<span class="kw-chip">${escapeHtml(k)}</span>`).join('')
        : '<span style="color: var(--text-dim); font-size: 12px;">Đã phủ đủ các kỹ năng cốt lõi của JD!</span>';

      const bullets = job.tailored_bullets || [];
      elements.tailoredBulletsList.innerHTML = bullets
        .map((b) => `<div class="bullet-item">• ${escapeHtml(b)}</div>`)
        .join('');

      // PDF preview
      const pdfUrl = `/api/jobs/${jobId}/pdf?t=${Date.now()}`;
      elements.pdfFrame.src = pdfUrl;
      elements.btnDownloadPdf.href = `/api/jobs/${jobId}/pdf?download=true`;
      elements.btnOpenPdfNewTab.href = pdfUrl;

      // Check for saved local draft first, fallback to DB code
      const savedDraft = localStorage.getItem('findmyboss_draft_latex_' + jobId);
      elements.latexSourceText.value = savedDraft || job.latex_code || '';
      updateLatexCharCount();

      if (elements.overleafCompileStatus) {
        elements.overleafCompileStatus.textContent = 'Bản dịch hiện tại sẵn sàng';
        elements.overleafCompileStatus.style.color = 'var(--accent-emerald-light)';
      }
    } else {
      elements.btnTailorText.textContent = 'Tạo CV với Gemini';
      elements.aiMatchScore.textContent = '--%';
      elements.aiMatchAnalysis.textContent = 'Nhấn nút "Tạo CV với Gemini" bên trên để phân tích JD và sinh CV hoàn chỉnh.';
      elements.missingKeywordsList.innerHTML = '<span style="color: var(--text-dim); font-size: 12px;">Chưa phân tích</span>';
      elements.tailoredSummaryText.textContent = 'Chưa tạo tóm tắt chuyên môn.';
      elements.tailoredBulletsList.innerHTML = '<span style="color: var(--text-dim); font-size: 12px;">Chưa tạo gạch đầu dòng kinh nghiệm.</span>';
      elements.pdfFrame.src = 'about:blank';
      elements.latexSourceText.value = '';
      updateLatexCharCount();
      if (elements.overleafCompileStatus) {
        elements.overleafCompileStatus.textContent = 'Chưa có mã nguồn LaTeX';
        elements.overleafCompileStatus.style.color = '#8b949e';
      }
    }
  } catch (err) {
    console.error('Failed to load job details:', err);
  }
}

// -------------------------------------------------------------
// CV Tailoring & PDF Generation
// -------------------------------------------------------------
async function triggerTailorCv(jobId) {
  setTailoringLoading(true);

  try {
    const template = elements.templateSelector ? elements.templateSelector.value : 'classic';
    const res = await fetch(`/api/jobs/${jobId}/tailor?template=${encodeURIComponent(template)}`, {
      method: 'POST',
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Tailoring failed');
    }

    const data = await res.json();

    if (data.used_master_cv && elements.aiSyncStatusText) {
      elements.aiSyncStatusText.innerHTML = `<strong>Quy chế AI:</strong> Đã dùng Master CV (${data.master_cv_words || 0} từ) & Tuân thủ ${data.applied_rules?.ats_rules_len || 0} quy tắc ATS, ${data.applied_rules?.cv_rules_len || 0} quy tắc CV!`;
      elements.aiSyncBanner.style.borderColor = 'var(--accent-emerald)';
    }

    localStorage.removeItem('findmyboss_draft_latex_' + jobId);
    await loadStats();
    await selectJob(jobId);
    switchTab('pdf');
  } catch (err) {
    alert(`Lỗi khi tạo CV: ${err.message}`);
  } finally {
    setTailoringLoading(false);
  }
}

async function triggerRecompileLatex(jobId) {
  const latexCode = elements.latexSourceText.value;
  if (!latexCode.trim()) return;

  elements.btnRecompileLatex.disabled = true;
  if (elements.btnRecompileText) elements.btnRecompileText.textContent = 'Compiling...';
  if (elements.overleafCompileStatus) {
    elements.overleafCompileStatus.textContent = 'Đang biên dịch với Tectonic Engine...';
    elements.overleafCompileStatus.style.color = 'var(--accent-amber)';
  }

  try {
    const res = await fetch(`/api/jobs/${jobId}/recompile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latex_code: latexCode }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Recompile failed');
    }

    // Clear local draft since DB is now synchronized
    localStorage.removeItem('findmyboss_draft_latex_' + jobId);

    elements.pdfFrame.src = `/api/jobs/${jobId}/pdf?t=${Date.now()}`;
    if (elements.overleafCompileStatus) {
      elements.overleafCompileStatus.textContent = 'Biên dịch thành công!';
      elements.overleafCompileStatus.style.color = 'var(--accent-emerald-light)';
    }
  } catch (err) {
    if (elements.overleafCompileStatus) {
      elements.overleafCompileStatus.textContent = 'Lỗi biên dịch LaTeX';
      elements.overleafCompileStatus.style.color = 'var(--accent-rose)';
    }
    alert(`Lỗi biên dịch LaTeX: ${err.message}`);
  } finally {
    elements.btnRecompileLatex.disabled = false;
    if (elements.btnRecompileText) elements.btnRecompileText.textContent = 'Recompile';
  }
}

function setTailoringLoading(isLoading) {
  elements.btnTailorCv.disabled = isLoading;
  if (isLoading) {
    elements.btnTailorSpinner.style.display = 'inline-block';
    elements.btnTailorText.textContent = 'Đang phân tích & render PDF...';
  } else {
    elements.btnTailorSpinner.style.display = 'none';
    elements.btnTailorText.textContent = 'Tạo CV với Gemini';
  }
}

// -------------------------------------------------------------
// Candidate Profile & Rules
// -------------------------------------------------------------
async function loadProfileData() {
  try {
    const res = await fetch('/api/profile');
    if (!res.ok) return;
    state.profile = await res.json();

    if (elements.inputAtsRules) elements.inputAtsRules.value = state.profile.ats_rules || '';
    if (elements.inputCvRules) elements.inputCvRules.value = state.profile.cv_rules || '';

    if (elements.inputProfileName) elements.inputProfileName.value = state.profile.name || '';
    if (elements.inputProfileTitle) elements.inputProfileTitle.value = state.profile.title || '';
    if (elements.inputProfileEmail) elements.inputProfileEmail.value = state.profile.email || '';
    if (elements.inputProfilePhone) elements.inputProfilePhone.value = state.profile.phone || '';
    if (elements.inputProfileLocation) elements.inputProfileLocation.value = state.profile.location || '';
    if (elements.inputProfileSummary) elements.inputProfileSummary.value = state.profile.summary || '';

    if (state.profile.master_cv_filename) {
      displayUploadedPdfInfo(
        state.profile.master_cv_filename,
        state.profile.master_cv_pages,
        state.profile.master_cv_words,
        state.profile.master_cv_text
      );
    }
  } catch (err) {
    console.warn('Could not load profile:', err);
  }
}

async function saveProfileData(showAlert = true) {
  if (!state.profile) state.profile = {};

  if (elements.inputAtsRules) state.profile.ats_rules = elements.inputAtsRules.value.trim();
  if (elements.inputCvRules) state.profile.cv_rules = elements.inputCvRules.value.trim();

  if (elements.inputProfileName) state.profile.name = elements.inputProfileName.value.trim();
  if (elements.inputProfileTitle) state.profile.title = elements.inputProfileTitle.value.trim();
  if (elements.inputProfileEmail) state.profile.email = elements.inputProfileEmail.value.trim();
  if (elements.inputProfilePhone) state.profile.phone = elements.inputProfilePhone.value.trim();
  if (elements.inputProfileLocation) state.profile.location = elements.inputProfileLocation.value.trim();
  if (elements.inputProfileSummary) state.profile.summary = elements.inputProfileSummary.value.trim();

  try {
    const res = await fetch('/api/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.profile),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Lưu hồ sơ thất bại');
    }
    if (showAlert) {
      alert('Đã lưu cấu hình hồ sơ và bộ quy tắc thành công!');
    }
  } catch (err) {
    if (showAlert) alert('Lỗi lưu hồ sơ: ' + err.message);
  }
}

// -------------------------------------------------------------
// Scraper Configuration
// -------------------------------------------------------------
async function loadScraperConfig() {
  try {
    const res = await fetch('/api/scraper/config');
    if (!res.ok) return;
    const config = await res.json();

    if (config.portals && elements.portalCheckboxes) {
      for (const [key, chk] of Object.entries(elements.portalCheckboxes)) {
        if (chk && config.portals[key] !== undefined) {
          chk.checked = !!config.portals[key];
        }
      }
    }

    if (elements.scraperKeywords && config.keywords) {
      elements.scraperKeywords.value = config.keywords.join(', ');
    }

    const levels = config.levels || [];
    document.querySelectorAll('.level-chk').forEach((chk) => {
      chk.checked = levels.includes(chk.value);
    });

    const locations = config.locations || [];
    document.querySelectorAll('.city-chk').forEach((chk) => {
      chk.checked = locations.includes(chk.value);
    });

    if (elements.scraperBlacklist && config.blacklisted_keywords) {
      elements.scraperBlacklist.value = config.blacklisted_keywords.join(', ');
    }

    if (elements.scraperMaxPages && config.max_pages_per_portal) {
      elements.scraperMaxPages.value = config.max_pages_per_portal;
    }
    if (elements.scraperDelay && config.delay_seconds) {
      elements.scraperDelay.value = config.delay_seconds;
    }
  } catch (err) {
    console.warn('Could not load scraper config:', err);
  }
}

async function saveScraperConfig(triggerCrawl = false, showAlert = true) {
  const portals = {};
  if (elements.portalCheckboxes) {
    for (const [key, chk] of Object.entries(elements.portalCheckboxes)) {
      if (chk) portals[key] = chk.checked;
    }
  }

  const keywords = (elements.scraperKeywords ? elements.scraperKeywords.value : '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  const levels = Array.from(document.querySelectorAll('.level-chk:checked')).map((c) => c.value);
  const locations = Array.from(document.querySelectorAll('.city-chk:checked')).map((c) => c.value);

  const blacklist = (elements.scraperBlacklist ? elements.scraperBlacklist.value : '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  const payload = {
    portals,
    keywords,
    levels,
    locations,
    blacklisted_keywords: blacklist,
    max_pages_per_portal: parseInt(elements.scraperMaxPages ? elements.scraperMaxPages.value : 3, 10) || 3,
    delay_seconds: parseFloat(elements.scraperDelay ? elements.scraperDelay.value : 2.0) || 2.0,
  };

  try {
    const res = await fetch('/api/scraper/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Không thể lưu cấu hình scraper');
    }

    if (triggerCrawl) {
      closeSettingsModal();
      try {
        const runRes = await fetch('/api/scraper/run', { method: 'POST' });
        const runData = await runRes.json();
        alert(runData.message || 'Đã lưu cấu hình và kích hoạt tiến trình cào dữ liệu từ các cổng!');
      } catch (e) {
        alert('Đã lưu cấu hình nhưng gặp sự cố khi kích hoạt cào: ' + e.message);
      }
      await loadJobs();
      await loadStats();
    } else if (showAlert) {
      alert('Đã lưu cấu hình cào tuyển dụng thành công!');
    }
  } catch (err) {
    if (showAlert) alert('Lỗi lưu cấu hình: ' + err.message);
  }
}

// -------------------------------------------------------------
// Quick Scraper Manager
// -------------------------------------------------------------
let scraperPollInterval = null;
let scraperStartTime = null;
let scraperTimerInterval = null;

function openScrapeModal() {
  if (elements.scrapeModal) {
    elements.scrapeModal.style.display = 'flex';
    checkScraperStatus();
  }
}

function closeScrapeModal() {
  if (elements.scrapeModal) {
    elements.scrapeModal.style.display = 'none';
  }
}

function updateScrapeTimer() {
  if (!scraperStartTime || !elements.scrapeModalTimer) return;
  const elapsed = Math.floor((Date.now() - scraperStartTime) / 1000);
  const min = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const sec = String(elapsed % 60).padStart(2, '0');
  elements.scrapeModalTimer.textContent = `${min}:${sec}`;
}

async function checkScraperStatus() {
  try {
    const res = await fetch('/api/scraper/status');
    if (!res.ok) return;
    const data = await res.json();
    updateScraperUI(data);
  } catch (err) {
    console.warn('Scraper status check failed:', err);
  }
}

function updateScraperUI(data) {
  const isRunning = !!data.is_running;

  // Header Status Pill
  if (elements.scraperStatusPill) {
    if (isRunning) {
      elements.scraperStatusPill.style.display = 'inline-flex';
      if (elements.scraperStatusText) {
        elements.scraperStatusText.textContent = data.current_stage || 'Đang cào dữ liệu...';
      }
    } else {
      elements.scraperStatusPill.style.display = 'none';
    }
  }

  // Modal Status Box
  if (elements.scrapeModalStatusBox) {
    if (isRunning) {
      elements.scrapeModalStatusBox.style.display = 'block';
      if (elements.scrapeModalStatusTitle) {
        elements.scrapeModalStatusTitle.textContent = data.current_portal
          ? `Đang cào ${data.current_portal.toUpperCase()}...`
          : 'Đang cào dữ liệu từ các cổng...';
      }
      if (elements.scrapeModalStatusDetail) {
        elements.scrapeModalStatusDetail.textContent = data.current_stage || 'Đang chạy Playwright headless worker...';
      }
      if (elements.btnStartScrape) {
        elements.btnStartScrape.disabled = true;
      }
      if (elements.btnStartScrapeSpinner) {
        elements.btnStartScrapeSpinner.style.display = 'inline-block';
      }
      if (elements.btnStartScrapeText) {
        elements.btnStartScrapeText.textContent = 'Đang cào dữ liệu...';
      }

      if (!scraperPollInterval) {
        if (!scraperStartTime) scraperStartTime = Date.now();
        scraperTimerInterval = setInterval(updateScrapeTimer, 1000);
        scraperPollInterval = setInterval(checkScraperStatus, 2000);
      }
    } else {
      // Not running
      if (scraperPollInterval) {
        clearInterval(scraperPollInterval);
        scraperPollInterval = null;
      }
      if (scraperTimerInterval) {
        clearInterval(scraperTimerInterval);
        scraperTimerInterval = null;
      }
      scraperStartTime = null;

      if (elements.btnStartScrape) {
        elements.btnStartScrape.disabled = false;
      }
      if (elements.btnStartScrapeSpinner) {
        elements.btnStartScrapeSpinner.style.display = 'none';
      }
      if (elements.btnStartScrapeText) {
        elements.btnStartScrapeText.textContent = '🚀 Bắt Đầu Cào Ngay';
      }

      if (data.last_run && elements.scrapeModalStatusBox.style.display === 'block') {
        if (elements.scrapeModalStatusTitle) {
          elements.scrapeModalStatusTitle.textContent = '✅ Đã cào dữ liệu thành công!';
        }
        if (elements.scrapeModalStatusDetail) {
          elements.scrapeModalStatusDetail.textContent = `Lần cào gần nhất: ${data.last_run} (thu được ${data.total_scraped_last_run || 0} việc, trong ${data.last_duration_seconds || 0}s). Tổng việc trong DB: ${data.total_jobs_in_db || 0}`;
        }
        // Auto refresh jobs & stats
        loadJobs();
        loadStats();
      }
    }
  }
}

async function startQuickScrape() {
  const portalCheckboxes = document.querySelectorAll('.portal-checkbox-grid input[type="checkbox"]:checked');
  const selectedPortals = Array.from(portalCheckboxes).map((cb) => cb.value);

  if (selectedPortals.length === 0) {
    alert('Vui lòng chọn ít nhất một cổng tuyển dụng để cào.');
    return;
  }

  const todayOnly = elements.quickScrapeToday ? elements.quickScrapeToday.value === 'true' : false;
  const maxPages = elements.quickScrapeMaxPages ? parseInt(elements.quickScrapeMaxPages.value, 10) || 2 : 2;

  const payload = {
    portals: selectedPortals,
    today_only: todayOnly,
    max_pages: maxPages,
  };

  if (elements.btnStartScrape) elements.btnStartScrape.disabled = true;
  if (elements.btnStartScrapeSpinner) elements.btnStartScrapeSpinner.style.display = 'inline-block';
  if (elements.btnStartScrapeText) elements.btnStartScrapeText.textContent = 'Đang khởi động...';
  if (elements.scrapeModalStatusBox) elements.scrapeModalStatusBox.style.display = 'block';
  if (elements.scrapeModalStatusTitle) elements.scrapeModalStatusTitle.textContent = 'Đang kết nối worker scraper...';
  if (elements.scrapeModalStatusDetail) elements.scrapeModalStatusDetail.textContent = 'Khởi tạo container Chromium Playwright...';

  try {
    const res = await fetch('/api/scraper/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || data.success === false) {
      throw new Error(data.message || 'Không thể kích hoạt scraper worker');
    }

    scraperStartTime = Date.now();
    scraperTimerInterval = setInterval(updateScrapeTimer, 1000);
    scraperPollInterval = setInterval(checkScraperStatus, 2000);
    checkScraperStatus();
  } catch (err) {
    alert('Lỗi khởi chạy cào dữ liệu: ' + err.message);
    if (elements.btnStartScrape) elements.btnStartScrape.disabled = false;
    if (elements.btnStartScrapeSpinner) elements.btnStartScrapeSpinner.style.display = 'none';
    if (elements.btnStartScrapeText) elements.btnStartScrapeText.textContent = '🚀 Bắt Đầu Cào Ngay';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Start application
document.addEventListener('DOMContentLoaded', initApp);
