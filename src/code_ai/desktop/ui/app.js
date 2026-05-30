const api = () => window.pywebview.api;
let APPS = [];
let curApp = null;

async function init() {
  APPS = await api().list_apps();
  renderApps();
  await loadSettings();
}

function findApp(id) { return APPS.find((x) => x.id === id); }

function renderApps() {
  const grid = document.getElementById("apps");
  grid.innerHTML = "";
  for (const a of APPS) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      `<button class="cfg" title="专有设置">⚙</button>` +
      `<div class="title">${a.display}</div>` +
      `<div class="status" id="status-${a.id}"></div>` +
      `<button class="action" id="btn-${a.id}"></button>`;
    grid.appendChild(card);
    updateCard(a.id, a.found, a.running);
    document.getElementById(`btn-${a.id}`).onclick = () => onAction(a.id);
    card.querySelector(".cfg").onclick = () => openAppSettings(a.id);
  }
}

function updateCard(id, found, running) {
  const a = findApp(id);
  if (a) { a.found = found; a.running = running; }
  const s = document.getElementById(`status-${id}`);
  const b = document.getElementById(`btn-${id}`);
  if (!s || !b) return;
  if (!found) {
    s.textContent = "⚠ 未检测到"; s.className = "status warn";
    b.textContent = "配置路径"; b.dataset.mode = "config";
  } else if (running) {
    s.textContent = "● 运行中"; s.className = "status on";
    b.textContent = "中止"; b.dataset.mode = "stop";
  } else {
    s.textContent = "○ 已停止"; s.className = "status off";
    b.textContent = "启动"; b.dataset.mode = "launch";
  }
}

async function onAction(id) {
  const mode = document.getElementById(`btn-${id}`).dataset.mode;
  if (mode === "config") {
    const r = await api().pick_app_path(id);
    if (r && r.ok) await refresh();
    return;
  }
  if (mode === "launch") {
    const r = await api().launch_app(id);
    if (!r.ok) toast(r.error);
  } else if (mode === "stop") {
    const r = await api().stop_app(id);
    if (!r.ok) toast(r.error);
  }
  await refresh();
}

async function refresh() {
  APPS = await api().list_apps();
  for (const a of APPS) updateCard(a.id, a.found, a.running);
}

window.updateStatus = (map) => {
  for (const id in map) {
    const a = findApp(id);
    if (a) updateCard(id, a.found, map[id]);
  }
};

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3000);
}

// ---- settings ----
async function loadSettings() {
  const s = await api().get_settings();
  document.getElementById("proxy").checked = !!s.check_system_proxy;
  renderEnv("common-env", s.env_vars);
}

function renderEnv(containerId, vars) {
  const c = document.getElementById(containerId);
  c.innerHTML = "";
  for (const [k, v] of Object.entries(vars || {})) addEnvRow(containerId, k, v);
}

function addEnvRow(containerId, k = "", v = "") {
  const c = document.getElementById(containerId);
  const row = document.createElement("div");
  row.className = "env-row";
  row.innerHTML =
    `<input class="k" placeholder="KEY" value="${k}">` +
    `<span>=</span>` +
    `<input class="v" placeholder="VALUE" value="${v}">` +
    `<button class="del">×</button>`;
  row.querySelector(".del").onclick = () => row.remove();
  c.appendChild(row);
}

function collectEnv(containerId) {
  const out = {};
  for (const row of document.querySelectorAll(`#${containerId} .env-row`)) {
    const k = row.querySelector(".k").value.trim();
    const v = row.querySelector(".v").value;
    if (k) out[k] = v;
  }
  return out;
}

async function saveSettings() {
  await api().save_settings({
    check_system_proxy: document.getElementById("proxy").checked,
    env_vars: collectEnv("common-env"),
  });
  toast("已保存");
}

// ---- per-app modal ----
async function openAppSettings(id) {
  curApp = id;
  const s = await api().get_app_settings(id);
  document.getElementById("app-modal-title").textContent =
    `${findApp(id).display} 专有设置`;
  document.getElementById("app-path").textContent = s.path || "(自动检测)";
  renderEnv("app-env", s.env_vars);
  document.getElementById("app-modal").classList.add("show");
}

async function saveAppSettings() {
  await api().save_app_settings(curApp, { env_vars: collectEnv("app-env") });
  document.getElementById("app-modal").classList.remove("show");
  toast("已保存");
}

async function pickPath() {
  const r = await api().pick_app_path(curApp);
  if (r && r.ok) {
    document.getElementById("app-path").textContent = r.path;
    await refresh();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("toggle-settings").onclick = () => {
    const p = document.getElementById("settings-panel");
    p.style.display = p.style.display === "none" ? "block" : "none";
  };
  document.getElementById("add-common").onclick = () => addEnvRow("common-env");
  document.getElementById("save-settings").onclick = saveSettings;
  document.getElementById("add-app-env").onclick = () => addEnvRow("app-env");
  document.getElementById("save-app").onclick = saveAppSettings;
  document.getElementById("pick-path").onclick = pickPath;
  document.getElementById("close-app").onclick = () =>
    document.getElementById("app-modal").classList.remove("show");
});

window.addEventListener("pywebviewready", init);
