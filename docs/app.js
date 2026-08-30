const copy = {
  en: {
    skip: "Skip to content",
    homeLabel: "PaperRoach home",
    githubLabel: "Open the PaperRoach repository on GitHub",
    navLabel: "Primary navigation",
    trustLabel: "Project commitments",
    coreIdeaLabel: "Core idea",
    osLabel: "Operating system",
    navOutput: "Live demo",
    navInstall: "Install",
    navPrinciples: "Why local",
    github: "GitHub",
    eyebrow: "Public case / one local run",
    heroTitle: "This one PDF produced one paper note and four concept notes.",
    heroLede: "Open the unchanged 14-page input, the publication-sanitized machine draft generated from it, and all four derivative drafts from that local run. Source-checked copies and corrections stay public beside them.",
    heroDemoBadge: "ONE LOCAL RUN",
    heroDemoTitle: "Scroll the lineage. Inspect each real file below.",
    heroDemoOpen: "Inspect full case ↗",
    startInstall: "Start installing",
    fullGuide: "Read the full guide",
    trustTelemetry: "No telemetry",
    trustZotero: "Zotero stays read-only",
    trustLicense: "MIT licensed",
    stageLabel: "ACTUAL GENERATED LINEAGE / PUBLIC CASE",
    lineageScrollSource: "01 / PDF ↓",
    lineageScrollNote: "02 / PAPER NOTE ↓",
    lineageScrollConcepts: "03 / CONCEPT NOTES",
    lineageScrollAll: "PDF → NOTE → CONCEPTS",
    lineageScrollInstruction: "Scroll to reveal the paper note, then its concept notes.",
    lineageStaticInstruction: "The source PDF, paper note, and concept notes are all shown below.",
    lineageAllInstruction: "All three artifact stages are visible because reduced motion is enabled.",
    lineageLabel: "Actual artifact lineage: source PDF to paper note to four concept notes",
    lineageSource: "SOURCE PDF",
    lineageSourceName: "Unchanged article",
    lineageSourceMeta: "14 pages · CC BY 4.0",
    lineagePaperNote: "PAPER NOTE",
    lineagePaperNoteName: "Generated paper-note draft",
    lineageReviewedMeta: "Source-checked sibling opens below",
    lineageConcepts: "CONCEPT NOTES",
    lineageConceptCount: "4 generated concept drafts",
    lineageConceptMeta: "Generated from paper-note.generated.md",
    lineagePreviewReviewedAction: "Preview its source-checked sibling",
    conceptAffective: "Affective Dynamics Model",
    conceptRelaxation: "Exponential Relaxation",
    conceptBaseline: "Individual Baseline",
    conceptRegulation: "Regulation Effect",
    lineagePreviewLabel: "Selected actual artifact preview",
    lineageActionsLabel: "Selected artifact actions",
    lineageStatusSource: "UNCHANGED SOURCE",
    lineageStatusReviewed: "SOURCE-CHECKED COPY",
    lineageFrameSuffix: "source-checked Markdown preview",
    lineageOpenDraft: "Generated draft ↗",
    lineageOpenFile: "Open file ↗",
    lineagePdfPreviewLabel: "Open the unchanged source PDF",
    lineageProof: "Arrows follow *.generated.md; preview defaults to source-checked sibling files.",
    lineageProofShort: "Generated lineage · source-checked preview",
    lineageCredit: "Pellert, Schweighofer & Garcia (2020) · © The Author(s) 2020 · CC BY 4.0",
    lineageCreditShort: "Pellert et al. (2020) · CC BY 4.0",
    lineageProvenanceLabel: "Source and provenance links",
    lineageAttribution: "Credit ↗",
    statement: "A paper folder stores files. <strong>PaperRoach builds memory.</strong>",
    workflowEyebrow: "FROM INBOX TO KNOWLEDGE",
    workflowTitle: "One pipeline, four useful outcomes.",
    workflowLede: "Start with one PDF or watch your Zotero library. PaperRoach keeps the source, note, concepts, and search index connected.",
    outcomeMetadata: "Bibliographic context",
    outcomeMetadataBody: "Title, authors, year, venue, DOI, and tags flow from Zotero when available.",
    outcomeNotes: "Notes you can edit",
    outcomeNotesBody: "Structured Markdown lands in your vault. Rebuilds keep everything under “My Notes.”",
    outcomeLinks: "Concept links",
    outcomeLinksBody: "Important concepts become Obsidian links so each new paper strengthens the graph.",
    outcomeSearch: "Local search",
    outcomeSearchBody: "LanceDB and local embeddings make the library searchable without a hosted knowledge service.",
    outputEyebrow: "SEPARATE OUTPUT EXAMPLE / ANOTHER RUN",
    outputTitle: "Feed it one real PDF. Here’s what lands in Obsidian.",
    outputLede: "This sanitized excerpt comes from an actual 24-page paper processed with PaperRoach. It is generated Markdown, not a mockup.",
    outputRun: "REAL RUN",
    outputSourcePaper: "Open the source paper",
    outputInputLabel: "ACTUAL INPUT",
    outputInputMeta: "Zotero metadata found",
    outputInputText: "PDF text extracted",
    outputInputFigures: "Figures detected",
    outputMyNotes: "Your own writing stays here when the note is rebuilt.",
    outputLedgerLabel: "Actual run summary",
    outputLedgerTitle: "WHAT THE RUN PRODUCED",
    outputPages: "source pages",
    outputFigures: "figure assets",
    outputConcepts: "concept links",
    outputMarkdown: "editable note",
    outputFilesTitle: "FILES IN THE VAULT",
    outputCaption: "Actual output, lightly shortened for the page. Local file paths and identifiers were removed. Model-generated analysis should always be checked against the source paper.",
    outputRawSummary: "Inspect the raw Markdown excerpt",
    outputCaseLabel: "NEW / COMPLETE PUBLIC CASE",
    outputCaseTitle: "Open the original PDF, generated Markdown, and four derivative notes.",
    outputCaseBody: "CC BY 4.0 source · raw and reviewed copies · checksums · change log",
    outputCaseAction: "Explore every file →",
    installEyebrow: "FIRST RUN",
    installTitle: "From a clean machine to the first note.",
    installLede: "Python 3.11–3.12, Obsidian, and Ollama are required. Zotero is optional for manual PDFs and recommended for automatic ingestion.",
    stepApps: "Install the companion apps",
    stepAppsBody: "Install uv for a current Python 3.12 patch, create or open an Obsidian vault, then install and start Ollama.",
    stepInstall: "Install PaperRoach",
    stepInstallBody: "Install the published command into its own isolated environment. No repository clone or environment activation is needed.",
    viewPypi: "View PaperRoach on PyPI ↗",
    stepSetup: "Run safe setup",
    stepSetupBody: "PaperRoach finds vaults Obsidian has opened, writes user-level config, detects Zotero when possible, and pulls the required models.",
    stepVerify: "Verify, then build one PDF",
    stepVerifyBody: "Doctor explains what is ready. At the prompt, paste the real path to one PDF before scanning the whole library.",
    terminalTitle: "SETUP TERMINAL",
    copy: "Copy",
    copied: "Copied",
    copyFailed: "Select and copy",
    setupDone: "Setup is repeatable and non-destructive.",
    setupDoneSmall: "Existing vault files and custom settings are left alone.",
    openGuide: "Open the step-by-step installation guide",
    principlesEyebrow: "DESIGNED FOR OWNERSHIP",
    principlesTitle: "Your research system should still work when a service does not.",
    localTitle: "Inference where you choose",
    localBody: "The default Ollama host is localhost. If you configure a remote host, extracted text and requested figure images go there—nowhere else.",
    plainTitle: "Markdown, not a silo",
    plainBody: "Generated notes are ordinary files in your Obsidian vault. Read them, edit them, version them, or leave PaperRoach.",
    openTitle: "MIT licensed and inspectable",
    openBody: "Use it, fork it, and help shape it. The project is early alpha, so honest issues and focused pull requests matter.",
    closingEyebrow: "YOUR NEXT PAPER",
    closingTitle: "Read it once. Keep it useful.",
    installNow: "Install PaperRoach",
    askQuestion: "Ask a question on GitHub ↗",
    footer: "Local-first paper knowledge. Built in the open."
  },
  ko: {
    skip: "본문으로 바로가기",
    homeLabel: "PaperRoach 홈",
    githubLabel: "GitHub에서 PaperRoach 저장소 열기",
    navLabel: "주요 탐색",
    trustLabel: "프로젝트 약속",
    coreIdeaLabel: "핵심 생각",
    osLabel: "운영체제",
    navOutput: "실제 데모",
    navInstall: "설치",
    navPrinciples: "로컬을 택한 이유",
    github: "GitHub",
    eyebrow: "공개 사례 / 한 번의 로컬 실행",
    heroTitle: "이 PDF 한 편에서 정리 노트 한 개와 개념 노트 네 개가 나왔습니다.",
    heroLede: "한 번의 로컬 실행에 사용한 변경 없는 14쪽 원문과, 그 실행에서 생성된 공개용 Markdown 및 네 개의 파생 초안을 직접 열어보세요. 원문 대조본과 수정 내역도 함께 공개합니다.",
    heroDemoBadge: "로컬 실행 1회",
    heroDemoTitle: "스크롤로 계보를 따라가며 실제 파일을 아래에서 확인하세요.",
    heroDemoOpen: "전체 사례 살펴보기 ↗",
    startInstall: "설치 시작하기",
    fullGuide: "전체 가이드 읽기",
    trustTelemetry: "텔레메트리 없음",
    trustZotero: "Zotero 읽기 전용",
    trustLicense: "MIT 라이선스",
    stageLabel: "실제 생성 계보 / 공개 사례",
    lineageScrollSource: "01 / PDF ↓",
    lineageScrollNote: "02 / 정리 노트 ↓",
    lineageScrollConcepts: "03 / 개념 노트",
    lineageScrollAll: "PDF → 정리 노트 → 개념 노트",
    lineageScrollInstruction: "스크롤하면 정리 노트와 파생 개념 노트가 차례로 나타납니다.",
    lineageStaticInstruction: "원문 PDF, 정리 노트, 파생 개념 노트를 모두 표시합니다.",
    lineageAllInstruction: "모션 감소 설정에 따라 세 산출물 단계를 모두 표시합니다.",
    lineageLabel: "실제 산출물 연결: 원문 PDF에서 정리 노트와 네 개의 개념 노트까지",
    lineageSource: "원문 PDF",
    lineageSourceName: "원문 그대로",
    lineageSourceMeta: "14쪽 · CC BY 4.0",
    lineagePaperNote: "정리 노트",
    lineagePaperNoteName: "생성된 논문 정리 초안",
    lineageReviewedMeta: "아래에는 원문 대조본 표시",
    lineageConcepts: "파생 개념 노트",
    lineageConceptCount: "생성된 개념 초안 4개",
    lineageConceptMeta: "paper-note.generated.md에서 파생",
    lineagePreviewReviewedAction: "대응 원문 대조본 미리보기",
    conceptAffective: "정서 역학 모델",
    conceptRelaxation: "지수 이완",
    conceptBaseline: "개인 기준선",
    conceptRegulation: "조절 효과",
    lineagePreviewLabel: "선택한 실제 산출물 미리보기",
    lineageActionsLabel: "선택한 산출물 작업",
    lineageStatusSource: "원문 그대로",
    lineageStatusReviewed: "원문 대조본",
    lineageFrameSuffix: "원문 대조 Markdown 미리보기",
    lineageOpenDraft: "실제 생성 초안 ↗",
    lineageOpenFile: "파일 열기 ↗",
    lineagePdfPreviewLabel: "변경되지 않은 원문 PDF 열기",
    lineageProof: "화살표는 *.generated.md 계보입니다. 미리보기는 대응 원문 대조본을 기본으로 엽니다.",
    lineageProofShort: "생성 계보 · 원문 대조 미리보기",
    lineageCredit: "Pellert, Schweighofer & Garcia (2020) · © The Author(s) 2020 · CC BY 4.0",
    lineageCreditShort: "Pellert 외 (2020) · CC BY 4.0",
    lineageProvenanceLabel: "출처 및 계보 링크",
    lineageAttribution: "출처 ↗",
    statement: "논문 폴더는 파일을 모읍니다. <strong>PaperRoach는 기억을 만듭니다.</strong>",
    workflowEyebrow: "받은 논문에서 지식까지",
    workflowTitle: "하나의 흐름, 네 가지 쓸모.",
    workflowLede: "PDF 한 편으로 시작하거나 Zotero 라이브러리를 감시하세요. 원문, 노트, 개념, 검색 색인이 계속 연결됩니다.",
    outcomeMetadata: "서지 정보의 맥락",
    outcomeMetadataBody: "가능한 경우 Zotero에서 제목, 저자, 연도, 학술지, DOI, 태그를 가져옵니다.",
    outcomeNotes: "내가 편집하는 노트",
    outcomeNotesBody: "구조화된 Markdown이 vault에 저장됩니다. 다시 빌드해도 ‘My Notes’ 아래에 쓴 내용은 보존됩니다.",
    outcomeLinks: "개념 연결",
    outcomeLinksBody: "핵심 개념을 Obsidian 링크로 만들어 논문이 늘어날수록 지식 그래프도 단단해집니다.",
    outcomeSearch: "로컬 검색",
    outcomeSearchBody: "LanceDB와 로컬 임베딩으로 별도 호스팅 지식 서비스 없이 전체 라이브러리를 검색합니다.",
    outputEyebrow: "별도 산출물 예시 / 다른 로컬 실행",
    outputTitle: "실제 PDF 한 편을 넣으면, Obsidian에 이렇게 남습니다.",
    outputLede: "PaperRoach가 실제 24쪽 논문을 처리한 결과에서 로컬 경로와 내부 식별자만 제거했습니다. 목업이 아니라 생성된 Markdown입니다.",
    outputRun: "실제 실행",
    outputSourcePaper: "원문 논문 열기",
    outputInputLabel: "실제 입력",
    outputInputMeta: "Zotero 서지 정보 탐지",
    outputInputText: "PDF 본문 추출",
    outputInputFigures: "그림 탐지",
    outputMyNotes: "다시 빌드해도 직접 쓴 내용은 이곳에 그대로 남습니다.",
    outputLedgerLabel: "실제 실행 결과 요약",
    outputLedgerTitle: "이번 실행이 만든 것",
    outputPages: "원문 페이지",
    outputFigures: "그림 자산",
    outputConcepts: "개념 링크",
    outputMarkdown: "편집 가능한 노트",
    outputFilesTitle: "VAULT에 생긴 파일",
    outputCaption: "실제 출력물을 웹에 맞게 짧게 줄였습니다. 로컬 파일 경로와 내부 식별자는 제거했습니다. 모델이 생성한 분석은 반드시 원문과 대조하세요.",
    outputRawSummary: "실제 Markdown 발췌 보기",
    outputCaseLabel: "새 공개 자료 / 전체 사례",
    outputCaseTitle: "원문 PDF, 생성 Markdown, 파생 노트 네 개를 모두 여세요.",
    outputCaseBody: "CC BY 4.0 원문 · 생성본과 교정본 · 체크섬 · 변경 이력",
    outputCaseAction: "모든 파일 살펴보기 →",
    installEyebrow: "첫 실행",
    installTitle: "빈 컴퓨터에서 첫 노트까지.",
    installLede: "Python 3.11–3.12, Obsidian, Ollama가 필요합니다. Zotero는 직접 PDF를 처리할 때는 선택 사항이고, 자동 수집에는 권장됩니다.",
    stepApps: "함께 쓸 앱 설치",
    stepAppsBody: "uv로 최신 보안 패치가 적용된 Python 3.12를 준비하고, Obsidian vault를 만들거나 연 뒤 Ollama를 설치하고 실행하세요.",
    stepInstall: "PaperRoach 설치",
    stepInstallBody: "공개 패키지를 독립된 환경에 설치합니다. 저장소 clone이나 가상환경 활성화가 필요 없습니다.",
    viewPypi: "PyPI에서 PaperRoach 보기 ↗",
    stepSetup: "안전한 초기 설정",
    stepSetupBody: "Obsidian이 열어 본 vault를 찾고 사용자 설정을 만든 뒤, 가능한 경우 Zotero를 탐지하고 필요한 모델을 받습니다.",
    stepVerify: "확인하고 PDF 한 편 빌드",
    stepVerifyBody: "doctor가 준비 상태를 설명합니다. 전체 라이브러리를 스캔하기 전에 프롬프트에 실제 PDF 한 편의 경로를 붙여 넣으세요.",
    terminalTitle: "설치 터미널",
    copy: "복사",
    copied: "복사됨",
    copyFailed: "선택해서 복사",
    setupDone: "설정은 여러 번 실행해도 안전합니다.",
    setupDoneSmall: "기존 vault 파일과 사용자 설정을 덮어쓰지 않습니다.",
    openGuide: "단계별 신규 사용자 설치 가이드 열기",
    principlesEyebrow: "소유권을 위한 설계",
    principlesTitle: "어떤 서비스가 멈춰도 연구 시스템은 계속 작동해야 합니다.",
    localTitle: "내가 정한 곳에서 추론",
    localBody: "기본 Ollama 주소는 localhost입니다. 원격 주소를 직접 설정한 경우에만 추출한 텍스트와 요청한 그림이 그 서버로 전송됩니다.",
    plainTitle: "사일로가 아닌 Markdown",
    plainBody: "생성된 노트는 Obsidian vault의 평범한 파일입니다. 읽고, 고치고, 버전 관리하고, 언제든 다른 도구로 옮길 수 있습니다.",
    openTitle: "검토 가능한 MIT 오픈소스",
    openBody: "사용하고, fork하고, 함께 다듬어 주세요. 아직 초기 알파이므로 솔직한 이슈와 집중된 pull request가 특히 중요합니다.",
    closingEyebrow: "다음 논문부터",
    closingTitle: "한 번 읽고, 계속 써먹기.",
    installNow: "PaperRoach 설치하기",
    askQuestion: "GitHub에서 질문하기 ↗",
    footer: "로컬 우선 논문 지식. 공개된 코드로 함께 만듭니다."
  }
};

