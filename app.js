/* صوتك — static app. The heavy work runs on the user's own engine (PC or Colab) or on ElevenLabs.
   Sections: helpers · storage · settings · engine client · ElevenLabs client · UI per tab · boot */

// ---------- helpers ----------
const $ = s => document.querySelector(s);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ext = blob => blob.type.includes("mp4") ? "mp4" : blob.type.includes("wav") ? "wav" : "mp3";
function toast(msg, err = false) {
  const t = $("#toast"); t.textContent = msg; t.className = "toast" + (err ? " err" : ""); t.hidden = false;
  clearTimeout(t._timer); t._timer = setTimeout(() => (t.hidden = true), 5000);
}
async function busy(button, statusEl, task) {
  button.disabled = true;
  try { return await task(msg => (statusEl.textContent = msg)); }
  catch (e) { statusEl.textContent = ""; toast(e.message, true); }
  finally { button.disabled = false; }
}

// ---------- storage: voice sample + generated files live in IndexedDB ----------
const store = {
  db: null,
  async open() {
    if (this.db) return this.db;
    this.db = await new Promise((res, rej) => {
      const r = indexedDB.open("sawtak", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("files", { keyPath: "id" });
      r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
    });
    return this.db;
  },
  async tx(mode, fn) {
    const db = await this.open();
    return new Promise((res, rej) => { const t = db.transaction("files", mode); const r = fn(t.objectStore("files")); t.oncomplete = () => res(r?.result); t.onerror = () => rej(t.error); });
  },
  put: rec => store.tx("readwrite", s => s.put(rec)),
  get: id => store.tx("readonly", s => s.get(id)),
  del: id => store.tx("readwrite", s => s.delete(id)),
  all: () => store.tx("readonly", s => s.getAll()),
};

// ---------- settings (localStorage) ----------
const DEFAULTS = { engineUrl: "", engineToken: "", elKey: "", elVoice: "", elModel: "eleven_multilingual_v2", stab: "0.5", sim: "0.85", style: "0.25", engine: "free" };
const settings = { ...DEFAULTS, ...JSON.parse(localStorage.getItem("sawtak_settings") || "{}") };
const saveSettings = () => localStorage.setItem("sawtak_settings", JSON.stringify(settings));

// ---------- engine client (our own server on the user's PC / Colab) ----------
const engine = {
  base: () => settings.engineUrl.replace(/\/+$/, ""),
  async request(path, options = {}) {
    if (!settings.engineUrl) throw new Error("المحرك مش متوصل. افتحي تبويب ⚙️ المحرك.");
    let r;
    try { r = await fetch(this.base() + path, { ...options, headers: { "X-Engine-Token": settings.engineToken, ...(options.headers || {}) } }); }
    catch { throw new Error("المحرك مش بيرد. اتأكدي إنه لسه شغال (Colab أو الكمبيوتر)."); }
    if (!r.ok) { let m = ""; try { m = (await r.json()).detail; } catch { /* not json */ } throw new Error(m || `المحرك رد بخطأ ${r.status}`); }
    return r;
  },
  health: () => engine.request("/health").then(r => r.json()),
  auth: () => engine.request("/auth"),
  async tts(text, lang, sample) {
    const fd = new FormData(); fd.append("text", text); fd.append("lang", lang);
    if (sample) fd.append("sample", sample.blob, sample.name || "sample.webm");
    return (await this.request("/tts", { method: "POST", body: fd })).blob();
  },
  async translate(text, src, tgt) {
    const r = await this.request("/translate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, src, tgt }) });
    return (await r.json()).text;
  },
  async lipsync(face, audio) {
    const fd = new FormData(); fd.append("face", face, face.name); fd.append("audio", audio, "audio." + ext(audio));
    return (await this.request("/lipsync", { method: "POST", body: fd })).blob();
  },
};

// ---------- ElevenLabs client (user's own key, browser-direct) ----------
const eleven = {
  async request(path, options = {}) {
    if (!settings.elKey) throw new Error("حطي مفتاح ElevenLabs في تبويب ⚙️ المحرك");
    const r = await fetch("https://api.elevenlabs.io/v1" + path, { ...options, headers: { "xi-api-key": settings.elKey, ...(options.headers || {}) } });
    if (!r.ok) { let m = ""; try { m = (await r.json()).detail?.message; } catch { /* not json */ } throw new Error(m || `ElevenLabs ${r.status}`); }
    return r;
  },
  async voices() {
    const data = await (await this.request("/voices")).json();
    return data.voices.filter(v => ["cloned", "generated", "professional"].includes(v.category));
  },
  async tts(text, voiceId) {
    const body = { text, model_id: settings.elModel, voice_settings: { stability: +settings.stab, similarity_boost: +settings.sim, style: +settings.style, use_speaker_boost: !settings.elModel.includes("v3") } };
    return (await this.request(`/text-to-speech/${voiceId}?output_format=mp3_44100_128`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })).blob();
  },
};

// ---------- tabs ----------
$("#tabs").onclick = e => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
  ({ library: renderLibrary, video: fillVideoAudio })[b.dataset.tab]?.();
};
const openTab = name => document.querySelector(`#tabs [data-tab="${name}"]`).click();

