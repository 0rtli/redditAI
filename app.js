const form = document.getElementById("research-form");
const summary = document.getElementById("summary");
const notice = document.getElementById("notice");
const statusBadge = document.getElementById("run-status");
const sampleSize = document.getElementById("sample-size");
const sourceCount = document.getElementById("source-count");
const sources = document.getElementById("sources");
const button = form.querySelector("button[type='submit']");
const rememberKey = document.getElementById("remember-key");
const clearSavedKeyButton = document.getElementById("clear-saved-key");
const copyReportButton = document.getElementById("copy-report");
const progressPanel = document.getElementById("progress-panel");
const progressTitle = document.getElementById("progress-title");
const progressStepCount = document.getElementById("progress-step-count");
const progressBar = document.getElementById("progress-bar");
const progressMessage = document.getElementById("progress-message");
const OPENAI_KEY_STORAGE_KEY = "redditOpportunityAgent.openaiKey";
let progressInterval = null;
let progressTimerStartedAt = null;
let latestReportText = "";

hydrateSavedKey();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    apiKey: form.apiKey.value.trim(),
    topic: form.topic.value.trim(),
    subreddit: form.subreddit.value.trim(),
    model: form.model.value.trim(),
    outputLanguage: form.outputLanguage.value.trim() || "English",
    limit: Number(form.limit.value),
    commentsPerPost: Number(form.commentsPerPost.value),
    time: form.time.value,
    sort: form.sort.value,
    useAi: form.useAi.checked,
    discoveryMode: form.discoveryMode.checked,
  };

  if (!payload.topic) {
    showNotice("Please enter a topic to research.");
    return;
  }

  persistKeyPreference();

  setLoading(true);
  clearResults();

  try {
    const response = await fetch("/api/research", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Request failed.");
    }

    latestReportText = result.summary || "";
    renderSummary(result.summary);
    renderSources(result.posts || []);
    sampleSize.textContent = `${result.sampleSize} posts reviewed`;

    if (result.aiNotice) {
      showNotice(`AI summary unavailable, fallback used instead: ${result.aiNotice}`);
    } else if (!payload.useAi && payload.outputLanguage.toLowerCase() !== "english") {
      showNotice("Chosen report language needs OpenAI analysis. Local fallback report stayed in English.");
    } else if (result.discoveryMode) {
      showNotice(`Broad search mode used ${result.discoveryQueries.length} sub-queries and merged the most relevant Reddit findings.`);
    } else if (result.analysisMode === "opportunity") {
      showNotice("Business-focused prompt detected, so the report was ranked with the investor scoring model.");
    } else {
      hideNotice();
    }
  } catch (error) {
    showNotice(error.message || "Something went wrong.");
    summary.classList.add("empty-state");
    summary.textContent = "The request failed. Fix the issue above and try again.";
    sampleSize.textContent = "No research yet";
    sourceCount.textContent = "0 posts";
  } finally {
    setLoading(false);
  }
});

form.apiKey.addEventListener("input", () => {
  if (rememberKey.checked) {
    localStorage.setItem(OPENAI_KEY_STORAGE_KEY, form.apiKey.value);
  }
});

rememberKey.addEventListener("change", () => {
  persistKeyPreference();
});

clearSavedKeyButton.addEventListener("click", () => {
  localStorage.removeItem(OPENAI_KEY_STORAGE_KEY);
  form.apiKey.value = "";
  rememberKey.checked = false;
  showNotice("Saved API key cleared from this browser.");
});

copyReportButton.addEventListener("click", async () => {
  if (!latestReportText.trim()) {
    showNotice("There is no report to copy yet.");
    return;
  }

  try {
    await navigator.clipboard.writeText(latestReportText);
    showNotice("Report copied to clipboard.");
  } catch (error) {
    showNotice("Could not copy automatically. Your browser may have blocked clipboard access.");
  }
});

function setLoading(isLoading) {
  statusBadge.textContent = isLoading ? "Researching..." : "Idle";
  button.disabled = isLoading;
  button.textContent = isLoading ? "Working..." : "Run Research";
  copyReportButton.disabled = isLoading;
  if (isLoading) {
    startProgress();
  } else {
    stopProgress();
  }
}

function clearResults() {
  hideNotice();
  summary.classList.remove("empty-state");
  summary.innerHTML = "<p>Searching Reddit, reviewing posts and comments, and assembling the report...</p>";
  sampleSize.textContent = "Research in progress";
  sourceCount.textContent = "0 posts";
  sources.innerHTML = "";
  latestReportText = "";
}

