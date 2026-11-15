/**
 * Kinetic ResumeTailor - Frontend Logic Controller
 * Cleanly decoupled from style sheets and design tokens.
 */

const state = {
  originalMarkdown: '',
  originalGeneratedMarkdown: '',
  tailoredMarkdown: '',
  coverLetterMarkdown: '',
  outreach: {
    linkedin_message: '',
    email_subject: '',
    email_body: ''
  },
  activeTab: 'tailored',
  analysis: null,
  diffs: [],
  slots: []
};

const SAMPLE_JDS = {
  facilities: `Commercial Facilities Operations Coordinator & Building Automation Specialist

Company: Apex Commercial Property Management
Location: Vancouver / Surrey, BC

About the Role:
We are seeking a Commercial Facilities Operations Coordinator to supervise building control systems (BAS/BMS), lead preventative maintenance scheduling, and ensure building compliance and life safety across commercial real estate portfolios.

Responsibilities:
- Conduct daily building rounds and mechanical room inspections (pumps, boilers, chillers, HVAC, air handlers).
- Manage incoming tenant service requests, dispatch trade contractors, and track SLAs via computerized work order systems (Angus, WPM Plus).
- Oversee life safety, fire alarm panels, emergency response protocols, and OH&S committee compliance.
- Track preventative maintenance logs and equipment diagnostics using automated tools, Python, or Power BI.
- Coordinate trade contractors across HVAC, electrical, plumbing, and elevating devices.

Requirements:
- 3+ years experience in commercial building operations, facilities coordination, or property security supervision.
- Knowledge of BMS/BAS control systems, preventative maintenance procedures, and Job Hazard Assessments (JHA).
- Experience with work order management systems (Angus, WPM, or equivalent).
- Valid BC Driver's License with reliable personal vehicle. OFA Level 1 certification preferred.`,

  cloud: `Senior Cloud & Distributed Systems Software Engineer

Company: Distributed Cloud Networks
Location: Remote

About the Role:
We are seeking a Senior Systems Engineer to architect resilient distributed backend systems, monitor high-throughput message streaming pipelines, and optimize containerized microservices on AWS and Kubernetes.

Responsibilities:
- Build and optimize low-latency backend services with Python, Go, and PostgreSQL.
- Automate cluster deployment and auto-scaling policies on Kubernetes with Prometheus observability.
- Architect high-throughput Kafka and Redis streaming solutions with zero data loss.
- Maintain rigorous CI/CD pipelines and infrastructure-as-code automation.

Requirements:
- 4+ years software development experience with Python, Go, Docker, and Kubernetes.
- Deep familiarity with Linux systems, network protocols, and relational database optimization.
- Strong track record designing fault-tolerant cloud platforms.`
};
SAMPLE_JDS.backend = SAMPLE_JDS.facilities;
SAMPLE_JDS.ai = SAMPLE_JDS.cloud;

// DOM Elements container
const elements = {};