const root = document.documentElement;
const languageButton = document.querySelector(".language-toggle");
const htmlCopyKeys = new Set(["statement"]);
const canStore = (() => {
  try {
    localStorage.setItem("paperroach-storage-test", "1");
    localStorage.removeItem("paperroach-storage-test");
    return true;
  } catch {
    return false;
  }
})();

function setLanguage(language) {
  const next = language === "ko" ? "ko" : "en";
  root.lang = next;
  root.dataset.language = next;

  document.querySelectorAll("[data-copy]").forEach((element) => {
    const key = element.dataset.copy;
    const value = copy[next][key];
    if (!value) return;
    if (htmlCopyKeys.has(key)) element.innerHTML = value;
    else element.textContent = value;
    element.lang = next;
  });
  document.querySelectorAll("[data-label-copy]").forEach((element) => {
    const value = copy[next][element.dataset.labelCopy];
    if (value) element.setAttribute("aria-label", value);
  });

  languageButton.setAttribute(
    "aria-label",
    next === "ko" ? "View in English" : "한국어로 보기"
  );
  document.title = next === "ko"
    ? "PaperRoach — 로컬 우선 논문 지식"
    : "PaperRoach — Local-first paper knowledge";
  updateLineagePreviewCopy();
  updateLineageScrollCopy();
  if (canStore) localStorage.setItem("paperroach-language", next);
}

