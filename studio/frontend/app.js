/* Sawtak Studio dashboard — vanilla JS, talks to /api. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
/** Escape anything user- or server-provided before it goes into an HTML template string. */
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let token = localStorage.getItem("sawtak_token");
let me = null, config = null, langs = {}, voices = [], jobs = [], plans = {};

// ---------- helpers ----------
async function api(path, opts = {}) {
  const headers = opts.headers || {};
  if (token) headers.Authorization = "Bearer " + token;
  if (opts.json) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.json); }
  const r = await fetch(path, { ...opts, headers });
  if (r.status === 401 && token) { logout(); throw new Error("انتهت الجلسة"); }
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error(data?.detail?.[0]?.msg || data?.detail || "حصل خطأ");
  return data;
}
function toast(msg, type = "ok") {
  const t = document.createElement("div"); t.className = "toast " + type; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 4000);
}
function logout() { token = null; localStorage.removeItem("sawtak_token"); location.reload(); }
const fmtDate = s => new Date(s).toLocaleString("ar-EG", { dateStyle: "short", timeStyle: "short" });
const kindName = { tts: "🗣️ صوت", reel: "🎬 ريلز", dub: "🌍 دبلجة" };
const statusName = { queued: "في الانتظار", running: "جاري التنفيذ", done: "جاهز", failed: "فشل" };
const costOf = text => Math.max(1, Math.round(text.length / 1000 * (config?.pricing.credits_per_1000_chars || 10)));

// ---------- auth ----------
$$(".tabs button").forEach(b => b.onclick = () => {
  $$(".tabs button").forEach(x => x.classList.remove("active")); b.classList.add("active");
  const signup = b.dataset.mode === "signup";
  $("#nameField").style.display = signup ? "block" : "none";
  $("#authForm button[type=submit]").textContent = signup ? "إنشاء حساب" : "دخول";
});
$("#authForm").onsubmit = async e => {
  e.preventDefault();
  const mode = $(".tabs button.active").dataset.mode;
  const f = Object.fromEntries(new FormData(e.target));
  try {
    const d = await api(`/api/auth/${mode}`, { method: "POST", json: f });
    token = d.access_token; localStorage.setItem("sawtak_token", token);
    await boot();
  } catch (err) { toast(err.message, "err"); }
};
$("#logout").onclick = logout;

// ---------- boot ----------
async function boot() {
  config = await api("/api/config");
  $$(".brand").forEach(e => e.textContent = config.app_name_ar);
  if (!token) { $("#auth").style.display = "grid"; return; }
  try { me = await api("/api/auth/me"); } catch { return; }
  $("#auth").style.display = "none"; $("#shell").style.display = "grid";
  [langs, plans] = await Promise.all([api("/api/voices/languages"), api("/api/billing/plans")]);
  fillLangs(); renderMe();
  $("#defLip").textContent = config.lipsync_engine;
  $$(".cloneCost").forEach(e => e.textContent = config.pricing.credits_per_voice_clone);
  await Promise.all([loadVoices(), loadJobs()]);
  route(); setInterval(pollJobs, 3000);
  const want = new URLSearchParams(location.search).get("plan");
  if (want && want !== "free") { location.hash = "billing"; }
}
function fillLangs() {
  const opts = Object.entries(langs).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  $$(".langSelect").forEach(s => s.insertAdjacentHTML("beforeend", opts));
  $("#cloneLang").innerHTML = opts; $("#cloneLang").value = "ar";
}
function renderMe() {
  $("#credits").textContent = me.credits; $("#kCredits").textContent = me.credits;
  $("#planName").textContent = "باقة " + me.plan_info.name; $("#userName").textContent = me.name || me.email;
  $("#billPlan").textContent = me.plan_info.name; $("#billCredits").textContent = me.credits;
  $("#apiKey").textContent = me.api_key;
  $("#adminLink").style.display = me.is_admin ? "flex" : "none";
  $("#remoteCard").style.display = me.is_admin ? "block" : "none";
  $("#billPlans").innerHTML = ["free", "creator", "pro", "agency"].map(k => { const p = plans[k]; return `
    <div class="card plan ${me.plan === k ? "hot" : ""}"><h3>${esc(p.name)}</h3><div class="price">${p.price_egp ? p.price_egp + " ج" : "مجاناً"}<small>${p.price_egp ? " / شهر" : ""}</small></div>
    <ul><li>${p.monthly_credits} كريدت</li><li>${p.max_voices} صوت</li><li>فيديو حتى ${p.max_video_seconds} ث</li><li>${p.watermark ? "علامة مائية" : "بدون علامة"}</li></ul>
    ${me.plan === k ? '<span class="badge done">باقتك الحالية</span>' : `<button class="btn primary sm" onclick="upgrade('${k}')">اشترك</button>`}</div>`; }).join("");
}
window.upgrade = async plan => {
  const d = await api("/api/billing/request-upgrade", { method: "POST", json: { plan } });
  const wa = config.whatsapp || "";
  const url = wa ? `https://wa.me/${wa}?text=${encodeURIComponent(d.message)}` : null;
  if (url) window.open(url, "_blank"); else { await navigator.clipboard?.writeText(d.message); toast("اتنسخت رسالة التفعيل، ابعتها على واتساب الدعم"); }
};