function initElements() {
  elements.statusBadge = document.getElementById('statusBadge');
  elements.providerBadge = document.getElementById('providerBadge');
  elements.jdInput = document.getElementById('jobDescriptionInput');
  elements.additionalNotes = document.getElementById('additionalNotesInput');
  elements.jdWordCount = document.getElementById('jdWordCount');
  elements.generateBtn = document.getElementById('generateResumeBtn');
  elements.generateCoverLetterBtn = document.getElementById('generateCoverLetterBtn');
  elements.generateOutreachBtn = document.getElementById('generateOutreachBtn');
  elements.clearJdBtn = document.getElementById('clearJdBtn');
  elements.loadBackendBtn = document.getElementById('loadSampleFacilitiesBtn') || document.getElementById('loadSampleBackendBtn');
  elements.loadAIBtn = document.getElementById('loadSampleCloudBtn') || document.getElementById('loadSampleAIBtn');

  // Tabs
  elements.tabTailored = document.getElementById('tabTailored');
  elements.tabCoverLetter = document.getElementById('tabCoverLetter');
  elements.tabOutreach = document.getElementById('tabOutreach');
  elements.tabOriginal = document.getElementById('tabOriginal');
  elements.tabDiff = document.getElementById('tabDiff');
  elements.tabEditor = document.getElementById('tabEditor');

  // Panels
  elements.panelTailored = document.getElementById('panelTailored');
  elements.panelCoverLetter = document.getElementById('panelCoverLetter');
  elements.panelOutreach = document.getElementById('panelOutreach');
  elements.panelOriginal = document.getElementById('panelOriginal');
  elements.panelDiff = document.getElementById('panelDiff');
  elements.panelEditor = document.getElementById('panelEditor');

  // Outreach Elements
  elements.linkedinMessageText = document.getElementById('linkedinMessageText');
  elements.emailSubjectText = document.getElementById('emailSubjectText');
  elements.emailBodyText = document.getElementById('emailBodyText');
  elements.linkedinStats = document.getElementById('linkedinStats');
  elements.emailStats = document.getElementById('emailStats');
  elements.copyLinkedInBtn = document.getElementById('copyLinkedInBtn');
  elements.copyEmailSubjectBtn = document.getElementById('copyEmailSubjectBtn');
  elements.copyEmailBtn = document.getElementById('copyEmailBtn');

  // Targets
  elements.tailoredRender = document.getElementById('tailoredResumeRender');
  elements.coverLetterRender = document.getElementById('coverLetterRender');
  elements.originalRender = document.getElementById('originalResumeRender');
  elements.diffContainer = document.getElementById('diffContainer');
  elements.markdownEditor = document.getElementById('markdownEditorInput');
  elements.resetEditorBtn = document.getElementById('resetEditorBtn');

  // Processing & Insights
  elements.processingIndicator = document.getElementById('processingIndicator');
  elements.processingStepText = document.getElementById('processingStepText');
  elements.toolbarAtsHud = document.getElementById('toolbarAtsHud');
  elements.toolbarAtsScoreValue = document.getElementById('toolbarAtsScoreValue');
  elements.toolbarAtsBreakdown = document.getElementById('toolbarAtsBreakdown');
  elements.toolbarQaBadge = document.getElementById('toolbarQaBadge');
  elements.analysisCard = document.getElementById('analysisCard');
  elements.atsScoreBadge = document.getElementById('atsScoreBadge');
  elements.targetRoleBadge = document.getElementById('targetRoleBadge');
  elements.keyTechBadges = document.getElementById('keyTechBadges');
  elements.reqMatrixBadges = document.getElementById('reqMatrixBadges');
  elements.slot1Desc = document.getElementById('slot1Desc');
  elements.slot2Desc = document.getElementById('slot2Desc');
  elements.qaReportBadge = document.getElementById('qaReportBadge');

  // Exports
  elements.downloadMarkdownBtn = document.getElementById('downloadMarkdownBtn');
  elements.downloadPdfBtn = document.getElementById('downloadPdfBtn');
}

// Initialize Application
async function init() {
  initElements();
  setupEventListeners();
  updateWordCount();
  await checkHealth();
  await loadMasterResume();
}

function setupEventListeners() {
  if (elements.jdInput) {
    elements.jdInput.addEventListener('input', updateWordCount);
  }

  if (elements.clearJdBtn) {
    elements.clearJdBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (elements.jdInput) elements.jdInput.value = '';
      if (elements.additionalNotes) elements.additionalNotes.value = '';
      updateWordCount();
    });
  }

  if (elements.loadBackendBtn) {
    elements.loadBackendBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (elements.jdInput) {
        elements.jdInput.value = SAMPLE_JDS.backend;
        updateWordCount();
      }
    });
  }

  if (elements.loadAIBtn) {
    elements.loadAIBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (elements.jdInput) {
        elements.jdInput.value = SAMPLE_JDS.ai;
        updateWordCount();
      }
    });
  }

  if (elements.generateBtn) {
    elements.generateBtn.addEventListener('click', (e) => {
      e.preventDefault();
      handleGenerateResume();
    });
  }

  if (elements.generateCoverLetterBtn) {
    elements.generateCoverLetterBtn.addEventListener('click', (e) => {
      e.preventDefault();
      handleGenerateCoverLetter();
    });
  }

  if (elements.generateOutreachBtn) {
    elements.generateOutreachBtn.addEventListener('click', (e) => {
      e.preventDefault();
      handleGenerateOutreach();
    });
  }

  // Tab switching
  if (elements.tabTailored) elements.tabTailored.addEventListener('click', () => switchTab('tailored'));
  if (elements.tabCoverLetter) elements.tabCoverLetter.addEventListener('click', () => switchTab('coverletter'));
  if (elements.tabOutreach) elements.tabOutreach.addEventListener('click', () => switchTab('outreach'));
  if (elements.tabOriginal) elements.tabOriginal.addEventListener('click', () => switchTab('original'));
  if (elements.tabDiff) elements.tabDiff.addEventListener('click', () => switchTab('diff'));
  if (elements.tabEditor) elements.tabEditor.addEventListener('click', () => switchTab('editor'));

  // Clipboard copy handlers
  if (elements.copyLinkedInBtn) {
    elements.copyLinkedInBtn.addEventListener('click', () => {
      copyToClipboard(elements.linkedinMessageText ? elements.linkedinMessageText.value : '', elements.copyLinkedInBtn, 'COPY MESSAGE');
    });
  }

  if (elements.copyEmailSubjectBtn) {
    elements.copyEmailSubjectBtn.addEventListener('click', () => {
      copyToClipboard(elements.emailSubjectText ? elements.emailSubjectText.value : '', elements.copyEmailSubjectBtn, 'COPY SUBJECT');
    });
  }

  if (elements.copyEmailBtn) {
    elements.copyEmailBtn.addEventListener('click', () => {
      const subj = elements.emailSubjectText ? elements.emailSubjectText.value : '';
      const body = elements.emailBodyText ? elements.emailBodyText.value : '';
      const fullEmail = subj ? `Subject: ${subj}\n\n${body}` : body;
      copyToClipboard(fullEmail, elements.copyEmailBtn, 'COPY FULL EMAIL');
    });
  }

  // Editor syncing
  if (elements.markdownEditor) {
    elements.markdownEditor.addEventListener('input', (e) => {
      state.tailoredMarkdown = e.target.value;
      renderMarkdownResume(state.tailoredMarkdown, elements.tailoredRender);
    });
  }

  if (elements.resetEditorBtn) {
    elements.resetEditorBtn.addEventListener('click', (e) => {
      e.preventDefault();
      state.tailoredMarkdown = state.originalGeneratedMarkdown || state.tailoredMarkdown;
      if (elements.markdownEditor) elements.markdownEditor.value = state.tailoredMarkdown;
      renderMarkdownResume(state.tailoredMarkdown, elements.tailoredRender);
    });
  }

  // Downloads
  if (elements.downloadMarkdownBtn) elements.downloadMarkdownBtn.addEventListener('click', handleDownloadMarkdown);
  if (elements.downloadPdfBtn) elements.downloadPdfBtn.addEventListener('click', handleDownloadPdf);
}