const savedLanguage = canStore ? localStorage.getItem("paperroach-language") : null;
const preferredLanguage = savedLanguage || (navigator.language.toLowerCase().startsWith("ko") ? "ko" : "en");
setLanguage(preferredLanguage);

languageButton.addEventListener("click", () => {
  setLanguage(root.dataset.language === "ko" ? "en" : "ko");
});

const tabs = [...document.querySelectorAll('[role="tab"]')];
const panels = [...document.querySelectorAll('[role="tabpanel"]')];

function selectOperatingSystem(os, focus = false) {
  tabs.forEach((tab) => {
    const selected = tab.dataset.os === os;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  });
  panels.forEach((panel) => {
    panel.hidden = panel.id !== (os === "windows" ? "windows-code" : "unix-code");
  });
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => selectOperatingSystem(tab.dataset.os));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (index + direction + tabs.length) % tabs.length;
    selectOperatingSystem(tabs[nextIndex].dataset.os, true);
  });
});

selectOperatingSystem(navigator.userAgent.includes("Windows") ? "windows" : "unix");

document.querySelector(".copy-button").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  const label = button.querySelector("span");
  const activePanel = panels.find((panel) => !panel.hidden);
  const commands = activePanel.innerText
    .split("\n")
    .map((line) => line.replace(/^[>$]\s?/, ""))
    .join("\n");

  try {
    await navigator.clipboard.writeText(commands);
    label.textContent = copy[root.dataset.language].copied;
  } catch {
    label.textContent = copy[root.dataset.language].copyFailed;
  }

  window.setTimeout(() => {
    label.textContent = copy[root.dataset.language].copy;
  }, 1800);
});