// ---------- routing ----------
function route() {
  const v = (location.hash || "#home").slice(1);
  $$(".view").forEach(x => x.classList.toggle("active", x.id === "view-" + v));
  $$(".side nav a").forEach(a => a.classList.toggle("active", a.dataset.view === v));
  $("#side").classList.remove("open");
  if (v === "billing") loadLedger(); if (v === "admin") loadAdmin();
}
window.addEventListener("hashchange", route);
$("#menuBtn").onclick = () => $("#side").classList.toggle("open");

// ---------- voices ----------
async function loadVoices() {
  voices = await api("/api/voices");
  $("#kVoices").textContent = voices.length;
  $("#voiceList").innerHTML = voices.length ? voices.map(v => `<div class="item"><div class="grow"><b>${esc(v.name)}</b><div class="meta">${esc(langs[v.language] || v.language)} · ${esc(v.engine)} · ${fmtDate(v.created_at)}</div></div>
    <button class="btn sm danger" onclick="delVoice('${v.id}')">حذف</button></div>`).join("") : '<p class="hint">لسه مفيش أصوات. ارفع عينة فوق 👆</p>';
  const opts = voices.map(v => `<option value="${esc(v.id)}">${esc(v.name)}</option>`).join("");
  $$(".voiceSelect").forEach(s => s.innerHTML = opts || '<option value="">— استنسخ صوت الأول —</option>');
}
window.delVoice = async id => { if (!confirm("تحذف الصوت ده؟")) return; await api(`/api/voices/${id}`, { method: "DELETE" }); toast("اتحذف"); loadVoices(); };
$("#cloneForm").onsubmit = async e => {
  e.preventDefault(); const btn = e.target.querySelector("button[type=submit]"); btn.disabled = true;
  try { await api("/api/voices", { method: "POST", body: new FormData(e.target) }); toast("تم استنساخ صوتك ✓"); e.target.reset(); recordedBlob = null; $("#recStatus").textContent = ""; await Promise.all([loadVoices(), refreshMe()]); }
  catch (err) { toast(err.message, "err"); } finally { btn.disabled = false; }
};
$("#loadRemote").onclick = async () => {
  try { const r = await api("/api/voices/remote"); $("#remoteVoices").innerHTML = r.map(v => `<option value="${esc(v.voice_id)}">${esc(v.name)} (${esc(v.category)})</option>`).join("") || "<option>لا يوجد</option>"; }
  catch (err) { toast(err.message, "err"); }
};
$("#importRemote").onclick = async () => {
  const s = $("#remoteVoices"); if (!s.value || s.value.startsWith("—")) return;
  const fd = new FormData(); fd.append("voice_id", s.value); fd.append("name", s.selectedOptions[0].textContent.split(" (")[0]); fd.append("language", "ar");
  try { await api("/api/voices/import", { method: "POST", body: fd }); toast("اتربط ✓"); loadVoices(); } catch (err) { toast(err.message, "err"); }
};
// in-browser recording of the sample
let rec = null, chunks = [], recordedBlob = null;
$("#recBtn").onclick = async () => {
  if (rec && rec.state === "recording") { rec.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    rec = new MediaRecorder(stream); chunks = [];
    rec.ondataavailable = e => chunks.push(e.data);
    rec.onstop = () => {
      recordedBlob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      const dt = new DataTransfer(); dt.items.add(new File([recordedBlob], "recording.webm", { type: recordedBlob.type }));
      $("#cloneForm input[name=sample]").files = dt.files;
      $("#recStatus").textContent = "✓ التسجيل جاهز، اضغط استنسخ"; $("#recBtn").textContent = "🔴 تسجيل";
      stream.getTracks().forEach(t => t.stop());
    };
    rec.start(); $("#recBtn").textContent = "⏹ إيقاف"; $("#recStatus").textContent = "بيسجل… اتكلم بشكل طبيعي 30 ثانية";
  } catch { toast("مفيش إذن للميكروفون", "err"); }
};