function updateWordCount() {
  if (!elements.jdInput || !elements.jdWordCount) return;
  const text = elements.jdInput.value.trim();
  const words = text ? text.split(/\s+/).length : 0;
  const chars = text.length;
  elements.jdWordCount.textContent = `[ ${words} WORDS // ${chars} CHARS ]`;
}

async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    if (data.status === 'healthy' && elements.providerBadge) {
      elements.providerBadge.textContent = data.llm_provider || 'Mock Engine';
    }
  } catch (err) {
    console.error('Health check failed:', err);
  }
}

async function loadMasterResume() {
  try {
    const res = await fetch('/api/resume/master');
    const data = await res.json();
    state.originalMarkdown = data.raw_markdown;
    renderMarkdownResume(data.raw_markdown, elements.originalRender);
  } catch (err) {
    console.error('Failed to load master resume:', err);
    if (elements.originalRender) {
      elements.originalRender.innerHTML = '<p style="color: #ef4444; padding: 20px;">Failed to load master resume from data/master/.</p>';
    }
  }
}

async function handleGenerateResume() {
  if (!elements.jdInput) return;
  const jdText = elements.jdInput.value.trim();
  if (!jdText) {
    alert('Please paste a job description first.');
    return;
  }
  if (jdText.split(/\s+/).length < 15) {
    alert('Please provide a slightly more complete job description (minimum 15 words).');
    return;
  }

  // Set UI to loading state
  if (elements.generateBtn) elements.generateBtn.disabled = true;
  if (elements.processingIndicator) elements.processingIndicator.classList.remove('hidden');
  if (elements.panelTailored) elements.panelTailored.classList.add('hidden');
  if (elements.panelOriginal) elements.panelOriginal.classList.add('hidden');
  if (elements.panelDiff) elements.panelDiff.classList.add('hidden');
  if (elements.panelEditor) elements.panelEditor.classList.add('hidden');

  try {
    if (elements.processingStepText) {
      elements.processingStepText.textContent = 'STAGE 1: EXTRACTING REQUIREMENTS & MATCHING PROJECTS...';
    }

    const response = await fetch('/api/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_description: jdText,
        additional_notes: (elements.additionalNotes && elements.additionalNotes.value) ? elements.additionalNotes.value.trim() : null
      })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Unknown error occurred.' }));
      throw new Error(errData.detail || 'Tailoring failed.');
    }

    const data = await response.json();
    state.originalGeneratedMarkdown = data.tailored_markdown;
    state.tailoredMarkdown = data.tailored_markdown;
    state.analysis = data.analysis;
    state.diffs = data.diffs || [];
    state.slots = data.slots || [];

    // Render results
    renderMarkdownResume(state.tailoredMarkdown, elements.tailoredRender);
    renderDiffs(state.diffs);
    renderInsights(state.analysis, state.slots);
    if (elements.markdownEditor) elements.markdownEditor.value = state.tailoredMarkdown;

    // Switch to tailored preview
    switchTab('tailored');

  } catch (err) {
    const msg = err.message || '';
    if (msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('networkerror')) {
      alert('Error: Could not connect to the backend server. Please verify the backend server is running on http://127.0.0.1:8000.');
    } else {
      alert(`Tailoring Error: ${msg}`);
    }
    switchTab('tailored');
  } finally {
    if (elements.generateBtn) elements.generateBtn.disabled = false;
    if (elements.processingIndicator) elements.processingIndicator.classList.add('hidden');
  }
}