const lineageNodes = [...document.querySelectorAll("[data-lineage-file]")];
const lineageFrame = document.querySelector(".lineage-preview iframe");
const lineagePdfPreview = document.querySelector(".lineage-pdf-preview");
const lineagePath = document.querySelector("[data-lineage-path]");
const lineageOpen = document.querySelector("[data-lineage-open]");
const lineageDraft = document.querySelector("[data-lineage-draft-link]");
const lineageScroll = document.querySelector("[data-lineage-scroll]");
const lineageStage = document.querySelector(".landing-demo-stage");
const lineageStageGroups = [
  document.querySelector(".lineage-source-stage"),
  document.querySelector(".lineage-note-stage"),
  document.querySelector(".lineage-concept-stage"),
];
const lineageStepNodes = [
  document.querySelector(".lineage-source-node"),
  document.querySelector(".lineage-note-node"),
  document.querySelector(".lineage-concept-list button"),
];
const lineageCompactQuery = window.matchMedia("(max-width: 760px)");
const lineageReducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const caseRoot = "examples/affective-dynamics/";
let activeLineageScrollStep = -1;
let lineageScrollFrame = 0;

function lineageViewerUrl(path, embedded = false) {
  const params = new URLSearchParams({ file: path });
  if (embedded) params.set("embed", "1");
  return `${caseRoot}markdown-viewer.html?${params}`;
}

