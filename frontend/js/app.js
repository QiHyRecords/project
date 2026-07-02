const token = localStorage.getItem("aas_token");
const role = localStorage.getItem("aas_role");
const username = localStorage.getItem("aas_username");

if (!token) {
  window.location.href = "/login.html";
}

document.getElementById("user-label").textContent = `${username} (${role})`;
document.getElementById("logout-btn").addEventListener("click", () => {
  localStorage.clear();
  window.location.href = "/login.html";
});

function authHeaders(extra = {}) {
  return { Authorization: `Bearer ${token}`, ...extra };
}

let uploadedFilename = null;

// ---- Dashboard (chỉ admin) ----
async function loadDashboard() {
  if (role !== "admin") return;
  const panel = document.getElementById("stats-panel");
  panel.hidden = false;
  try {
    const res = await fetch("/api/admin/dashboard", { headers: authHeaders() });
    if (!res.ok) return;
    const stats = await res.json();
    const grid = document.getElementById("stats-grid");
    grid.innerHTML = "";
    const items = [
      ["CPU", `${stats.cpu_percent}%`],
      ["RAM", `${stats.ram_percent}% (${stats.ram_used_gb}/${stats.ram_total_gb} GB)`],
      ["Ổ đĩa", `${stats.disk_percent}% (${stats.disk_used_gb}/${stats.disk_total_gb} GB)`],
      ["Model đã cài", stats.models_installed],
      ["Job đang chạy", stats.jobs_running],
      ["Job hoàn thành", stats.jobs_completed],
    ];
    for (const [label, value] of items) {
      const box = document.createElement("div");
      box.className = "stat-box";
      box.innerHTML = `<div class="value">${value}</div><div class="label">${label}</div>`;
      grid.appendChild(box);
    }
  } catch (e) { /* im lặng nếu lỗi mạng thoáng qua */ }
}
loadDashboard();

// ---- Danh sách model tách vocal (không hardcode, lấy từ Model Manager) ----
async function loadSeparationModels() {
  const select = document.getElementById("separator-model");
  const btn = document.getElementById("btn-separate");
  try {
    const res = await fetch("/api/models/vocal-separation", { headers: authHeaders() });
    const models = res.ok ? await res.json() : [];
    select.innerHTML = "";
    if (models.length === 0) {
      select.innerHTML = `<option value="">Chưa có model nào được cài</option>`;
      btn.disabled = true;
      return;
    }
    for (const m of models) {
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = m.name;
      select.appendChild(opt);
    }
    btn.disabled = false;
  } catch (e) {
    select.innerHTML = `<option value="">Lỗi tải danh sách model</option>`;
    btn.disabled = true;
  }
}
loadSeparationModels();

// ---- Upload (drag & drop + progress) ----
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");
const uploadResult = document.getElementById("upload-result");
const actionPanel = document.getElementById("action-panel");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFile(fileInput.files[0]);
});

function uploadFile(file) {
  uploadResult.textContent = "";
  progressWrap.hidden = false;
  progressBar.style.width = "0%";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");
  xhr.setRequestHeader("Authorization", `Bearer ${token}`);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      progressBar.style.width = `${Math.round((e.loaded / e.total) * 100)}%`;
    }
  };
  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      const data = JSON.parse(xhr.responseText);
      uploadedFilename = data.filename;
      uploadResult.textContent = `Đã upload: ${data.filename}`;
      actionPanel.hidden = false;
    } else {
      uploadResult.textContent = "Upload thất bại";
    }
  };
  xhr.onerror = () => { uploadResult.textContent = "Lỗi kết nối khi upload"; };

  const formData = new FormData();
  formData.append("file", file);
  xhr.send(formData);
}

// ---- Analyze / Separate ----
const jobPanel = document.getElementById("job-panel");
const jobStatus = document.getElementById("job-status");
const jobResult = document.getElementById("job-result");

document.getElementById("btn-analyze").addEventListener("click", async () => {
  if (!uploadedFilename) return;
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ filename: uploadedFilename }),
  });
  const data = await res.json();
  if (res.ok) pollJob(data.job_id);
  else jobStatusText(`Lỗi: ${data.detail}`);
});

document.getElementById("btn-separate").addEventListener("click", async () => {
  if (!uploadedFilename) return;
  const model = document.getElementById("separator-model").value;
  const res = await fetch("/api/separate", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ filename: uploadedFilename, model }),
  });
  const data = await res.json();
  if (res.ok) pollJob(data.job_id);
  else jobStatusText(`Lỗi: ${data.detail}`);
});

function jobStatusText(text) {
  jobPanel.hidden = false;
  jobStatus.textContent = text;
}

async function pollJob(jobId) {
  jobPanel.hidden = false;
  jobResult.innerHTML = "";
  const interval = setInterval(async () => {
    const res = await fetch(`/api/job/${jobId}`, { headers: authHeaders() });
    if (!res.ok) { clearInterval(interval); return; }
    const job = await res.json();
    jobStatus.textContent = `Trạng thái: ${job.status} — ${job.progress}%`;
    if (job.status === "done") {
      clearInterval(interval);
      showResult(job);
    } else if (job.status === "failed") {
      clearInterval(interval);
      jobStatus.textContent = `Job thất bại: ${job.error}`;
    }
  }, 1500);
}

function showResult(job) {
  jobResult.innerHTML = "";

  if (job.job_type === "analyze" && job.result?.summary) {
    const s = job.result.summary;
    const p = document.createElement("p");
    p.textContent = `BPM: ${s.bpm} | Key: ${s.key} ${s.mode} | Duration: ${s.duration}s`;
    jobResult.appendChild(p);
    addDownloadLink(job.id, "json", "Tải kết quả JSON");
    addDownloadLink(job.id, "txt", "Tải timeline TXT");
    return;
  }

  if (job.job_type === "separate" && job.result) {
    const labels = { vocal: "Vocal", instrumental: "Instrumental", bass: "Bass", drums: "Drums", other: "Other" };
    for (const key of Object.keys(job.result)) {
      const stem = key.replace("_path", "");
      if (!labels[stem]) continue;
      addDownloadLink(job.id, stem, `Tải ${labels[stem]}.wav`);
    }
    return;
  }
}

function addDownloadLink(jobId, fileKey, text) {
  const dl = document.createElement("a");
  dl.href = `/api/download/${jobId}?file=${fileKey}`;
  dl.textContent = text;
  dl.setAttribute("download", "");
  dl.style.display = "block";
  jobResult.appendChild(dl);
}
