const API_BASE = "http://localhost:5000/api";

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const api = {
  apply:        (body)               => apiFetch("/apply", { method: "POST", body: JSON.stringify(body) }),
  appeal:       (body)               => apiFetch("/appeal", { method: "POST", body: JSON.stringify(body) }),
  getResult:    (id)                 => apiFetch(`/result/${id}`),
  adminList:    (params = "")        => apiFetch(`/admin/applicants${params}`),
  disqualify:   (id, reason)         => apiFetch(`/admin/disqualify/${id}`, { method: "POST", body: JSON.stringify({ reason }) }),
  override:     (id, reason, status) => apiFetch(`/admin/override/${id}`, { method: "POST", body: JSON.stringify({ reason, status }) }),
  resolveAppeal:(id, note)           => apiFetch(`/admin/appeal/${id}/resolve`, { method: "POST", body: JSON.stringify({ note }) }),
  exportCSV:    ()                   => window.open(API_BASE + "/admin/export"),
  stats:        ()                   => apiFetch("/admin/stats"),
};

function formatRp(n) {
  if (n == null) return "-";
  return "Rp " + Number(n).toLocaleString("id-ID");
}

function statusBadge(status) {
  const map = {
    waiting_list:  ["badge-green",  "Waiting List"],
    rejected:      ["badge-red",    "Ditolak"],
    disqualified:  ["badge-orange", "Didiskualifikasi"],
    appealed:      ["badge-purple", "Banding"],
    pending:       ["badge-gray",   "Pending"],
  };
  const [cls, label] = map[status] || ["badge-gray", status];
  return `<span class="badge ${cls}">${label}</span>`;
}

function catClass(cat) {
  return { kemiskinan: "cat-kemiskinan", tanggungan: "cat-tanggungan", infrastruktur: "cat-infrastruktur", sosial: "cat-sosial", prestasi: "cat-prestasi" }[cat] || "";
}
function catLabel(cat) {
  return { kemiskinan: "A — Kemiskinan", tanggungan: "B — Tanggungan Keluarga", infrastruktur: "C — Infrastruktur & Ekonomi", sosial: "D — Kondisi Sosial", prestasi: "E — Prestasi Akademik" }[cat] || cat;
}