function updateLineagePreviewCopy() {
  const activeNode = document.querySelector("[data-lineage-file].is-selected");
  const status = document.querySelector("[data-lineage-status]");
  const frame = document.querySelector(".lineage-preview iframe");
  if (!activeNode || !status || !frame) return;
  const language = root.dataset.language || "en";
  const statusKey = activeNode.dataset.lineageStatusCopy;
  const name = activeNode.querySelector(".lineage-node-name")?.textContent.trim();
  status.textContent = copy[language][statusKey] || "";
  status.lang = language;
  if (!frame.hidden && name) {
    frame.title = `${name} — ${copy[language].lineageFrameSuffix}`;
  }
}

function updateLineageScrollCopy() {
  const stage = document.querySelector("[data-lineage-step]");
  const label = document.querySelector("[data-lineage-scroll-label]");
  const instruction = document.querySelector("#lineage-scroll-instruction");
  if (!stage || !label || !instruction) return;
  const stepKeys = {
    source: "lineageScrollSource",
    note: "lineageScrollNote",
    concepts: "lineageScrollConcepts",
    all: "lineageScrollAll",
  };
  const ready = stage.classList.contains("is-scroll-ready");
  const key = ready
    ? stepKeys[stage.dataset.lineageStep] || stepKeys.source
    : stepKeys.all;
  const language = root.dataset.language || "en";
  label.dataset.copy = key;
  label.textContent = copy[language][key];
  label.lang = language;
  const instructionKey = !ready
    ? "lineageStaticInstruction"
    : stage.dataset.lineageStep === "all"
      ? "lineageAllInstruction"
      : "lineageScrollInstruction";
  instruction.dataset.copy = instructionKey;
  instruction.textContent = copy[language][instructionKey];
  instruction.lang = language;
}

