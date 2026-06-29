// 工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务

const BACKEND_BASE_URL = "http://127.0.0.1:5057/api";

const state = {
  backendAvailable: false,
  waitingResponse: false,
  schedules: [],
  reminders: [],
};

const els = {
  backendStatus: document.querySelector("#backend-status"),
  activeCount: document.querySelector("#active-count"),
  reminderCount: document.querySelector("#reminder-count"),
  todayLabel: document.querySelector("#today-label"),
  chatLog: document.querySelector("#chat-log"),
  chatForm: document.querySelector("#chat-form"),
  chatInput: document.querySelector("#chat-input"),
  submitButton: document.querySelector("#submit-btn"),
  clearChatBtn: document.querySelector("#clear-chat-btn"),
  scheduleTableBody: document.querySelector("#schedule-table-body"),
  reminderFeed: document.querySelector("#reminder-feed"),
  messageTemplate: document.querySelector("#message-template"),
};

boot().catch((error) => {
  console.error(error);
  addMessage("system", `启动失败：${error?.message ?? "未知错误"}`);
});

async function boot() {
  bindEvents();
  const healthy = await checkBackendHealth();
  if (healthy) {
    await refreshDashboard();
  } else {
    renderScheduleTable();
    renderReminderFeed();
    addMessage("system", "⚠️ 后端服务未连接，请先启动服务：python desktop_agent.py");
  }
}

function bindEvents() {
  els.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.waitingResponse) return;
    const text = els.chatInput.value.trim();
    if (!text) return;
    els.chatInput.value = "";
    await handleUserInput(text);
  });

  els.clearChatBtn.addEventListener("click", () => {
    els.chatLog.innerHTML = "";
    addMessage("system", "对话已清空，您可以继续输入新的日程指令。");
  });

  document.querySelectorAll("[data-question]").forEach((button) => {
    button.addEventListener("click", async () => {
      const question = button.dataset.question;
      await handleUserInput(question);
    });
  });
}

async function checkBackendHealth() {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/health`);
    const data = await response.json();
    state.backendAvailable = response.ok;
    els.backendStatus.textContent = response.ok ? "✅ 已连接" : "❌ 未连接";
    els.activeCount.textContent = `${data.active_schedules ?? 0}`;
    els.reminderCount.textContent = `${data.reminder_logs ?? 0}`;
    els.todayLabel.textContent = data.today ?? "-";
    return response.ok;
  } catch (error) {
    state.backendAvailable = false;
    els.backendStatus.textContent = "❌ 未连接";
    els.activeCount.textContent = "-";
    els.reminderCount.textContent = "-";
    return false;
  }
}

async function refreshDashboard() {
  await Promise.all([loadSchedules(), loadReminders(), checkBackendHealth()]);
}

async function loadSchedules() {
  const response = await fetch(`${BACKEND_BASE_URL}/schedules`);
  const data = await response.json();
  state.schedules = Array.isArray(data.items) ? data.items : [];
  renderScheduleTable();
}

async function loadReminders() {
  const response = await fetch(`${BACKEND_BASE_URL}/reminders`);
  const data = await response.json();
  state.reminders = Array.isArray(data.items) ? data.items : [];
  renderReminderFeed();
}

async function handleUserInput(question) {
  addMessage("user", question);

  if (!state.backendAvailable) {
    addMessage("assistant", "⚠️ 后端服务未连接，请先启动服务：python desktop_agent.py");
    return;
  }

  setPendingState(true);
  const loadingId = addMessage("assistant", "正在处理您的日程指令，请稍候...");

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      replaceMessage(loadingId, "assistant", `❌ 请求失败：HTTP ${response.status}`);
      return;
    }

    const data = await response.json();
    replaceMessage(loadingId, "assistant", data.answer ?? "已处理。");
    await refreshDashboard();
  } catch (error) {
    replaceMessage(loadingId, "assistant", `❌ 请求失败：${error.message}`);
  } finally {
    setPendingState(false);
  }
}

function addMessage(role, text) {
  const clone = els.messageTemplate.content.cloneNode(true);
  const article = clone.querySelector(".message");
  article.dataset.role = role;
  article.dataset.messageId = crypto.randomUUID();

  const roleLabel = clone.querySelector(".message__role");
  roleLabel.textContent = role === "user" ? "您" : role === "assistant" ? "智能体" : "系统提示";

  const bubble = clone.querySelector(".message__bubble");
  bubble.textContent = text;

  els.chatLog.appendChild(clone);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
  return article.dataset.messageId;
}

function replaceMessage(messageId, role, text) {
  const article = els.chatLog.querySelector(`[data-message-id="${messageId}"]`);
  if (!article) {
    addMessage(role, text);
    return;
  }
  article.dataset.role = role;
  article.querySelector(".message__role").textContent = role === "user" ? "您" : role === "assistant" ? "智能体" : "系统提示";
  article.querySelector(".message__bubble").textContent = text;
}

function renderScheduleTable() {
  els.scheduleTableBody.innerHTML = "";
  if (!state.schedules.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="5">当前还没有日程。</td>';
    els.scheduleTableBody.appendChild(row);
    return;
  }

  for (const item of state.schedules) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.id}</td>
      <td>${item.time_label}</td>
      <td>${item.repeat_text}</td>
      <td>${item.content}</td>
      <td>${item.status}</td>
    `;
    els.scheduleTableBody.appendChild(row);
  }
}

function renderReminderFeed() {
  els.reminderFeed.innerHTML = "";
  if (!state.reminders.length) {
    els.reminderFeed.innerHTML = '<div class="reminder-item">暂时还没有提醒记录。</div>';
    return;
  }

  for (const item of state.reminders.slice(0, 8)) {
    const card = document.createElement("div");
    card.className = "reminder-item";
    card.innerHTML = `<strong>${item.triggered_at.replace("T", " ").slice(0, 16)}</strong><br>${item.message}`;
    els.reminderFeed.appendChild(card);
  }
}

function setPendingState(pending) {
  state.waitingResponse = pending;
  els.submitButton.disabled = pending;
  els.submitButton.textContent = pending ? "处理中..." : "发送";
  els.chatInput.disabled = pending;
}