function renderSummary(markdownText) {
  summary.classList.remove("empty-state");
  summary.innerHTML = renderMarkdownLite(markdownText);
}

function renderSources(posts) {
  sourceCount.textContent = `${posts.length} posts`;
  sources.innerHTML = "";

  posts.forEach((post) => {
    const link = document.createElement("a");
    link.className = "source-card";
    link.href = post.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.innerHTML = `
      <strong>${escapeHtml(post.title)}</strong>
      <div class="source-meta">r/${escapeHtml(post.subreddit)} • score ${post.score} • ${post.num_comments} comments</div>
    `;
    sources.appendChild(link);
  });
}

function showNotice(message) {
  notice.textContent = message;
  notice.classList.remove("hidden");
}

function hideNotice() {
  notice.classList.add("hidden");
  notice.textContent = "";
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function hydrateSavedKey() {
  const savedKey = localStorage.getItem(OPENAI_KEY_STORAGE_KEY);
  if (savedKey) {
    form.apiKey.value = savedKey;
    rememberKey.checked = true;
  }
}

function persistKeyPreference() {
  if (rememberKey.checked && form.apiKey.value.trim()) {
    localStorage.setItem(OPENAI_KEY_STORAGE_KEY, form.apiKey.value);
    return;
  }
  localStorage.removeItem(OPENAI_KEY_STORAGE_KEY);
}

function startProgress() {
  progressTimerStartedAt = Date.now();
  progressPanel.classList.remove("hidden");
  updateProgress();
  progressInterval = window.setInterval(updateProgress, 900);
}

function stopProgress() {
  if (progressInterval) {
    window.clearInterval(progressInterval);
    progressInterval = null;
  }
  progressPanel.classList.add("hidden");
}

function updateProgress() {
  const elapsedSeconds = Math.floor((Date.now() - progressTimerStartedAt) / 1000);
  const likelyOpportunityMode = isOpportunityPrompt(form.topic.value);
  const steps = form.discoveryMode.checked
    ? [
        "Generating broader Reddit sub-queries...",
        "Searching Reddit across multiple angles...",
        "Reviewing posts and comments...",
        likelyOpportunityMode ? "Scoring stronger opportunities..." : "Grouping repeated patterns...",
        "Writing the final report...",
      ]
    : [
        "Searching Reddit...",
        "Reviewing posts and comments...",
        "Extracting repeated themes...",
        likelyOpportunityMode ? "Ranking the strongest business signals..." : "Organizing the strongest evidence...",
        "Writing the final report...",
      ];

  const stepIndex = Math.min(steps.length - 1, Math.floor(elapsedSeconds / 3));
  const progressPercent = Math.min(92, 12 + stepIndex * 18 + (elapsedSeconds % 3) * 4);

  progressTitle.textContent = form.discoveryMode.checked
    ? "Broad search mode is expanding the search"
    : likelyOpportunityMode
      ? "Researching business signals"
      : "Research in progress";
  progressStepCount.textContent = `Step ${stepIndex + 1} of ${steps.length}`;
  progressBar.style.width = `${progressPercent}%`;
  progressMessage.textContent = steps[stepIndex];
}

function isOpportunityPrompt(topic) {
  const lowered = topic.toLowerCase();
  const markers = [
    "monetizable",
    "profitable",
    "opportunity",
    "browser extension ideas",
    "chrome extension ideas",
    "small saas ideas",
    "startup",
    "business idea",
    "pricing",
    "revenue",
    "mrr",
  ];
  return markers.some((marker) => lowered.includes(marker));
}

function renderMarkdownLite(markdownText) {
  const lines = markdownText.split("\n");
  let html = "";
  let inList = false;

  const closeList = () => {
    if (inList) {
      html += "</ul>";
      inList = false;
    }
  };

  lines.forEach((rawLine) => {
    const line = rawLine.trim();

    if (!line) {
      closeList();
      return;
    }

    if (line.startsWith("# ")) {
      closeList();
      html += `<h3>${formatInline(line.slice(2))}</h3>`;
      return;
    }

    if (line.startsWith("- ")) {
      if (!inList) {
        html += "<ul>";
        inList = true;
      }
      html += `<li>${formatInline(line.slice(2))}</li>`;
      return;
    }

    closeList();
    html += `<p>${formatInline(line)}</p>`;
  });

  closeList();
  return html;
}

function formatInline(text) {
  let value = escapeHtml(text);
  value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
  value = value.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return value;
}