function switchTab(tabId) {
  state.activeTab = tabId;
  const tabs = [
    { btn: elements.tabTailored, panel: elements.panelTailored, id: 'tailored' },
    { btn: elements.tabCoverLetter, panel: elements.panelCoverLetter, id: 'coverletter' },
    { btn: elements.tabOutreach, panel: elements.panelOutreach, id: 'outreach' },
    { btn: elements.tabOriginal, panel: elements.panelOriginal, id: 'original' },
    { btn: elements.tabDiff, panel: elements.panelDiff, id: 'diff' },
    { btn: elements.tabEditor, panel: elements.panelEditor, id: 'editor' }
  ];

  tabs.forEach(t => {
    if (!t.btn || !t.panel) return;
    if (t.id === tabId) {
      t.btn.classList.add('active');
      t.btn.setAttribute('aria-selected', 'true');
      t.panel.classList.remove('hidden');
    } else {
      t.btn.classList.remove('active');
      t.btn.setAttribute('aria-selected', 'false');
      t.panel.classList.add('hidden');
    }
  });
}

function renderMarkdownResume(markdownText, targetElement) {
  if (!markdownText || !targetElement) return;

  const lines = markdownText.split('\n');
  let html = '<div class="resume-paper">';
  let inBullets = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) {
      if (inBullets) {
        html += '</ul>';
        inBullets = false;
      }
      continue;
    }

    if (line.startsWith('# ')) {
      const name = line.substring(2);
      html += `<div class="r-name">${escapeHtml(name)}</div>`;
    } else if (line.startsWith('## ')) {
      if (inBullets) { html += '</ul>'; inBullets = false; }
      const section = line.substring(3);
      html += `<div class="r-section-title">${escapeHtml(section)}</div>`;
    } else if (line.startsWith('### ')) {
      if (inBullets) { html += '</ul>'; inBullets = false; }
      const title = line.substring(4);
      const isProposed = title.includes('(Targeted Implementation') || title.includes('(Proposed') || title.includes('(Under Development');
      let titleHtml = escapeHtml(title);
      titleHtml = titleHtml.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: underline; font-weight: 600;">$1</a>');
      html += `<div class="r-job-header" style="margin-top: 10px;">
        <span>${titleHtml}</span>
        ${isProposed ? '<span class="proposal-tag">UNDER DEVELOPMENT</span>' : ''}
      </div>`;
    } else if (line.startsWith('*') && line.endsWith('*')) {
      const meta = line.substring(1, line.length - 1);
      html += `<div class="r-job-meta">${escapeHtml(meta)}</div>`;
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      if (!inBullets) {
        html += '<ul>';
        inBullets = true;
      }
      const bulletText = escapeHtml(line.substring(2));
      const formatted = bulletText.replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>');
      html += `<li>${formatted}</li>`;
    } else {
      if (inBullets) { html += '</ul>'; inBullets = false; }
      if (i === 1 && lines[0].startsWith('# ')) {
        let contactHtml = escapeHtml(line);
        // Replace markdown link [Text](url) with clickable link
        contactHtml = contactHtml.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: underline; font-weight: 600;">$1</a>');
        // If raw LinkedIn word without link, link to Manbir's LinkedIn profile
        if (!contactHtml.includes('linkedin.com') && contactHtml.includes('LinkedIn')) {
          contactHtml = contactHtml.replace('LinkedIn', '<a href="https://www.linkedin.com/in/manbir-singh-sidhu/" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: underline; font-weight: 600;">LinkedIn</a>');
        }
        // If raw GitHub word without link, link to Manbir's GitHub profile
        if (!contactHtml.includes('github.com') && contactHtml.includes('GitHub')) {
          contactHtml = contactHtml.replace('GitHub', '<a href="https://github.com/SidhuManbirSingh/SidhuManbirSingh/" target="_blank" rel="noopener noreferrer" style="color: #0284c7; text-decoration: underline; font-weight: 600;">GitHub</a>');
        }
        html += `<div class="r-contact">${contactHtml}</div>`;
      } else {
        html += `<p style="font-size: 13px; line-height: 1.5; margin: 4px 0 8px 0; color: #1e293b;">${escapeHtml(line)}</p>`;
      }
    }
  }

  if (inBullets) { html += '</ul>'; }
  html += '</div>';

  targetElement.innerHTML = html;
}