// ---------- engine status banner ----------
async function refreshStatus() {
  const el = $("#engineStatus");
  if (!settings.engineUrl) { el.className = "status off"; el.textContent = "🔴 المحرك المجاني مش متوصل. افتحي تبويب ⚙️ المحرك وشغّليه (أو استخدمي ElevenLabs)."; return; }
  try {
    const h = await engine.health(); await engine.auth();
    const parts = [h.gpu ? "GPU ⚡" : "CPU", h.tts.cairo ? "عامية + إنجليزي" : null, h.tts.chatterbox ? "+22 لغة" : null, h.lipsync ? "مزامنة شفاه" : null, h.mock ? "وضع تجريبي" : null].filter(Boolean);
    el.className = "status on"; el.textContent = "🟢 المحرك متوصل · " + parts.join(" · ");
  } catch (e) { el.className = "status off"; el.textContent = "🔴 " + e.message; }
}

// ---------- tab: my voice ----------
async function setSample(blob, name) { await store.put({ id: "sample", kind: "sample", name, blob, at: Date.now() }); await showSample(); toast("✓ العينة اتحفظت"); }
async function showSample() {
  const s = await store.get("sample");
  $("#samplePreview").hidden = !s; if (!s) return;
  $("#sampleAudio").src = URL.createObjectURL(s.blob);
  $("#sampleMeta").textContent = `${s.name} · ${(s.blob.size / 1024).toFixed(0)} KB`;
}
$("#sampleFile").onchange = e => { const f = e.target.files[0]; if (f) setSample(f, f.name); };
$("#clearSample").onclick = async () => { await store.del("sample"); showSample(); };
let recorder = null;
$("#recBtn").onclick = async () => {
  if (recorder?.state === "recording") return recorder.stop();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    const chunks = []; recorder = new MediaRecorder(stream);
    recorder.ondataavailable = e => chunks.push(e.data);
    recorder.onstop = () => { stream.getTracks().forEach(t => t.stop()); setSample(new Blob(chunks, { type: recorder.mimeType }), "recording.webm"); $("#recBtn").textContent = "🔴 تسجيل من المايك"; $("#recStatus").textContent = ""; };
    recorder.start(); $("#recBtn").textContent = "⏹ إيقاف"; $("#recStatus").textContent = "بيسجّل… اتكلمي 30 ثانية بشكل طبيعي";
  } catch { toast("مفيش إذن للمايك", true); }
};
async function loadElVoices() {
  if (!settings.elKey) return;
  try {
    const vs = await eleven.voices();
    $("#elVoices").innerHTML = vs.map(v => `<option value="${esc(v.voice_id)}">${esc(v.name)} (${esc(v.category)})</option>`).join("") || "<option value=''>مفيش أصوات مستنسخة في حسابك</option>";
    if (settings.elVoice) $("#elVoices").value = settings.elVoice;
    settings.elVoice = $("#elVoices").value; saveSettings();
  } catch (e) { toast(e.message, true); }
}
$("#elVoices").onchange = () => { settings.elVoice = $("#elVoices").value; saveSettings(); };
$("#elRefresh").onclick = loadElVoices;

// ---------- tab: generate ----------
let last = null; // { blob, text }
function syncEngineUI() { $("#langRow").hidden = $("#engine").value !== "free"; }
$("#engine").value = settings.engine; syncEngineUI();
$("#engine").onchange = () => { settings.engine = $("#engine").value; saveSettings(); syncEngineUI(); };
$("#trTarget").value = "en";
$("#text").oninput = () => { const n = $("#text").value.length; $("#charCount").textContent = n; $("#estTime").textContent = `≈ ${Math.ceil(n / 14)} ثانية كلام`; };
$("#trBtn").onclick = () => busy($("#trBtn"), $("#genStatus"), async status => {
  const text = $("#text").value.trim(); if (!text) throw new Error("اكتبي النص الأول");
  status("بيترجم… (أول مرة بتاخد دقيقة لتحميل موديل الترجمة)");
  $("#text").value = await engine.translate(text, $("#lang").value, $("#trTarget").value);
  $("#lang").value = $("#trTarget").value; $("#text").dispatchEvent(new Event("input"));
  status("✓ اتترجم، راجعيه وولّدي");
});
$("#genBtn").onclick = () => busy($("#genBtn"), $("#genStatus"), async status => {
  const text = $("#text").value.trim(); if (!text) throw new Error("اكتبي النص الأول");
  let blob;
  if ($("#engine").value === "free") {
    const sample = await store.get("sample"); if (!sample) { openTab("voice"); throw new Error("سجّلي أو ارفعي عينة صوتك الأول"); }
    status("بيولّد بصوتك… (أول مرة بتاخد دقيقة لتحميل الموديل)");
    blob = await engine.tts(text, $("#lang").value, sample);
  } else {
    if (!settings.elVoice) { openTab("voice"); throw new Error("اختاري صوتك من تبويب صوتي"); }
    status("بيولّد…"); blob = await eleven.tts(text, settings.elVoice);
  }
  last = { blob, text };
  const url = URL.createObjectURL(blob);
  $("#result").hidden = false; $("#resultAudio").src = url;
  $("#downloadBtn").href = url; $("#downloadBtn").download = `sawtak_${Date.now()}.${ext(blob)}`;
  status("✓ جاهز"); $("#resultAudio").play().catch(() => {});
});
$("#saveBtn").onclick = async () => { if (!last) return; await store.put({ id: "aud_" + Date.now(), kind: "audio", name: last.text.slice(0, 60), blob: last.blob, at: Date.now() }); toast("اتحفظ في ملفاتي"); };
$("#toVideoBtn").onclick = () => openTab("video");