function selectLineageArtifact(node, focus = false) {
  lineageNodes.forEach((candidate) => {
    const selected = candidate === node;
    candidate.classList.toggle("is-selected", selected);
    candidate.setAttribute("aria-pressed", String(selected));
  });

  const path = node.dataset.lineageFile;
  const draftPath = node.dataset.lineageDraft;
  const isPdf = node.dataset.lineageKind === "pdf";
  lineagePath.textContent = path;

  if (isPdf) {
    const pdfUrl = `${caseRoot}${path}`;
    lineageOpen.href = pdfUrl;
    lineageDraft.hidden = true;
    lineagePdfPreview.href = pdfUrl;
    lineagePdfPreview.hidden = false;
    lineageFrame.hidden = true;
  } else {
    const frameUrl = lineageViewerUrl(path, true);
    lineageOpen.href = lineageViewerUrl(path);
    lineageDraft.href = draftPath ? lineageViewerUrl(draftPath) : "";
    lineageDraft.hidden = !draftPath;
    if (lineageFrame.getAttribute("src") !== frameUrl) lineageFrame.src = frameUrl;
    lineageFrame.hidden = false;
    lineagePdfPreview.hidden = true;
  }

  updateLineagePreviewCopy();
  if (focus) node.focus();
}

lineageNodes.forEach((node) => {
  node.addEventListener("click", () => {
    alignLineageStepWithNode(node);
    selectLineageArtifact(node);
  });
  node.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const availableNodes = lineageNodes.filter((candidate) => !candidate.closest("[inert]"));
    const index = availableNodes.indexOf(node);
    let nextIndex = index;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + availableNodes.length) % availableNodes.length;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % availableNodes.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = availableNodes.length - 1;
    const nextNode = availableNodes[nextIndex];
    alignLineageStepWithNode(nextNode);
    selectLineageArtifact(nextNode, true);
  });
});

