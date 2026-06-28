const API_BASE_URL = window.location.origin.startsWith("http")
  ? window.location.origin
  : "http://localhost:8000";

const form = document.querySelector("#scheduleForm");
const studentId = document.querySelector("#studentId");
const interests = document.querySelector("#interests");
const careerGoal = document.querySelector("#careerGoal");
const courseLoad = document.querySelector("#courseLoad");
const messages = document.querySelector("#messages");

function buildSchedulePrompt(values) {
  return [
    `Student ID: ${values.studentId}`,
    `Interests: ${values.interests}`,
    `Career goal: ${values.careerGoal}`,
    `Desired course load: ${values.courseLoad} courses`,
    "",
    "Generate a semester schedule recommendation from this intake.",
    "Use course prerequisites, professor review trends, and the available mock student/course data when helpful.",
    "Return a concise schedule with a short explanation for each course and mention any assumptions you made.",
  ].join("\n");
}

function clearMessages() {
  messages.innerHTML = "";
}

function addTrace(trace) {
  if (!trace || trace.length === 0) {
    return;
  }

  const details = document.createElement("details");
  details.className = "trace";

  const summary = document.createElement("summary");
  summary.textContent = `Trace (${trace.length} steps)`;
  details.appendChild(summary);

  const list = document.createElement("ol");
  for (const step of trace) {
    const item = document.createElement("li");
    const detailsText = JSON.stringify(step.details || {});
    item.textContent = `${step.agent} - ${step.event} ${detailsText}`;
    list.appendChild(item);
  }

  details.appendChild(list);
  messages.appendChild(details);
  messages.scrollTop = messages.scrollHeight;
}

function addResult(text) {
  const bubble = document.createElement("article");
  bubble.className = "message assistant";
  bubble.innerHTML = `<div class="markdown-content">${markdownToHtml(text)}</div>`;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

function markdownToHtml(text) {
  const normalized = normalizeMessageText(text);
  const lines = normalized.split("\n");
  const blocks = [];
  let paragraphLines = [];
  let listType = null;
  let listItems = [];
  let inCodeBlock = false;
  let codeLines = [];

  const flushParagraph = () => {
    if (paragraphLines.length === 0) {
      return;
    }

    blocks.push(`<p>${renderInlineMarkdown(paragraphLines.join(" "))}</p>`);
    paragraphLines = [];
  };

  const flushList = () => {
    if (listItems.length === 0) {
      listType = null;
      return;
    }

    const tagName = listType === "ol" ? "ol" : "ul";
    const itemsHtml = listItems
      .map((item) => `<li>${renderInlineMarkdown(item)}</li>`)
      .join("");
    blocks.push(`<${tagName}>${itemsHtml}</${tagName}>`);
    listItems = [];
    listType = null;
  };

  const flushCode = () => {
    if (codeLines.length === 0) {
      return;
    }

    blocks.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushList();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*+]\s+(.+)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType && listType !== "ul") {
        flushList();
      }
      listType = "ul";
      listItems.push(unorderedMatch[1]);
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType && listType !== "ol") {
        flushList();
      }
      listType = "ol";
      listItems.push(orderedMatch[1]);
      continue;
    }

    paragraphLines.push(trimmed);
  }

  flushParagraph();
  flushList();
  flushCode();

  return blocks.length > 0 ? blocks.join("") : `<p>${escapeHtml(normalized)}</p>`;
}

function normalizeMessageText(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function renderInlineMarkdown(text) {
  let rendered = escapeHtml(text);

  rendered = rendered.replace(/`([^`]+)`/g, "<code>$1</code>");
  rendered = rendered.replace(/\[(.+?)\]\((.+?)\)/g, (_, label, url) => {
    const safeUrl = sanitizeUrl(url);
    return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });
  rendered = rendered.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  rendered = rendered.replace(/(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)/g, "<em>$1</em>");

  return rendered;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function sanitizeUrl(url) {
  try {
    const parsed = new URL(url, window.location.origin);
    if (parsed.protocol === "http:" || parsed.protocol === "https:" || parsed.protocol === "mailto:") {
      return parsed.href;
    }
  } catch (_error) {
    // Fall through to a safe inert link.
  }

  return "#";
}

async function sendMessage(message) {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      student_id: studentId.value,
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  return response.json();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const values = {
    studentId: studentId.value,
    interests: interests.value.trim(),
    careerGoal: careerGoal.value.trim(),
    courseLoad: courseLoad.value,
  };

  if (!values.interests || !values.careerGoal || !values.courseLoad) {
    return;
  }

  const message = buildSchedulePrompt(values);
  clearMessages();
  form.querySelector("button").disabled = true;

  try {
    const data = await sendMessage(message);
    addResult(data.reply);
    addTrace(data.trace);
  } catch (error) {
    addResult(
      "The API is not reachable yet. Start FastAPI with uvicorn backend.main:app --reload."
    );
  } finally {
    form.querySelector("button").disabled = false;
    interests.focus();
  }
});