// ---------- tab: video ----------
async function fillVideoAudio() {
  const saved = (await store.all()).filter(x => x.kind === "audio").sort((a, b) => b.at - a.at);
  $("#videoAudio").innerHTML = (last ? '<option value="last">آخر صوت ولّدته</option>' : "") +
    saved.map(x => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("") || '<option value="">ولّدي صوت الأول</option>';
}
$("#videoBtn").onclick = () => busy($("#videoBtn"), $("#videoStatus"), async status => {
  const face = $("#faceFile").files[0]; if (!face) throw new Error("ارفعي صورتك أو فيديوك");
  const choice = $("#videoAudio").value;
  const audio = choice === "last" ? last?.blob : (await store.get(choice))?.blob;
  if (!audio) throw new Error("ولّدي صوت الأول من تبويب ولّد");
  status("بيعمل مزامنة الشفاه… (دقيقة على GPU، أكتر على CPU)");
  const blob = await engine.lipsync(face, audio);
  const url = URL.createObjectURL(blob);
  $("#videoResult").hidden = false; $("#resultVideo").src = url; $("#videoDownload").href = url;
  await store.put({ id: "vid_" + Date.now(), kind: "video", name: "ريلز " + new Date().toLocaleString("ar-EG"), blob, at: Date.now() });
  status("✓ جاهز، واتحفظ في ملفاتي");
});

// ---------- tab: library ----------
async function renderLibrary() {
  const items = (await store.all()).filter(x => x.kind !== "sample").sort((a, b) => b.at - a.at);
  $("#libraryList").innerHTML = items.map(x => {
    const url = URL.createObjectURL(x.blob);
    const player = x.kind === "video" ? `<video controls playsinline src="${url}"></video>` : `<audio controls src="${url}"></audio>`;
    return `<div class="item"><b>${esc(x.name)}</b><div class="meta">${new Date(x.at).toLocaleString("ar-EG")} · ${(x.blob.size / 1024).toFixed(0)} KB</div>${player}
      <div class="row"><a class="btn" download="${esc(x.id)}.${ext(x.blob)}" href="${url}">⬇️ تحميل</a><button class="link" data-del="${esc(x.id)}">حذف</button></div></div>`;
  }).join("") || '<p class="hint">مفيش ملفات لسه.</p>';
}
$("#libraryList").onclick = async e => { const id = e.target.dataset.del; if (id) { await store.del(id); renderLibrary(); } };

// ---------- tab: engine settings ----------
const FIELDS = ["engineUrl", "engineToken", "elKey", "elModel", "stab", "sim", "style"];
function fillSettings() {
  FIELDS.forEach(k => ($("#" + k).value = settings[k]));
  ["stab", "sim", "style"].forEach(k => { $("#" + k + "V").textContent = settings[k]; $("#" + k).oninput = () => ($("#" + k + "V").textContent = $("#" + k).value); });
}
function readSettings() { FIELDS.forEach(k => (settings[k] = $("#" + k).value.trim())); saveSettings(); }
$("#saveSettings").onclick = () => { readSettings(); toast("✓ اتحفظ"); refreshStatus(); loadElVoices(); };
$("#engineTest").onclick = () => { readSettings(); refreshStatus(); };

// ---------- boot: a connect link looks like  #engine=<url>&token=<token> ----------
function readConnectLink() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (!p.get("engine")) return;
  settings.engineUrl = p.get("engine"); settings.engineToken = p.get("token") || ""; settings.engine = "free"; saveSettings();
  history.replaceState(null, "", location.pathname + location.search); // keep the token out of the address bar
  toast("✓ اتوصلتي بالمحرك");
}
readConnectLink(); fillSettings(); $("#engine").value = settings.engine; syncEngineUI();
showSample(); loadElVoices(); refreshStatus();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