function setLineageStageAvailability(stepIndex, revealAll = false) {
  lineageStageGroups.forEach((group, index) => {
    const unavailable = !revealAll && (
      lineageCompactQuery.matches ? index !== stepIndex : index > stepIndex
    );
    group.toggleAttribute("inert", unavailable);
    if (unavailable) group.setAttribute("aria-hidden", "true");
    else group.removeAttribute("aria-hidden");
  });
}

function setLineageScrollStep(stepIndex, force = false, selectDefault = true) {
  const boundedStep = Math.max(0, Math.min(lineageStepNodes.length - 1, stepIndex));
  const changed = boundedStep !== activeLineageScrollStep;
  if (!changed && !force) return;
  activeLineageScrollStep = boundedStep;
  lineageStage.dataset.lineageStep = ["source", "note", "concepts"][boundedStep];
  setLineageStageAvailability(boundedStep);
  updateLineageScrollCopy();
  const selectedNode = document.querySelector("[data-lineage-file].is-selected");
  const selectionUnavailable = !selectedNode || Boolean(selectedNode.closest("[inert]"));
  if (selectDefault && (changed || selectionUnavailable)) {
    selectLineageArtifact(lineageStepNodes[boundedStep]);
  }
}

function lineageStepIndexForNode(node) {
  return lineageStageGroups.findIndex((group) => group.contains(node));
}