function renderDiffs(diffs) {
  if (!elements.diffContainer) return;
  if (!diffs || diffs.length === 0) {
    elements.diffContainer.innerHTML = '<p style="text-align: center; color: var(--dp-color-ink-muted); padding: 40px; font-family: var(--dp-typography-mono);">NO SECTION DIFFS CURRENTLY AVAILABLE.</p>';
    return;
  }

  let html = '';
  diffs.forEach(diff => {
    let badgeClass = 'modified';
    if (diff.change_type === 'proposed') badgeClass = 'proposed';
    if (diff.change_type === 'selected') badgeClass = 'selected';

    html += `
    <div class="diff-row">
      <div class="diff-title-bar">
        <span>// ${escapeHtml(diff.section)}</span>
        <span class="diff-badge ${badgeClass}">[ ${escapeHtml(diff.change_type)} ]</span>
      </div>
      <div class="diff-split">
        <div class="diff-pane-orig">
          <div class="pane-label" style="color: #ef4444;">&larr; ORIGINAL BASELINE</div>
          ${escapeHtml(diff.original)}
        </div>
        <div class="diff-pane-mod">
          <div class="pane-label" style="color: #22c55e;">&rarr; TARGETED MODIFICATION</div>
          ${escapeHtml(diff.modified)}
        </div>
      </div>
    </div>
  `;
  });

  elements.diffContainer.innerHTML = html;
}

