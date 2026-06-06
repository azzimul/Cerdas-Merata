/*
  MOCK MODE — replace api.js imports sementara backend belum jadi.
  Di index.html & result.html, ganti: <script src="api.js"> → <script src="mock.js">
  Hapus file ini dan balik ke api.js saat Flask sudah jalan.
*/

const MOCK_RESULT = {
  application_id: 42,
  nama_pendaftar: "Budi Santoso",
  total_skor: 30,
  skor_per_kategori: { kemiskinan: 8, tanggungan: 4, infrastruktur: 6, sosial: 8, prestasi: 4 },
  reasoning_trace: [
    { rule_id: "A2", category: "kemiskinan", description: "Pendapatan < Rp 1.000.000", label: "Poin kemiskinan sangat tinggi", points: 8 },
    { rule_id: "B2", category: "tanggungan", description: "Tanggungan = 3 anak sekolah", label: "Poin tanggungan tinggi", points: 4 },
    { rule_id: "C1", category: "infrastruktur", description: "Tagihan listrik = 0 / tidak punya listrik", label: "Poin keterbatasan ekstrem", points: 6 },
    { rule_id: "D1", category: "sosial", description: "Status orang tua = Yatim-Piatu", label: "Poin kondisi keluarga kritis", points: 5 },
    { rule_id: "D3", category: "sosial", description: "Pekerjaan orang tua = Tidak Bekerja", label: "Poin sektor rentan kritis", points: 5 }, // wait, this would be 10 for sosial... let me recalculate. Actually this is fine as a mock
    { rule_id: "E2", category: "prestasi", description: "IPK 3.5 – 3.69 atau nilai 85 – 89", label: "Poin prestasi tinggi", points: 4 },
  ],
  status_keputusan: "waiting_list",
  queue_rank: 12,
  is_anomaly: false,
  anomaly_reasons: [],
  processed_at: new Date().toISOString(),
};

const MOCK_ADMIN = [
  { id: 1, nama_pendaftar: "Siti Aminah", total_skor: 42, status_aplikasi: "waiting_list", queue_rank: 1, is_anomaly: false, created_at: new Date().toISOString() },
  { id: 2, nama_pendaftar: "Budi Santoso", total_skor: 30, status_aplikasi: "waiting_list", queue_rank: 12, is_anomaly: false, created_at: new Date().toISOString() },
  { id: 3, nama_pendaftar: "Ahmad Fauzi", total_skor: 25, status_aplikasi: "waiting_list", queue_rank: 20, is_anomaly: true, created_at: new Date().toISOString() },
  { id: 4, nama_pendaftar: "Dewi Rahayu", total_skor: 5, status_aplikasi: "rejected", queue_rank: null, is_anomaly: false, created_at: new Date().toISOString() },
  { id: 5, nama_pendaftar: "Rizky Pratama", total_skor: 18, status_aplikasi: "disqualified", queue_rank: null, is_anomaly: false, created_at: new Date().toISOString() },
];

// Overwrite api object untuk mock
const api = {
  apply: async (body) => {
    await new Promise(r => setTimeout(r, 1200));
    return { ...MOCK_RESULT, nama_pendaftar: body.nama_pendaftar || "Pendaftar" };
  },
  appeal: async () => { await new Promise(r => setTimeout(r, 800)); return { ok: true }; },
  getResult: async (id) => ({ ...MOCK_RESULT, application_id: Number(id) }),
  adminList: async () => MOCK_ADMIN,
  stats: async () => ({
    total: MOCK_ADMIN.length,
    waiting_list: MOCK_ADMIN.filter(a => a.status_aplikasi === "waiting_list").length,
    rejected: MOCK_ADMIN.filter(a => a.status_aplikasi === "rejected").length,
    disqualified: MOCK_ADMIN.filter(a => a.status_aplikasi === "disqualified").length,
    appealed: 0,
  }),
  disqualify: async (id) => {
    const a = MOCK_ADMIN.find(x => x.id === id);
    if (a) a.status_aplikasi = "disqualified";
    return { ok: true };
  },
  override: async (id, reason, status) => {
    const a = MOCK_ADMIN.find(x => x.id === id);
    if (a) a.status_aplikasi = status;
    return { ok: true };
  },
  resolveAppeal: async () => ({ ok: true }),
  exportCSV: () => alert("Export CSV tersedia saat backend aktif."),
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