function scrollLineageToStep(stepIndex) {
  const stageTop = Number.parseFloat(getComputedStyle(lineageStage).top) || 0;
  const scrollSpan = Math.max(1, lineageScroll.offsetHeight - lineageStage.offsetHeight);
  const wrapperTop = window.scrollY + lineageScroll.getBoundingClientRect().top;
  const targetProgress = [.05, .5, .85][stepIndex];
  const previousScrollBehavior = document.documentElement.style.scrollBehavior;
  document.documentElement.style.scrollBehavior = "auto";
  window.scrollTo({
    top: wrapperTop - stageTop + scrollSpan * targetProgress,
    behavior: "auto",
  });
  document.documentElement.style.scrollBehavior = previousScrollBehavior;
}

function alignLineageStepWithNode(node) {
  if (lineageReducedMotionQuery.matches) return;
  const targetStep = lineageStepIndexForNode(node);
  if (targetStep < 0 || targetStep === activeLineageScrollStep) return;
  setLineageScrollStep(targetStep, true, false);
  scrollLineageToStep(targetStep);
}

function updateLineageFromScroll(force = false) {
  const reducedMotion = lineageReducedMotionQuery.matches;
  lineageScroll.classList.add("is-scroll-ready");
  lineageScroll.classList.toggle("is-reduced-motion", reducedMotion);
  lineageStage.classList.toggle("is-reduced-motion", reducedMotion);
  lineageStage.classList.add("is-scroll-ready");

  if (reducedMotion) {
    activeLineageScrollStep = -1;
    lineageStage.dataset.lineageStep = "all";
    setLineageStageAvailability(0, true);
    updateLineageScrollCopy();
    return;
  }

  const stageTop = Number.parseFloat(getComputedStyle(lineageStage).top) || 0;
  const scrollSpan = Math.max(1, lineageScroll.offsetHeight - lineageStage.offsetHeight);
  const progress = Math.max(0, Math.min(1, (stageTop - lineageScroll.getBoundingClientRect().top) / scrollSpan));
  const stepIndex = progress < .34 ? 0 : progress < .67 ? 1 : 2;
  setLineageScrollStep(stepIndex, force);
}

function queueLineageScrollUpdate() {
  if (lineageScrollFrame) return;
  lineageScrollFrame = window.requestAnimationFrame(() => {
    lineageScrollFrame = 0;
    updateLineageFromScroll();
  });
}

window.addEventListener("scroll", queueLineageScrollUpdate, { passive: true });
window.addEventListener("resize", queueLineageScrollUpdate);

function watchLineageMediaQuery(query) {
  const listener = () => updateLineageFromScroll(true);
  if (typeof query.addEventListener === "function") query.addEventListener("change", listener);
  else if (typeof query.addListener === "function") query.addListener(listener);
}

watchLineageMediaQuery(lineageCompactQuery);
watchLineageMediaQuery(lineageReducedMotionQuery);
updateLineageFromScroll(true);

window.addEventListener("message", (event) => {
  if (
    event.origin !== window.location.origin ||
    event.source !== lineageFrame.contentWindow ||
    lineageFrame.hidden ||
    event.data?.type !== "paperroach:artifact-change"
  ) return;

  const node = lineageNodes.find((candidate) => candidate.dataset.lineageFile === event.data.path);
  if (!node) return;
  alignLineageStepWithNode(node);
  selectLineageArtifact(node);
});
