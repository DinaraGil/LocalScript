const API = "";
let currentSessionId = null;

const $ = (sel) => document.querySelector(sel);
const sessionList = $("#sessionList");
const messagesDiv = $("#messages");
const chatForm = $("#chatForm");
const userInput = $("#userInput");
const sendBtn = $("#sendBtn");
const newChatBtn = $("#newChatBtn");

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function renderMarkdown(text) {
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts
    .map((part) => {
      const m = part.match(/^```(\w*)\n?([\s\S]*?)```$/);
      if (m) {
        const lang = m[1] || "lua";
        const code = m[2].trim();
        let highlighted;
        try {
          highlighted = hljs.highlight(code, { language: lang }).value;
        } catch {
          highlighted = escapeHtml(code);
        }
        return `<pre><code class="hljs language-${lang}">${highlighted}</code><button class="copy-btn" onclick="copyCode(this)">Copy</button></pre>`;
      }
      return `<span>${escapeHtml(part)}</span>`;
    })
    .join("");
}

function copyCode(btn) {
  const code = btn.previousElementSibling.textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = "Copied!";
    setTimeout(() => (btn.textContent = "Copy"), 1500);
  });
}

function addMessage(role, content, luaCode, isValid) {
  const welcome = messagesDiv.querySelector(".welcome");
  if (welcome) welcome.remove();

  const div = document.createElement("div");
  div.className = `msg ${role}`;

  const label = role === "user" ? "You" : "Assistant";
  let html = `<div class="role-label">${label}</div>`;
  html += renderMarkdown(content);

  if (luaCode && isValid !== null) {
    const cls = isValid ? "valid" : "invalid";
    const txt = isValid ? "Syntax OK" : "Syntax Error";
    html += `<div class="validation-badge ${cls}">${txt}</div>`;
  }

  div.innerHTML = html;
  messagesDiv.appendChild(div);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function showLoading() {
  const div = document.createElement("div");
  div.className = "msg assistant";
  div.id = "loadingMsg";
  div.innerHTML =
    '<div class="role-label">Assistant</div><div class="loading"><span></span><span></span><span></span></div>';
  messagesDiv.appendChild(div);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function hideLoading() {
  const el = document.getElementById("loadingMsg");
  if (el) el.remove();
}

async function loadSessions() {
  try {
    const sessions = await api("GET", "/chat/sessions");
    sessionList.innerHTML = "";
    sessions.forEach((s) => {
      const div = document.createElement("div");
      div.className = `session-item${s.id === currentSessionId ? " active" : ""}`;
      div.textContent = s.title || "New Chat";
      div.onclick = () => selectSession(s.id);
      sessionList.appendChild(div);
    });
  } catch {
    /* ignore on first load */
  }
}

async function selectSession(id) {
  currentSessionId = id;
  messagesDiv.innerHTML = "";
  const msgs = await api("GET", `/chat/sessions/${id}/messages`);
  if (msgs.length === 0) {
    messagesDiv.innerHTML =
      '<div class="welcome"><h1>LocalScript</h1><p>AI-agent for Lua code generation</p><p class="hint">Describe your task in natural language (RU/EN)</p></div>';
  }
  msgs.forEach((m) => addMessage(m.role, m.content, m.lua_code, m.is_valid));
  await loadSessions();
}

async function createSession() {
  const data = await api("POST", "/chat/sessions");
  currentSessionId = data.id;
  messagesDiv.innerHTML =
    '<div class="welcome"><h1>LocalScript</h1><p>AI-agent for Lua code generation</p><p class="hint">Describe your task in natural language (RU/EN)</p></div>';
  await loadSessions();
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = userInput.value.trim();
  if (!text) return;

  if (!currentSessionId) await createSession();

  addMessage("user", text);
  userInput.value = "";
  sendBtn.disabled = true;
  showLoading();

  try {
    const resp = await api("POST", `/chat/sessions/${currentSessionId}/messages`, {
      content: text,
    });
    hideLoading();
    addMessage("assistant", resp.content, resp.lua_code, resp.is_valid);
    await loadSessions();
  } catch (err) {
    hideLoading();
    addMessage("assistant", `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    userInput.focus();
  }
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.dispatchEvent(new Event("submit"));
  }
});

newChatBtn.addEventListener("click", createSession);

loadSessions();