function renderInsights(analysis, slots) {
  if (!analysis) return;

  if (elements.analysisCard) {
    elements.analysisCard.classList.remove('hidden');
  }

  const ats = analysis.ats_score;
  const hasAtsScore = Boolean(ats && typeof ats.overall_score === 'number');
  const scoreColor = hasAtsScore
    ? (ats.overall_score >= 75 ? '#22c55e' : (ats.overall_score >= 50 ? 'var(--dp-color-accent)' : '#ef4444'))
    : 'var(--dp-color-ink-muted)';
  const breakdownText = hasAtsScore
    ? `T: ${ats.technical_overlap}% | R: ${ats.responsibility_alignment}% | D: ${ats.domain_relevance}% | K: ${ats.keyword_coverage}%`
    : '[ N/A ]';

  if (elements.toolbarAtsScoreValue) {
    elements.toolbarAtsScoreValue.textContent = hasAtsScore ? `${ats.overall_score} / 100` : '-- / 100';
    elements.toolbarAtsScoreValue.style.color = scoreColor;
  }
  if (elements.toolbarAtsBreakdown) {
    elements.toolbarAtsBreakdown.textContent = breakdownText;
  }

  if (elements.atsScoreBadge) {
    if (hasAtsScore) {
      elements.atsScoreBadge.innerHTML = `
        <div style="display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;">
          <span style="font-size: 20px; font-weight: 700; color: ${scoreColor}; font-family: var(--dp-typography-mono);">${escapeHtml(String(ats.overall_score))} / 100</span>
          <span style="font-size: 11px; color: var(--dp-color-ink-muted); font-family: var(--dp-typography-mono);">${escapeHtml(breakdownText)}</span>
        </div>
      `;
    } else {
      elements.atsScoreBadge.textContent = '-';
    }
  }

  if (elements.targetRoleBadge) {
    elements.targetRoleBadge.textContent = analysis.target_role_title || 'Facilities Specialist';
  }

  const techs = analysis.key_technical_requirements || [];
  if (elements.keyTechBadges) {
    elements.keyTechBadges.innerHTML = techs.map(t => `
      <span style="display: inline-block; background-color: var(--dp-color-surface-elevated); border: 1px solid var(--dp-color-rule); color: var(--dp-color-accent); font-family: var(--dp-typography-mono); font-size: 11px; padding: 2px 8px; margin: 2px 4px 2px 0;">
        ${escapeHtml(t)}
      </span>
    `).join('');
  }

  if (elements.reqMatrixBadges) {
    const matrix = analysis.requirement_matrix || [];
    if (matrix.length > 0) {
      elements.reqMatrixBadges.innerHTML = matrix.slice(0, 6).map(item => {
        let lvlBg = '#7f1d1d';
        let lvlFg = '#fecaca';
        if (item.match_level === 'Strong') {
          lvlBg = '#065f46';
          lvlFg = '#a7f3d0';
        } else if (item.match_level === 'Partial') {
          lvlBg = '#78350f';
          lvlFg = '#fde68a';
        }
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 11px; font-family: var(--dp-typography-mono);">
            <span style="color: var(--dp-color-ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(item.candidate_evidence || '')}">${escapeHtml(item.requirement)}</span>
            <span style="background: ${lvlBg}; color: ${lvlFg}; padding: 1px 6px; font-size: 10px; font-weight: 700; flex-shrink: 0;">${escapeHtml(item.match_level)} (${escapeHtml(item.provenance)})</span>
          </div>
        `;
      }).join('');
    } else {
      elements.reqMatrixBadges.textContent = '-';
    }
  }

  const slot1 = (slots || []).find(s => s.slot_number === 1);
  if (slot1 && elements.slot1Desc) {
    const s1ScoreBadge = (typeof slot1.relevance_score === 'number')
      ? `<span style="background: #065f46; color: #a7f3d0; padding: 1px 6px; font-family: var(--dp-typography-mono); font-size: 10px; font-weight: 700; margin-left: 6px;">[ SCORE: ${escapeHtml(String(slot1.relevance_score))}/100 ]</span>`
      : '';
    elements.slot1Desc.innerHTML = `<span style="color: var(--dp-color-ink);">${escapeHtml(slot1.title)}</span> ${s1ScoreBadge}<br><span style="color: var(--dp-color-ink-muted); font-size: 11px; font-family: var(--dp-typography-mono);">${escapeHtml(slot1.proposal_rationale || '')}</span>`;
  }

  const slot2 = (slots || []).find(s => s.slot_number === 2);
  if (slot2 && elements.slot2Desc) {
    const badge = slot2.is_proposed
      ? '<span style="background: var(--dp-color-accent); color: var(--dp-color-ground); padding: 1px 6px; font-family: var(--dp-typography-mono); font-size: 10px; font-weight: 700; margin-left: 6px;">[ UNDER DEVELOPMENT ]</span>'
      : '<span style="background: #065f46; color: #a7f3d0; padding: 1px 6px; font-family: var(--dp-typography-mono); font-size: 10px; font-weight: 700; margin-left: 6px;">[ EXISTING PROJECT ]</span>';

    elements.slot2Desc.innerHTML = `
      <span style="color: var(--dp-color-ink);">${escapeHtml(slot2.title)}</span> ${badge}<br>
      <span style="color: var(--dp-color-ink-muted); font-size: 11px; font-family: var(--dp-typography-mono);">${escapeHtml(slot2.proposal_rationale || '')}</span>
      ${slot2.implementation_plan ? `<div style="margin-top: 6px; padding: 8px 12px; background: #241400; border: 1px solid var(--dp-color-accent); color: #fed7aa; font-size: 11px; font-family: var(--dp-typography-mono);"><strong>1-2 DAY PLAN:</strong> ${escapeHtml(slot2.implementation_plan)}</div>` : ''}
    `;
  }

  const qa = analysis.qa_report;
  const hasQa = Boolean(qa && typeof qa.passed === 'boolean');

  if (elements.toolbarQaBadge) {
    elements.toolbarQaBadge.classList.remove('pass', 'warn');
    if (hasQa) {
      elements.toolbarQaBadge.classList.remove('hidden');
      elements.toolbarQaBadge.classList.add(qa.passed ? 'pass' : 'warn');
      elements.toolbarQaBadge.textContent = qa.passed ? 'QA: PASS' : 'QA: WARN';
      elements.toolbarQaBadge.title = qa.summary || '';
    } else {
      elements.toolbarQaBadge.classList.add('hidden');
      elements.toolbarQaBadge.textContent = '';
    }
  }

  if (elements.qaReportBadge) {
    if (hasQa) {
      const qaStatusBadge = qa.passed
        ? '<span style="background: #065f46; color: #a7f3d0; padding: 1px 6px; font-family: var(--dp-typography-mono); font-size: 10px; font-weight: 700; margin-right: 6px;">[ PASS ]</span>'
        : '<span style="background: #78350f; color: #fde68a; padding: 1px 6px; font-family: var(--dp-typography-mono); font-size: 10px; font-weight: 700; margin-right: 6px;">[ WARN ]</span>';
      elements.qaReportBadge.innerHTML = `${qaStatusBadge}<span style="font-size: 11px; font-family: var(--dp-typography-mono); color: var(--dp-color-ink-muted);">${escapeHtml(qa.summary || '')}</span>`;
    } else {
      elements.qaReportBadge.textContent = '-';
    }
  }
}

function getDownloadFilename(extension) {
  const candidateName = "Manbir";
  const isCoverLetter = state.activeTab === 'coverletter';
  const isOutreach = state.activeTab === 'outreach';
  let docSuffix = "";
  if (isCoverLetter) docSuffix = " - Cover Letter";
  if (isOutreach) docSuffix = " - Outreach Messages";

  // Determine role title from analysis or fallback
  let role = (state.analysis && state.analysis.target_role_title)
    ? state.analysis.target_role_title.replace(/[^\w\s-]/g, '').trim()
    : "Operations Specialist";

  if (role.length > 40) {
    role = role.substring(0, 40).trim();
  }

  // Attempt to extract company name from analysis or job description input
  let company = "";
  if (state.analysis && state.analysis.target_company) {
    company = state.analysis.target_company.replace(/[^\w\s-]/g, '').trim();
  } else if (elements.jdInput && elements.jdInput.value) {
    const compMatch = elements.jdInput.value.match(/(?:Company|Client|Employer|Organization):\s*([^\n\r,]+)/i);
    if (compMatch && compMatch[1]) {
      company = compMatch[1].replace(/[^\w\s-]/g, '').trim();
    }
  }

  if (company && company.toLowerCase() !== "unknown" && company.toLowerCase() !== "n/a") {
    return `${candidateName} - ${role} - ${company}${docSuffix}.${extension}`;
  }

  // Fallback to timestamp serial if company is not available
  const now = new Date();
  const serial = `${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
  return `${candidateName} - ${role} - ${serial}${docSuffix}.${extension}`;
}

async function handleDownloadMarkdown() {
  const isCoverLetter = state.activeTab === 'coverletter';
  const isOutreach = state.activeTab === 'outreach';
  let content = '';

  if (isOutreach) {
    const subj = state.outreach.email_subject || (elements.emailSubjectText ? elements.emailSubjectText.value : '');
    const email = state.outreach.email_body || (elements.emailBodyText ? elements.emailBodyText.value : '');
    const linkedin = state.outreach.linkedin_message || (elements.linkedinMessageText ? elements.linkedinMessageText.value : '');
    content = `# Outreach Messages - Manbir Singh Sidhu\n\n## Version 1: LinkedIn Direct Message\n\n${linkedin}\n\n## Version 2: Direct Email Outreach\n\n**Subject:** ${subj}\n\n${email}`;
  } else if (isCoverLetter) {
    content = state.coverLetterMarkdown || state.tailoredMarkdown || state.originalMarkdown;
  } else {
    content = state.tailoredMarkdown || state.originalMarkdown;
  }

  if (!content || !content.trim()) {
    alert('No content available to download.');
    return;
  }

  const filename = getDownloadFilename('md');

  try {
    const res = await fetch('/api/export/markdown', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown_content: content, filename: filename })
    });
    const blob = await res.blob();
    triggerBlobDownload(blob, filename);
  } catch (err) {
    alert(`Markdown download failed: ${err.message}`);
  }
}

async function handleDownloadPdf() {
  const isCoverLetter = state.activeTab === 'coverletter';
  const isOutreach = state.activeTab === 'outreach';
  let content = '';

  if (isOutreach) {
    const subj = state.outreach.email_subject || (elements.emailSubjectText ? elements.emailSubjectText.value : '');
    const email = state.outreach.email_body || (elements.emailBodyText ? elements.emailBodyText.value : '');
    const linkedin = state.outreach.linkedin_message || (elements.linkedinMessageText ? elements.linkedinMessageText.value : '');
    content = `# Outreach Messages - Manbir Singh Sidhu\nSurrey, BC | +1 778-956-1186 | manbirs285@gmail.com | [LinkedIn](https://www.linkedin.com/in/manbir-singh-sidhu/)\n\n## Version 1: LinkedIn Direct Message\n\n${linkedin}\n\n## Version 2: Direct Email Outreach\n\n**Subject:** ${subj}\n\n${email}`;
  } else if (isCoverLetter) {
    content = state.coverLetterMarkdown || state.tailoredMarkdown || state.originalMarkdown;
  } else {
    content = state.tailoredMarkdown || state.originalMarkdown;
  }

  if (!content || !content.trim()) {
    alert('No content available to download.');
    return;
  }

  const filename = getDownloadFilename('pdf');

  try {
    if (elements.downloadPdfBtn) {
      elements.downloadPdfBtn.disabled = true;
      elements.downloadPdfBtn.textContent = 'COMPILING PDF...';
    }

    const res = await fetch('/api/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown_content: content, filename: filename })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'PDF compilation failed.' }));
      throw new Error(err.detail);
    }

    const blob = await res.blob();
    triggerBlobDownload(blob, filename);
  } catch (err) {
    alert(`PDF download failed: ${err.message}`);
  } finally {
    if (elements.downloadPdfBtn) {
      elements.downloadPdfBtn.disabled = false;
      elements.downloadPdfBtn.innerHTML = '<span>DOWNLOAD ATS PDF &darr;</span>';
    }
  }
}

async function handleGenerateCoverLetter() {
  if (!elements.jdInput) return;
  const jdText = elements.jdInput.value.trim();
  if (!jdText) {
    alert('Please paste a job description first.');
    return;
  }
  if (jdText.split(/\s+/).length < 15) {
    alert('Please provide a slightly more complete job description (minimum 15 words).');
    return;
  }

  // Set UI to loading state
  if (elements.generateCoverLetterBtn) elements.generateCoverLetterBtn.disabled = true;
  if (elements.generateBtn) elements.generateBtn.disabled = true;
  if (elements.processingIndicator) elements.processingIndicator.classList.remove('hidden');
  if (elements.processingStepText) {
    elements.processingStepText.textContent = 'CRAFTING TARGETED & CATCHY COVER LETTER...';
  }

  try {
    const response = await fetch('/api/tailor/cover-letter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_description: jdText,
        tailored_markdown: state.tailoredMarkdown || null,
        additional_notes: (elements.additionalNotes && elements.additionalNotes.value) ? elements.additionalNotes.value.trim() : null
      })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Cover letter generation failed.' }));
      throw new Error(errData.detail || 'Cover letter generation failed.');
    }

    const data = await response.json();
    state.coverLetterMarkdown = data.cover_letter_markdown;
    if (!state.analysis) state.analysis = {};
    if (data.target_role_title) state.analysis.target_role_title = data.target_role_title;
    if (data.target_company) state.analysis.target_company = data.target_company;

    // Render cover letter
    renderMarkdownResume(state.coverLetterMarkdown, elements.coverLetterRender);
    switchTab('coverletter');
  } catch (err) {
    const msg = err.message || '';
    if (msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('networkerror')) {
      alert('Error: Could not connect to the backend server. Please verify the backend server is running on http://127.0.0.1:8000.');
    } else {
      alert(`Cover Letter Error: ${msg}`);
    }
    switchTab('coverletter');
  } finally {
    if (elements.generateCoverLetterBtn) elements.generateCoverLetterBtn.disabled = false;
    if (elements.generateBtn) elements.generateBtn.disabled = false;
    if (elements.processingIndicator) elements.processingIndicator.classList.add('hidden');
  }
}

