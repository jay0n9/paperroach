(() => {
  "use strict";

  const DEFAULT_DOCUMENT = "processed/paper-note.md";
  const documents = [
    ["processed/paper-note.md", "Source-checked paper note", "reviewed", "Reviewed"],
    ["processed/paper-note.generated.md", "Actual generated paper note", "generated", "Generated"],
    ["derivatives/affective-dynamics-model.md", "Affective Dynamics Model", "reviewed", "Reviewed"],
    ["derivatives/affective-dynamics-model.generated.md", "Affective Dynamics Model — generated", "generated", "Generated"],
    ["derivatives/exponential-relaxation.md", "Exponential Relaxation", "reviewed", "Reviewed"],
    ["derivatives/exponential-relaxation.generated.md", "Exponential Relaxation — generated", "generated", "Generated"],
    ["derivatives/individual-baseline.md", "Individual Baseline", "reviewed", "Reviewed"],
    ["derivatives/individual-baseline.generated.md", "Individual Baseline — generated", "generated", "Generated"],
    ["derivatives/regulation-effect.md", "Regulation Effect", "reviewed", "Reviewed"],
    ["derivatives/regulation-effect.generated.md", "Regulation Effect — generated", "generated", "Generated"],
    ["ATTRIBUTION.md", "Attribution and licenses", "provenance", "Provenance"],
    ["CHANGELOG.md", "Public review change log", "provenance", "Provenance"],
    ["README.md", "Case bundle README", "provenance", "Provenance"]
  ].map(([path, label, state, stateLabel]) => ({ path, label, state, stateLabel }));

  const documentByPath = new Map(documents.map((document) => [document.path, document]));
  const wikiTargets = new Map([
    ["affective dynamics model", "derivatives/affective-dynamics-model.md"],
    ["exponential relaxation", "derivatives/exponential-relaxation.md"],
    ["individual baseline", "derivatives/individual-baseline.md"],
    ["regulation effect", "derivatives/regulation-effect.md"],
    ["the individual dynamics of affective expression on social media", DEFAULT_DOCUMENT],
    ["the individual dynamics of affective expression on social media (2020)", DEFAULT_DOCUMENT]
  ]);

  const picker = document.querySelector("#mdv-document-select");
  const article = document.querySelector("#markdown-document");
  const status = document.querySelector("#mdv-status");
  const stateBadge = document.querySelector("#mdv-state");
  const rawLink = document.querySelector("#mdv-raw-link");
  const pathLabel = document.querySelector("#mdv-path");
  const baseUrl = new URL("./", window.location.href);
  const embedded = document.documentElement.dataset.embed === "true";
  const cache = new Map();
  let activeController = null;
  let currentPath = null;

  if (!picker || !article || !window.markdownit || !window.DOMPurify || !window.katex) {
    showFatalError("The Markdown viewer could not start.", DEFAULT_DOCUMENT);
    return;
  }

  const markdown = window.markdownit({
    html: false,
    linkify: true,
    breaks: false,
    typographer: false
  });

  function splitFrontmatter(source) {
    const normalized = source.replace(/^[\u200B-\u200F\uFEFF]/, "").replace(/\r\n?/g, "\n");
    const lines = normalized.split("\n");
    if (lines[0]?.trim() !== "---") return { frontmatter: "", body: normalized };
    const closingIndex = lines.findIndex((line, index) => index > 0 && line.trim() === "---");
    if (closingIndex < 0) return { frontmatter: "", body: normalized };
    return {
      frontmatter: lines.slice(1, closingIndex).join("\n").trim(),
      body: lines.slice(closingIndex + 1).join("\n").replace(/^\s+/, "")
    };
  }

  function preprocess(body) {
    const mathTokens = [];
    const wikiTokens = [];
    let output = body.replace(/%%[\s\S]*?%%/g, "");

    output = output.replace(/\$\$([\s\S]*?)\$\$/g, (_match, expression) => {
      const index = mathTokens.push({ expression: expression.trim(), display: true }) - 1;
      return `\n\nPRMATHBLOCKTOKEN${index}X\n\n`;
    });

    output = output.replace(/(^|[^\\$])\$([^$\n]+?)\$/g, (_match, prefix, expression) => {
      const index = mathTokens.push({ expression: expression.trim(), display: false }) - 1;
      return `${prefix}PRMATHINLINETOKEN${index}X`;
    });

    output = output.replace(/\[\[([^\]|\n]+?)(?:\|([^\]\n]+?))?\]\]/g, (_match, target, alias) => {
      const label = (alias || target).trim();
      const resolved = wikiTargets.get(target.trim().toLowerCase());
      if (resolved) {
        const safeLabel = label.replace(/([\\\[\]])/g, "\\$1");
        return `[${safeLabel}](?file=${encodeURIComponent(resolved)})`;
      }
      const index = wikiTokens.push(label) - 1;
      return `PRWIKILINKTOKEN${index}X`;
    });

    return { output, mathTokens, wikiTokens };
  }

  function createFrontmatter(raw) {
    if (!raw) return null;
    const details = document.createElement("details");
    details.className = "mdv-frontmatter";
    const summary = document.createElement("summary");
    summary.textContent = "Document metadata";
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = raw;
    pre.append(code);
    details.append(summary, pre);
    return details;
  }

  function createMath(expression, display) {
    const element = document.createElement(display ? "div" : "span");
    element.className = display ? "mdv-math-block" : "mdv-math-inline";
    try {
      window.katex.render(expression, element, {
        displayMode: display,
        throwOnError: false,
        strict: "ignore",
        trust: false,
        output: "htmlAndMathml"
      });
    } catch {
      element.classList.add("mdv-math-error");
      element.textContent = display ? `$$\n${expression}\n$$` : `$${expression}$`;
    }
    return element;
  }

  function hydrateTokens(mathTokens, wikiTokens) {
    article.querySelectorAll("p").forEach((paragraph) => {
      const match = paragraph.textContent.trim().match(/^PRMATHBLOCKTOKEN(\d+)X$/);
      if (!match) return;
      const token = mathTokens[Number(match[1])];
      if (token) paragraph.replaceWith(createMath(token.expression, true));
    });

    const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!/PR(?:MATHINLINE|WIKILINK)TOKEN\d+X/.test(node.nodeValue || "")) {
          return NodeFilter.FILTER_REJECT;
        }
        return node.parentElement?.closest("pre, code")
          ? NodeFilter.FILTER_REJECT
          : NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    const pattern = /PR(MATHINLINE|WIKILINK)TOKEN(\d+)X/g;
    nodes.forEach((node) => {
      const value = node.nodeValue || "";
      const fragment = document.createDocumentFragment();
      let cursor = 0;
      let match;
      pattern.lastIndex = 0;
      while ((match = pattern.exec(value))) {
        fragment.append(document.createTextNode(value.slice(cursor, match.index)));
        const index = Number(match[2]);
        if (match[1] === "MATHINLINE" && mathTokens[index]) {
          fragment.append(createMath(mathTokens[index].expression, false));
        } else if (match[1] === "WIKILINK" && wikiTokens[index]) {
          const span = document.createElement("span");
          span.className = "mdv-wikilink";
          span.setAttribute("aria-label", "Unresolved wiki link");
          span.textContent = wikiTokens[index];
          fragment.append(span);
        } else {
          fragment.append(document.createTextNode(match[0]));
        }
        cursor = match.index + match[0].length;
      }
      fragment.append(document.createTextNode(value.slice(cursor)));
      node.replaceWith(fragment);
    });
  }

  function transformCallouts() {
    const labels = { note: "Note", info: "Info", warning: "Unreviewed output" };
    article.querySelectorAll("blockquote").forEach((blockquote) => {
      const firstParagraph = blockquote.querySelector(":scope > p:first-child");
      const firstText = firstParagraph?.firstChild;
      if (!firstParagraph || !firstText || firstText.nodeType !== Node.TEXT_NODE) return;
      const match = firstText.nodeValue.match(/^\[!(note|info|warning)\]\s*/i);
      if (!match) return;
      const type = match[1].toLowerCase();
      firstText.nodeValue = firstText.nodeValue.slice(match[0].length);
      blockquote.classList.add("mdv-callout", `mdv-callout-${type}`);
      blockquote.setAttribute("role", "note");
      const label = document.createElement("div");
      label.className = "mdv-callout-label";
      label.textContent = labels[type];
      blockquote.prepend(label);
      if (!firstParagraph.textContent.trim()) firstParagraph.remove();
    });
  }

  function addHeadingIds() {
    const used = new Set();
    article.querySelectorAll("h1, h2, h3, h4, h5, h6").forEach((heading) => {
      const base = heading.textContent
        .normalize("NFKD")
        .toLowerCase()
        .replace(/[^\p{Letter}\p{Number}]+/gu, "-")
        .replace(/^-|-$/g, "") || "section";
      let slug = base;
      let index = 2;
      while (used.has(slug)) {
        slug = `${base}-${index}`;
        index += 1;
      }
      used.add(slug);
      heading.id = slug;
    });
  }

  function viewerUrl(path, hash = "") {
    const url = new URL("markdown-viewer.html", baseUrl);
    url.searchParams.set("file", path);
    if (embedded) url.searchParams.set("embed", "1");
    url.hash = hash;
    return url;
  }

  function relativeCasePath(url) {
    if (url.origin !== baseUrl.origin || !url.pathname.startsWith(baseUrl.pathname)) return null;
    try {
      return decodeURIComponent(url.pathname.slice(baseUrl.pathname.length));
    } catch {
      return null;
    }
  }

  function scrollToHash(hash) {
    if (!hash) return;
    let id;
    try {
      id = decodeURIComponent(hash.slice(1));
    } catch {
      return;
    }
    if (!id) return;
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView());
  }

  function rebaseLinks(activeDocument) {
    const sourceUrl = new URL(activeDocument.path, baseUrl);
    article.querySelectorAll("a[href]").forEach((link) => {
      const rawHref = link.getAttribute("href");
      if (!rawHref || rawHref.startsWith("#")) return;

      if (rawHref.startsWith("?file=")) {
        const targetUrl = new URL(rawHref, baseUrl);
        const targetPath = targetUrl.searchParams.get("file");
        if (targetPath && documentByPath.has(targetPath)) {
          link.href = viewerUrl(targetPath, targetUrl.hash);
          link.dataset.viewerFile = targetPath;
        }
        return;
      }

      let resolved;
      try {
        resolved = new URL(rawHref, sourceUrl);
      } catch {
        return;
      }

      const localPath = relativeCasePath(resolved);
      if (localPath && documentByPath.has(localPath)) {
        link.href = viewerUrl(localPath, resolved.hash);
        link.dataset.viewerFile = localPath;
        return;
      }

      link.href = resolved.href;
      if (resolved.origin !== window.location.origin) link.rel = "noopener noreferrer";
    });
  }

  function finish(activeDocument, source) {
    const { frontmatter, body } = splitFrontmatter(source);
    const { output, mathTokens, wikiTokens } = preprocess(body);
    const rendered = markdown.render(output);
    const sanitized = window.DOMPurify.sanitize(rendered, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ["style", "script", "iframe", "object", "embed"]
    });

    article.innerHTML = sanitized;
    const metadata = createFrontmatter(frontmatter);
    if (metadata) article.prepend(metadata);
    hydrateTokens(mathTokens, wikiTokens);
    transformCallouts();
    addHeadingIds();
    rebaseLinks(activeDocument);
    article.querySelectorAll("pre > code.language-mermaid").forEach((code) => {
      code.parentElement?.classList.add("mdv-mermaid-source");
    });

    article.setAttribute("aria-busy", "false");
    document.body.dataset.documentState = activeDocument.state;
    stateBadge.textContent = activeDocument.stateLabel;
    pathLabel.textContent = activeDocument.path;
    rawLink.href = activeDocument.path;
    picker.value = activeDocument.path;
    document.title = `${activeDocument.label} — PaperRoach Markdown viewer`;
    status.textContent = `Rendered ${activeDocument.path} · ${new TextEncoder().encode(source).byteLength.toLocaleString("en-US")} bytes`;
  }

  function showLoading(activeDocument) {
    article.setAttribute("aria-busy", "true");
    article.innerHTML = `<div class="mdv-loading"><span></span><span></span><span></span><p>Loading ${activeDocument.path}…</p></div>`;
    pathLabel.textContent = activeDocument.path;
    status.textContent = "Loading Markdown…";
  }

  function showError(activeDocument) {
    article.setAttribute("aria-busy", "false");
    article.replaceChildren();
    const container = document.createElement("div");
    container.className = "mdv-error";
    const heading = document.createElement("h1");
    heading.textContent = "This Markdown file could not be loaded.";
    const paragraph = document.createElement("p");
    paragraph.textContent = "The original file is still available directly.";
    const link = document.createElement("a");
    link.href = activeDocument.path;
    link.textContent = "Open the raw .md";
    container.append(heading, paragraph, link);
    article.append(container);
    status.textContent = `Failed to load ${activeDocument.path}`;
  }

  function showFatalError(message, fallbackPath) {
    if (!article) return;
    article.setAttribute("aria-busy", "false");
    article.replaceChildren();
    const container = document.createElement("div");
    container.className = "mdv-error";
    const heading = document.createElement("h1");
    heading.textContent = message;
    const link = document.createElement("a");
    link.href = fallbackPath;
    link.textContent = "Open the raw Markdown";
    container.append(heading, link);
    article.append(container);
  }

  async function getSource(path, signal) {
    if (cache.has(path)) return cache.get(path);
    const response = await fetch(path, { signal });
    if (!response.ok) throw new Error(`Markdown request failed: ${response.status}`);
    const source = await response.text();
    cache.set(path, source);
    return source;
  }

  async function load(path, options = {}) {
    const activeDocument = documentByPath.get(path) || documentByPath.get(DEFAULT_DOCUMENT);
    const historyMode = options.history || "none";
    const targetHash = options.hash || "";

    activeController?.abort();
    activeController = new AbortController();
    currentPath = activeDocument.path;
    showLoading(activeDocument);

    if (historyMode !== "none") {
      const url = viewerUrl(activeDocument.path, targetHash);
      window.history[historyMode === "replace" ? "replaceState" : "pushState"](
        { file: activeDocument.path },
        "",
        url
      );
    }

    try {
      const source = await getSource(activeDocument.path, activeController.signal);
      if (currentPath !== activeDocument.path) return;
      finish(activeDocument, source);
      if (targetHash) {
        scrollToHash(targetHash);
      } else if (options.scroll && !embedded) {
        window.scrollTo({ top: 0, behavior: "auto" });
      }
    } catch (error) {
      if (error.name !== "AbortError") showError(activeDocument);
    }
  }

  picker.addEventListener("change", () => {
    load(picker.value, { history: "push", scroll: true });
  });

  article.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-viewer-file]");
    if (!link) return;
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      link.target ||
      link.hasAttribute("download")
    ) return;
    const path = link.dataset.viewerFile;
    if (!documentByPath.has(path)) return;
    event.preventDefault();
    const hash = new URL(link.href).hash;
    load(path, { history: "push", hash, scroll: !hash });
  });

  window.addEventListener("popstate", () => {
    const url = new URL(window.location.href);
    load(url.searchParams.get("file") || DEFAULT_DOCUMENT, { history: "none", hash: url.hash });
  });

  const initialUrl = new URL(window.location.href);
  const requested = initialUrl.searchParams.get("file") || DEFAULT_DOCUMENT;
  const initialPath = documentByPath.has(requested) ? requested : DEFAULT_DOCUMENT;
  if (requested !== initialPath) {
    window.history.replaceState({ file: initialPath }, "", viewerUrl(initialPath, initialUrl.hash));
  }
  load(initialPath, { history: "none", hash: initialUrl.hash });
})();