// ---------- jobs ----------
async function refreshMe() { me = await api("/api/auth/me"); renderMe(); }
function jobCard(j) {
  const out = j.output_url ? (j.kind === "tts" ? `<audio controls src="${j.output_url}?t=${token}"></audio>` : `<video controls playsinline src="${j.output_url}?t=${token}"></video>`) : "";
  const txt = j.params.translated_text ? `<div class="meta">🌍 الترجمة: ${esc(j.params.translated_text)}</div>` : "";
  return `<div class="item" id="job-${j.id}"><div class="grow"><b>${kindName[j.kind]}</b> <span class="badge ${j.status}">${statusName[j.status]}</span>
    <div class="meta">${esc((j.params.text || j.params.target_lang || "").slice(0, 120))}</div>${txt}<div class="meta">${esc(j.message)} · ${esc(j.credits_cost)} كريدت · ${fmtDate(j.created_at)}</div>
    ${j.status === "running" || j.status === "queued" ? `<div class="bar"><i style="width:${Math.round(j.progress * 100)}%"></i></div>` : ""}${out}</div>
    ${j.output_url ? `<a class="btn sm" href="${j.output_url}?t=${token}" download>⬇️ تحميل</a>` : ""}<button class="btn sm danger" onclick="delJob('${j.id}')">🗑</button></div>`;
}
function renderJobs() {
  $("#kJobs").textContent = jobs.filter(j => j.status === "done").length;
  const by = k => jobs.filter(j => j.kind === k).map(jobCard).join("") || '<p class="hint">مفيش حاجة لسه.</p>';
  $("#ttsJobs").innerHTML = by("tts"); $("#reelJobs").innerHTML = by("reel"); $("#dubJobs").innerHTML = by("dub");
  $("#allJobs").innerHTML = jobs.map(jobCard).join("") || '<p class="hint">المكتبة فاضية.</p>';
  $("#recentJobs").innerHTML = jobs.slice(0, 3).map(jobCard).join("") || '<p class="hint">ابدأ أول عمل ليك 🚀</p>';
}
async function loadJobs() { jobs = await api("/api/jobs"); renderJobs(); }
async function pollJobs() {
  if (!jobs.some(j => j.status === "queued" || j.status === "running")) return;
  const before = jobs.filter(j => j.status !== "done" && j.status !== "failed").map(j => j.id);
  await loadJobs();
  if (jobs.some(j => before.includes(j.id) && j.status === "done")) { toast("ملف جاهز ✓"); refreshMe(); }
  if (jobs.some(j => before.includes(j.id) && j.status === "failed")) { toast("عملية فشلت، اتردّ الرصيد", "err"); refreshMe(); }
}
window.delJob = async id => { await api(`/api/jobs/${id}`, { method: "DELETE" }); loadJobs(); };
$$("textarea[name=text]").forEach(t => t.oninput = () => { const f = t.closest("form"); $(".charCount", f).textContent = t.value.length; $(".costEst", f).textContent = costOf(t.value) * (f.translate_to?.value ? 2 : 1); });
async function submitJob(form, path, asJson) {
  const btn = form.querySelector("button[type=submit]"); btn.disabled = true;
  try {
    const fd = new FormData(form);
    const d = asJson ? await api(path, { method: "POST", json: Object.fromEntries([...fd].filter(([, v]) => v !== "")) }) : await api(path, { method: "POST", body: fd });
    toast(`اتبعت للتنفيذ (${d.credits_cost} كريدت)`); jobs.unshift(d); renderJobs(); refreshMe();
  } catch (err) { toast(err.message, "err"); } finally { btn.disabled = false; }
}
$("#ttsForm").onsubmit = e => { e.preventDefault(); submitJob(e.target, "/api/tts", true); };
$("#reelForm").onsubmit = e => { e.preventDefault(); submitJob(e.target, "/api/reels", false); };
$("#dubForm").onsubmit = e => { e.preventDefault(); submitJob(e.target, "/api/dub", false); };

// ---------- billing / admin ----------
$("#rotateKey").onclick = async () => { me = await api("/api/auth/rotate-key", { method: "POST" }); renderMe(); toast("اتجدد المفتاح"); };
async function loadLedger() {
  const l = await api("/api/billing/ledger");
  $("#ledger").innerHTML = l.map(r => `<div class="item"><div class="grow"><b style="color:${r.delta > 0 ? "var(--ok)" : "var(--err)"}">${r.delta > 0 ? "+" : ""}${r.delta}</b> <span class="meta">${esc(r.reason)} ${esc(r.job_id || "")}</span></div><span class="meta">${fmtDate(r.at)}</span></div>`).join("") || '<p class="hint">فاضي</p>';
}
async function loadAdmin() {
  if (!me.is_admin) return;
  const u = await api("/api/billing/admin/users");
  $("#adminUsers").innerHTML = u.map(x => `<div class="item"><div class="grow"><b>${esc(x.email)}</b> <span class="badge">${esc(x.plan)}</span><div class="meta">${esc(x.name)} · ${esc(x.credits)} كريدت · ${esc(x.voices)} صوت · ${esc(x.jobs)} عمل · ${fmtDate(x.created_at)}</div></div></div>`).join("");
}
$("#adminForm").onsubmit = async e => {
  e.preventDefault(); const f = Object.fromEntries(new FormData(e.target));
  try { const r = await api(`/api/billing/admin/activate?plan=${f.plan}`, { method: "POST", json: { user_email: f.user_email, delta: +f.delta, reason: f.reason } }); toast(`${r.email}: ${r.plan} / ${r.credits} كريدت`); loadAdmin(); }
  catch (err) { toast(err.message, "err"); }
};

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
boot().catch(err => toast(err.message, "err"));