async function handleGenerateOutreach() {
  if (!elements.jdInput) return;
  const jdText = elements.jdInput.value.trim();
  if (!jdText) {
    alert('Please paste a job description first.');
    return;
  }
  if (jdText.split(/\s+/).length < 15) {
    alert('Please provide a slightly more complete job description (minimum 15 words).');
    return;
  }

  // Set UI to loading state
  if (elements.generateOutreachBtn) elements.generateOutreachBtn.disabled = true;
  if (elements.generateBtn) elements.generateBtn.disabled = true;
  if (elements.generateCoverLetterBtn) elements.generateCoverLetterBtn.disabled = true;
  if (elements.processingIndicator) elements.processingIndicator.classList.remove('hidden');
  if (elements.processingStepText) {
    elements.processingStepText.textContent = 'CRAFTING TARGETED LINKEDIN & EMAIL OUTREACH MESSAGES...';
  }

  try {
    const response = await fetch('/api/tailor/outreach', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_description: jdText,
        tailored_markdown: state.tailoredMarkdown || null,
        additional_notes: (elements.additionalNotes && elements.additionalNotes.value) ? elements.additionalNotes.value.trim() : null
      })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Outreach generation failed.' }));
      throw new Error(errData.detail || 'Outreach generation failed.');
    }

    const data = await response.json();
    state.outreach = {
      linkedin_message: data.linkedin_message || '',
      email_subject: data.email_subject || '',
      email_body: data.email_body || ''
    };

    if (elements.linkedinMessageText) elements.linkedinMessageText.value = state.outreach.linkedin_message;
    if (elements.emailSubjectText) elements.emailSubjectText.value = state.outreach.email_subject;
    if (elements.emailBodyText) elements.emailBodyText.value = state.outreach.email_body;

    updateOutreachStats();
    switchTab('outreach');
  } catch (err) {
    const msg = err.message || '';
    if (msg.toLowerCase().includes('failed to fetch') || msg.toLowerCase().includes('networkerror')) {
      alert('Error: Could not connect to the backend server. Please verify the backend server is running on http://127.0.0.1:8000.');
    } else {
      alert(`Outreach Generation Error: ${msg}`);
    }
    switchTab('outreach');
  } finally {
    if (elements.generateOutreachBtn) elements.generateOutreachBtn.disabled = false;
    if (elements.generateBtn) elements.generateBtn.disabled = false;
    if (elements.generateCoverLetterBtn) elements.generateCoverLetterBtn.disabled = false;
    if (elements.processingIndicator) elements.processingIndicator.classList.add('hidden');
  }
}

function updateOutreachStats() {
  if (elements.linkedinMessageText && elements.linkedinStats) {
    const text = elements.linkedinMessageText.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    elements.linkedinStats.textContent = `[ ${words} WORDS // ${text.length} CHARS ]`;
  }
  if (elements.emailBodyText && elements.emailStats) {
    const text = elements.emailBodyText.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    elements.emailStats.textContent = `[ ${words} WORDS // ${text.length} CHARS ]`;
  }
}

async function copyToClipboard(text, btnElement, defaultLabel) {
  if (!text || !text.trim()) {
    alert('Nothing to copy yet. Trigger "TAILOR OUTREACH" first.');
    return;
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }

    if (btnElement) {
      btnElement.classList.add('copied');
      btnElement.textContent = 'COPIED!';
      setTimeout(() => {
        btnElement.classList.remove('copied');
        btnElement.textContent = defaultLabel;
      }, 2000);
    }
  } catch (err) {
    alert('Could not copy to clipboard: ' + err.message);
  }
}

function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Auto-run init
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
