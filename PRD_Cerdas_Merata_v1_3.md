**PRODUCT REQUIREMENTS DOCUMENT**

**Cerdas Merata — AI-Powered Scholarship Eligibility System**

Bimbingan Belajar Domain  |  Reasoning \+ Waiting List Queue  |  Forward Chaining

 

| Atribut | Detail |
| :---- | :---- |
| Versi Dokumen | v1.3 — Revisi Sistem Poin & Enum Pekerjaan |
| Tanggal Dibuat | Juni 2026 |
| Domain | Pendidikan — Bimbingan Belajar (Bimbel) |
| Algoritma Utama | Reasoning: Forward Chaining \+ Waiting List Queue System |
| Database | PostgreSQL (persistent runtime storage) |
| Pameran / Exhibition | AI Exhibition — 10 Juni 2026 |
| Status | Draft v1.2 — Menunggu Review Tim |

# **1\. Overview & Latar Belakang**

Bimbingan belajar "Cerdas Merata" menyediakan kuota subsidi terbatas (50 siswa per bulan) bagi siswa dari keluarga kurang mampu. Saat ini, proses seleksi dilakukan secara manual oleh admin, sehingga tidak konsisten, lambat, dan rentan terhadap bias subjektif.

Proyek ini membangun sistem Agen AI Otonom berbasis web yang mengotomasi proses seleksi:

* Reasoning (Forward Chaining): Menilai kelayakan siswa secara otomatis berdasarkan data ekonomi, akademik, dan sosial yang diinputkan melalui form.

* Waiting List Queue: Semua pendaftar yang lolos seleksi otomatis masuk ke antrian waiting list berurutan berdasarkan skor. Admin/manusia dapat menandai peserta sebagai tidak lolos (jika ditemukan kecurangan atau pemalsuan data), sehingga peserta di bawahnya naik peringkat secara otomatis dan mengisi slot yang terbuka.

Sistem ini juga wajib memenuhi standar Ethical Guardrails sebagaimana disyaratkan oleh tugas mata kuliah, dengan penilaian 50% teknis dan 50% argumen etika.

# **2\. Tujuan Proyek**

## **2.1 Tujuan Fungsional**

1. Membangun mesin reasoning berbasis Forward Chaining dengan 12 aturan IF-THEN yang memproses data siswa dan menghasilkan skor prioritas secara transparan.

2. Membangun sistem Waiting List Queue yang otomatis mengurutkan pendaftar lolos berdasarkan skor, dan secara otomatis menaikkan peringkat peserta berikutnya apabila admin mendiskualifikasi peserta di atasnya karena kecurangan atau pemalsuan data.

3. Menyimpan seluruh data pendaftar dan hasil reasoning ke PostgreSQL sebagai sumber kebenaran sistem.

4. Menyediakan antarmuka web yang dapat digunakan siswa (pendaftar) dan admin bimbel.

5. Menghasilkan reasoning trace yang dapat dibaca pengguna untuk setiap keputusan yang diambil AI.

## **2.2 Tujuan Non-Fungsional**

6. Sistem harus transparan: setiap keputusan disertai alasan yang dapat dipahami manusia.

7. Sistem harus adil: tidak menggunakan atribut suku, agama, ras, atau jenis kelamin.

8. Sistem harus aman: data sensitif (pendapatan, tagihan) tidak disimpan lebih dari 30 hari.

9. Sistem harus memungkinkan intervensi manusia (admin override dan mekanisme banding).

# **3\. Scope & Batasan**

## **3.1 Dalam Scope (In-Scope)**

* Form input data siswa (web-based) dengan 9 field termasuk IPK, status & pekerjaan orang tua, dan wattage listrik

* Mesin Forward Chaining dengan 12 aturan IF-THEN berbasis poin (5 kategori)

* Sistem Waiting List Queue: semua pendaftar lolos langsung masuk antrian berurutan berdasarkan skor; admin dapat mendiskualifikasi peserta (kecurangan/pemalsuan data) dan sistem otomatis menaikkan peringkat peserta berikutnya

* PostgreSQL sebagai database utama runtime sistem

* Dashboard admin: daftar pendaftar, skor, status, dan override

* Reasoning trace yang ditampilkan ke pengguna

* Tombol banding (appeal) yang mengirim notifikasi ke admin

* Dataset sintetis 100 baris (students.csv) \+ rules.json (untuk pengujian dan bias analysis saja)

* Bias analysis report (PDF)

## **3.2 Di Luar Scope (Out-of-Scope)**

* Integrasi dengan sistem pembayaran nyata

* Machine Learning / model prediktif berbasis data historis

* Aplikasi mobile

* Otentikasi multi-faktor dan keamanan produksi level enterprise

* Integrasi API beasiswa eksternal secara real-time

# **4\. Pengguna & Peran (User Roles)**

| Peran | Deskripsi | Akses Utama |
| :---- | :---- | :---- |
| Pendaftar (Siswa) | Siswa/orang tua yang mendaftar subsidi | Isi form, lihat hasil, ajukan banding |
| Admin Bimbel | Staf yang mengelola kuota & keputusan akhir | Dashboard, override keputusan, kelola kuota |
| Reviewer / Dosen (Penilai) | Audiens pameran yang mengevaluasi sistem | Lihat reasoning trace & ethical analysis |

# **5\. Fitur & Requirement Fungsional**

## **5.1 Form Pendaftaran Siswa (FR-01)**

Form web yang mengumpulkan data input untuk mesin reasoning. Setelah submit, data langsung disimpan ke tabel applications di PostgreSQL sebelum diproses oleh AI engine.

| Field Input | Tipe Data | Keterangan & Relevansi Reasoning |
| :---- | :---- | :---- |
| Pendapatan orang tua / bulan | Angka (Rp) | Fakta utama — 3 tier poin kemiskinan |
| Jumlah tanggungan anak sekolah | Integer | Penambah poin prioritas (\>= 3 anak vs 2 anak) |
| Tagihan listrik rata-rata / bulan (Rp) | Angka (Rp) | Indikator keterbatasan ekonomi berbasis biaya |
| Daya listrik terpasang / wattage (VA) | Integer | Indikator infrastruktur ekonomi: 450 / 900 / 1300+ VA |
| IPK atau nilai rata-rata rapor | Desimal | Poin prestasi akademik; skala 0-4 atau 0-100 |
| Status orang tua | Enum | Lengkap / Yatim / Piatu / Yatim-Piatu |
| Pekerjaan orang tua | Enum | Tidak Bekerja / Buruh/Petani / Pedagang Kecil / Wiraswasta / PNS-Swasta-TNI |
| Sedang menerima beasiswa lain? | Boolean | Pengurang poin prioritas jika Ya |
| Kondisi khusus (opsional) | Teks bebas | Trigger anomaly detection untuk human review |

## **5.2 Mesin Reasoning — Forward Chaining (FR-02)**

Sistem membaca data pendaftar dari PostgreSQL, lalu memproses seluruh fakta secara iteratif menggunakan aturan IF-THEN. Semakin tinggi total poin, semakin layak siswa mendapat subsidi. Aturan dikelompokkan dalam 5 kategori.

**Kategori A — Kemiskinan (berdasarkan pendapatan)**

| Kondisi (IF) | Aksi (THEN) | Poin |
| :---- | :---- | :---- |
| Pendapatan \= 0 (tidak ada penghasilan) | Poin kemiskinan kritis | \+10 |
| Pendapatan \< Rp 1.000.000 | Poin kemiskinan sangat tinggi | \+8 |
| Pendapatan Rp 1.000.000 – 1.999.999 | Poin kemiskinan tinggi | \+6 |
| Pendapatan Rp 2.000.000 – 2.999.999 | Poin kemiskinan sedang | \+4 |
| Pendapatan Rp 3.000.000 – 4.500.000 | Poin kemiskinan rendah | \+2 |

**Kategori B — Tanggungan Keluarga**

| Kondisi (IF) | Aksi (THEN) | Poin |
| :---- | :---- | :---- |
| Tanggungan \>= 4 anak sekolah | Poin tanggungan sangat tinggi | \+6 |
| Tanggungan \= 3 anak sekolah | Poin tanggungan tinggi | \+4 |
| Tanggungan \= 2 anak sekolah | Poin tanggungan sedang | \+2 |

**Kategori C — Infrastruktur & Keterbatasan Ekonomi**

| Kondisi (IF) | Aksi (THEN) | Poin |
| :---- | :---- | :---- |
| Tagihan listrik \= 0 / tidak punya listrik | Poin keterbatasan ekstrem | \+6 |
| Tagihan listrik \< Rp 100.000 / bulan | Poin keterbatasan biaya tinggi | \+4 |
| Tagihan listrik Rp 100.000 – 199.999 / bulan | Poin keterbatasan biaya sedang | \+2 |
| Tagihan listrik Rp 200.000 – 350.000 / bulan | Poin keterbatasan biaya rendah | \+1 |
| Wattage listrik terpasang \= 450 VA | Poin keterbatasan infrastruktur tinggi | \+5 |
| Wattage listrik terpasang \= 900 VA | Poin keterbatasan infrastruktur sedang | \+3 |
| Wattage listrik terpasang \= 1300 VA | Poin keterbatasan infrastruktur rendah | \+1 |

**Kategori D — Kondisi Sosial & Keluarga**

| Kondisi (IF) | Aksi (THEN) | Poin |
| :---- | :---- | :---- |
| Status orang tua \= Yatim-Piatu | Poin kondisi keluarga kritis | \+5 |
| Status orang tua \= Yatim atau Piatu | Poin kondisi keluarga berat | \+3 |
| Pekerjaan orang tua \= Tidak Bekerja | Poin sektor rentan kritis | \+5 |
| Pekerjaan orang tua \= Buruh / Petani | Poin sektor rentan tinggi | \+3 |
| Pekerjaan orang tua \= Pedagang Kecil | Poin sektor rentan rendah | \+2 |

**Kategori E — Prestasi Akademik & Pengurang**

| Kondisi (IF) | Aksi (THEN) | Poin |
| :---- | :---- | :---- |
| IPK \>= 3.7 (atau nilai rata-rata \>= 90\) | Poin prestasi sangat tinggi | \+5 |
| IPK 3.5 – 3.69 (atau nilai 85 – 89\) | Poin prestasi tinggi | \+4 |
| IPK 3.0 – 3.49 (atau nilai 75 – 84\) | Poin prestasi sedang | \+2 |
| IPK 2.5 – 2.99 (atau nilai 65 – 74\) | Poin prestasi rendah | \+1 |
| Sedang menerima beasiswa lain \= Ya | Pengurang prioritas | \-8 |

Total skor maksimum teoritis: 45 poin. Threshold kuota: siswa dengan skor tertinggi mengisi 50 slot per bulan melalui Waiting List Queue. Sistem menampilkan reasoning trace lengkap (aturan mana yang aktif dan poin yang diperoleh dari setiap kategori).

## **5.3 Sistem Waiting List Queue (FR-03)**

Setiap pendaftar yang lolos scoring (skor cukup untuk mengisi kuota 50 slot) langsung dimasukkan ke dalam antrian waiting list secara otomatis berdasarkan urutan skor tertinggi. Tidak ada status "lolos langsung" — semua melalui waiting list sebagai mekanisme transparansi dan kontrol kualitas.

**Mekanisme Antrian:**

* Setelah Forward Chaining selesai, sistem mengurutkan seluruh pendaftar berdasarkan total skor (descending).
* 50 posisi teratas mendapat status `waiting_list` dengan posisi antrian (rank) yang tersimpan di database.
* Pendaftar di luar 50 besar mendapat status `rejected`.

**Mekanisme Diskualifikasi & Kenaikan Rank:**

Apabila admin menemukan indikasi kecurangan atau pemalsuan data pada seorang peserta:

1. Admin mengubah status peserta tersebut menjadi `disqualified` dan wajib mengisi alasan (alasan disimpan di kolom `disqualify_reason`).
2. Sistem secara otomatis menaikkan rank semua peserta di bawah posisi tersebut sebesar +1.
3. Peserta dengan rank tertinggi berikutnya (sebelumnya di luar 50 besar) otomatis masuk ke waiting list mengisi slot yang terbuka.
4. Seluruh perubahan rank dicatat di tabel `rank_history` untuk keperluan audit.

**Contoh Skenario:**

> Peserta A (rank 3) terbukti memalsukan data pendapatan → Admin set `disqualified` → Peserta rank 4 naik ke rank 3, rank 5 naik ke rank 4, dst. → Peserta yang sebelumnya rank 51 masuk ke rank 50.

## **5.4 Dashboard Admin (FR-04)**

* Tabel daftar pendaftar beserta skor, posisi rank antrian, status, dan reasoning trace (data dari PostgreSQL)

* Fitur filter berdasarkan status (waiting\_list / disqualified / rejected / banding)

* Tombol Diskualifikasi: admin dapat mendiskualifikasi peserta karena kecurangan/pemalsuan data dan wajib menuliskan alasan; sistem otomatis menaikkan rank peserta berikutnya

* Tombol Override: admin dapat mengubah keputusan AI untuk kasus di luar diskualifikasi dan wajib menuliskan alasan

* Kelola kuota bulanan (ubah batas 50 slot)

* Lihat dan tanggapi banding dari pendaftar

* Export data ke CSV

## **5.5 Ethical Guardrails (FR-05)**

Komponen ini wajib ada dan dinilai secara terpisah (50% dari total nilai).

* Transparansi Penuh: Setiap keputusan menampilkan reasoning trace per kategori — aturan mana yang aktif, poin per kategori, dan total skor.

* Tombol Banding (Appeal): Pendaftar yang merasa tidak adil dapat mengajukan banding. Notifikasi dikirim ke admin untuk review manual.

* Anomaly Detection: Jika ada kondisi ekstrem (pendapatan \= 0, atau wattage 450 VA tapi pendapatan \> 5 juta), sistem menghentikan proses otomatis dan mengirim alert human review.

* Mitigasi Bias: Atribut suku, agama, ras, dan jenis kelamin tidak digunakan. Tagihan listrik dikombinasikan dengan wattage VA untuk menghindari bias daerah subsidi.

* Privasi Data: Data sensitif tidak disimpan lebih dari 30 hari (auto-delete job di PostgreSQL). Consent form wajib ditampilkan sebelum form diproses.

* Bias Analysis: Dataset sintetis diuji dengan kasus-kasus ekstrem untuk memastikan output tidak absurd.

# **6\. Arsitektur Sistem**

## **6.1 Tech Stack**

| Layer | Teknologi | Keterangan |
| :---- | :---- | :---- |
| Frontend | HTML / CSS / JavaScript (atau React) | Form input, halaman hasil reasoning, status antrian |
| Backend / API | Python (Flask / FastAPI) | REST API: terima form, simpan ke DB, panggil AI engine |
| Database | PostgreSQL | Penyimpanan utama runtime: applications, results, appeals, rank\_history |
| ORM / DB Driver | psycopg2 atau SQLAlchemy | Koneksi Python ke PostgreSQL |
| AI Engine — Reasoning | Custom Python (reasoning/engine.py) | Forward chaining — baca dari DB, hasilkan skor \+ trace |
| Queue Engine | Custom Python (queue/manager.py) | Kelola waiting list, hitung rank, proses diskualifikasi \+ kenaikan rank otomatis |
| Rules | rules.json | File konfigurasi statis, dimuat saat server start |
| Dataset Pengujian | students.csv (100 baris sintetis) | Untuk bias analysis saja, tidak digunakan saat runtime |

## **6.2 Alur Data: Form → PostgreSQL → AI → Hasil**

Berikut adalah alur lengkap dari sudut pandang data:

10. Pendaftar membuka web, membaca consent form, dan menyetujui penggunaan data.

11. Pendaftar mengisi form input (FR-01) dan men-submit.

12. Backend (Flask/FastAPI) menerima data form via HTTP POST.

13. Backend memvalidasi semua field (tipe, range, tidak kosong), lalu INSERT ke tabel applications di PostgreSQL. Status awal: 'pending'.

14. Backend memanggil reasoning/engine.py dan mem-passing application\_id sebagai parameter.

15. AI engine melakukan SELECT data pendaftar dari PostgreSQL berdasarkan application\_id.

16. Forward Chaining dijalankan — semua 12 aturan dievaluasi, skor dan trace dikumpulkan.

17. Hasil reasoning (skor, reasoning\_trace JSON) di-INSERT ke tabel results di PostgreSQL.

18. Queue Manager dipanggil: mengurutkan ulang seluruh pendaftar berdasarkan skor, menetapkan rank, dan mengisi 50 slot waiting list. Status pendaftar di-UPDATE ke `waiting_list` (rank 1–50) atau `rejected` (rank 51+).

19. Backend mengembalikan response ke frontend: posisi rank antrian, skor, dan reasoning trace.

20. Frontend menampilkan hasil kepada pendaftar beserta posisinya di antrian.

21. Admin membuka dashboard — query ke PostgreSQL untuk semua data pendaftar, skor, rank, dan status.

22. Jika admin mendiskualifikasi peserta: Queue Manager otomatis menaikkan rank semua peserta di bawahnya dan mencatat perubahan ke tabel rank\_history.

# **7\. Skema Database PostgreSQL**

Empat tabel utama yang digunakan sistem saat runtime. CSV (students.csv) hanya untuk pengujian bias dan tidak pernah diakses oleh AI engine saat aplikasi berjalan.

## **7.1 Tabel: applications**

Menyimpan data form yang disubmit oleh setiap pendaftar.

| Kolom | Tipe | Constraint | Keterangan |
| :---- | :---- | :---- | :---- |
| id | SERIAL | PRIMARY KEY | ID unik auto-increment |
| nama\_pendaftar | VARCHAR(100) | NOT NULL | Nama lengkap siswa |
| pendapatan\_ortu | INTEGER | NOT NULL | Pendapatan orang tua per bulan (Rp) |
| jumlah\_tanggungan | SMALLINT | NOT NULL | Jumlah anak yang masih sekolah |
| tagihan\_listrik | INTEGER | NOT NULL | Rata-rata tagihan listrik per bulan (Rp) |
| wattage\_listrik | SMALLINT | NOT NULL | Daya terpasang: 450 / 900 / 1300 / 2200+ |
| ipk | NUMERIC(4,2) | NOT NULL | IPK skala 4.00 atau nilai rata-rata rapor |
| status\_ortu | VARCHAR(20) | NOT NULL | ENUM: lengkap / yatim / piatu / yatim\_piatu |
| pekerjaan\_ortu | VARCHAR(30) | NOT NULL | ENUM: tidak\_bekerja / buruh\_petani / pedagang\_kecil / wiraswasta / pns\_swasta\_tni |
| bantuan\_lain | BOOLEAN | NOT NULL | True jika sedang menerima beasiswa lain |
| kondisi\_khusus | TEXT | NULLABLE | Teks opsional untuk anomaly detection |
| status\_aplikasi | VARCHAR(20) | DEFAULT 'pending' | pending / waiting\_list / rejected / disqualified / appealed |
| queue\_rank | SMALLINT | NULLABLE | Posisi antrian (1 = tertinggi); NULL jika rejected |
| created\_at | TIMESTAMP | DEFAULT NOW() | Waktu submit form |
| expire\_at | TIMESTAMP | NOT NULL | created\_at \+ 30 hari (auto-delete untuk privasi) |

## **7.2 Tabel: results**

Menyimpan output reasoning dan planning yang dihasilkan AI untuk setiap pendaftar.

| Kolom | Tipe | Constraint | Keterangan |
| :---- | :---- | :---- | :---- |
| id | SERIAL | PRIMARY KEY | ID unik auto-increment |
| application\_id | INTEGER | FK → applications.id | Relasi ke pendaftar |
| total\_skor | SMALLINT | NOT NULL | Total poin hasil Forward Chaining (dapat negatif s/d 45) |
| skor\_per\_kategori | JSONB | NOT NULL | Breakdown poin: {kemiskinan, tanggungan, infrastruktur, sosial, prestasi} |
| reasoning\_trace | JSONB | NOT NULL | Daftar aturan yang aktif beserta poin masing-masing |
| status\_keputusan | VARCHAR(20) | NOT NULL | waiting\_list / rejected / disqualified |
| is\_anomaly | BOOLEAN | DEFAULT FALSE | True jika triggered anomaly detection |
| admin\_override | BOOLEAN | DEFAULT FALSE | True jika admin mengubah keputusan AI |
| override\_reason | TEXT | NULLABLE | Alasan wajib diisi admin jika override \= True |
| disqualify\_reason | TEXT | NULLABLE | Alasan wajib diisi admin jika mendiskualifikasi peserta |
| processed\_at | TIMESTAMP | DEFAULT NOW() | Waktu AI selesai memproses |

## **7.3 Tabel: appeals**

Menyimpan pengajuan banding dari pendaftar yang merasa keputusan tidak adil.

| Kolom | Tipe | Constraint | Keterangan |
| :---- | :---- | :---- | :---- |
| id | SERIAL | PRIMARY KEY | ID unik auto-increment |
| application\_id | INTEGER | FK → applications.id | Relasi ke pendaftar yang mengajukan banding |
| alasan\_banding | TEXT | NOT NULL | Alasan yang ditulis pendaftar |
| status\_banding | VARCHAR(20) | DEFAULT 'open' | open / under\_review / resolved |
| catatan\_admin | TEXT | NULLABLE | Catatan admin setelah review banding |
| created\_at | TIMESTAMP | DEFAULT NOW() | Waktu banding diajukan |
| resolved\_at | TIMESTAMP | NULLABLE | Waktu banding diselesaikan admin |

## **7.4 Tabel: rank\_history**

Mencatat setiap perubahan posisi antrian untuk keperluan audit dan transparansi.

| Kolom | Tipe | Constraint | Keterangan |
| :---- | :---- | :---- | :---- |
| id | SERIAL | PRIMARY KEY | ID unik auto-increment |
| application\_id | INTEGER | FK → applications.id | Pendaftar yang rank-nya berubah |
| rank\_lama | SMALLINT | NOT NULL | Posisi sebelum perubahan |
| rank\_baru | SMALLINT | NOT NULL | Posisi setelah perubahan |
| triggered\_by | INTEGER | FK → applications.id | ID pendaftar yang didiskualifikasi sebagai pemicu perubahan |
| admin\_id | VARCHAR(50) | NOT NULL | Admin yang melakukan diskualifikasi |
| changed\_at | TIMESTAMP | DEFAULT NOW() | Waktu perubahan rank terjadi |

# **8\. Deliverables Proyek**

| Komponen | Isi | Bahasa |
| :---- | :---- | :---- |
| 1\. Prototipe Aplikasi | Web app (form \+ dashboard admin \+ hasil reasoning \+ waiting list queue); terhubung ke PostgreSQL | Inggris (UI) |
| 2\. Poster Ilmiah (A1) | Abstract, Forward Chaining diagram (5 kategori), Waiting List Queue flow, DB schema, Ethical Analysis, QR GitHub, Logo UNPAD | Inggris |
| 3\. Source Code (GitHub) | Folder: reasoning/ \+ queue/ \+ ethics/ \+ db/ \+ tests/. Modular, clean code. | Bebas |
| 4\. Dataset | students.csv (100 baris sintetis, untuk bias analysis), rules.json, bias\_analysis\_report.pdf | Bebas |
| 5\. Panduan Pengguna | Manual instalasi (termasuk setup PostgreSQL) \+ cara input data \+ Ethical Impact Assessment | Indo/Inggris |

# **9\. Struktur Repositori GitHub**

cerdas-merata/  ├── reasoning/          \# Forward chaining engine  │   ├── engine.py       \# Baca dari PostgreSQL, jalankan rules  │   └── rules.json      \# 12 aturan IF-THEN (5 kategori)  ├── queue/              \# Waiting list queue manager  │   └── manager.py      \# Hitung rank, proses diskualifikasi, kenaikan rank otomatis  ├── ethics/             \# Bias testing & guardrails  │   ├── bias\_test.py    \# Uji kasus ekstrem dari students.csv  │   └── bias\_analysis\_report.pdf  ├── db/                 \# Database layer  │   ├── schema.sql      \# CREATE TABLE scripts  │   ├── models.py       \# SQLAlchemy models  │   └── seed.py         \# Import students.csv untuk testing  ├── frontend/           \# UI web (HTML/React)  ├── data/               \# students.csv (sintetis, testing only)  ├── docs/               \# PRD, panduan pengguna  ├── app.py              \# Flask/FastAPI entry point  └── README.md

# **10\. Timeline Pengerjaan**

| Minggu | Fokus | Output |
| :---- | :---- | :---- |
| Minggu 1 | Pembentukan Tim & Lelang Tema | PRD final v1.1, pembagian tugas, setup repo GitHub \+ PostgreSQL lokal |
| Minggu 2 | Eksplorasi Data & Desain Arsitektur | schema.sql, rules.json, students.csv, wireframe UI, diagram arsitektur |
| Minggu 3 | Koding, Testing & Ethical Filtering | Forward chaining engine \+ waiting list queue manager \+ koneksi PostgreSQL \+ bias test \+ web app berjalan |
| Minggu 4 | Poster & Dokumentasi Final | Poster A1 selesai, panduan pengguna PDF (incl. setup PostgreSQL), bias analysis report |
| 10 Juni 2026 | EXHIBITION DAY | Demo live sistem \+ presentasi poster \+ defense pertanyaan |

# **11\. Analisis Risiko & Mitigasi**

| Risiko | Tingkat | Mitigasi |
| :---- | :---- | :---- |
| Threshold kaku membuat penolakan tidak adil | Tinggi | Sistem poin scoring \+ kuota diisi skor tertinggi, bukan pass/fail biner |
| Bias tagihan listrik (daerah subsidi berbeda) | Sedang | Dikombinasikan dengan wattage VA sebagai indikator kedua yang lebih objektif |
| Data pendaftar bisa dipalsukan | Sedang | AI hanya screening awal; keputusan final butuh bukti fisik saat pendaftaran ulang; admin dapat mendiskualifikasi dengan alasan tercatat |
| Kasus anomali (wattage 450VA tapi pendapatan \> 5 juta) | Sedang | Anomaly detection → proses otomatis dihentikan → human review |
| Admin menyalahgunakan fitur diskualifikasi | Sedang | Setiap diskualifikasi wajib disertai alasan dan dicatat di rank\_history; dapat diaudit kapan saja |
| Koneksi PostgreSQL gagal saat demo | Sedang | Siapkan fallback mode dengan SQLite untuk demo offline |
| Dataset sintetis tidak realistis | Sedang | Gunakan acuan data BPS/PODES; seed.py mengimpor students.csv ke DB lokal untuk testing |

# **12\. Kriteria Kelulusan (Grading Criteria)**

## **12.1 Teknis (50%)**

* Kebenaran 12 aturan Forward Chaining dalam 5 kategori (dievaluasi dan diskor dengan benar)

* Kebenaran Waiting List Queue Manager (rank terurut, kenaikan rank otomatis saat diskualifikasi, audit trail tercatat)

* Integrasi PostgreSQL berfungsi: data form tersimpan, AI baca dari DB, hasil disimpan kembali

* Kualitas kode (modular, clean code, ada folder reasoning/, queue/, ethics/, db/)

* Kebersihan dataset sintetis (100 baris, realistis, ada bias\_analysis\_report)

* Fungsionalitas aplikasi web berjalan lancar saat demo

## **12.2 Transformatif / Etika (50%)**

* Kedalaman argumen etika pada poster dan saat presentasi

* Reasoning trace per kategori dapat dibaca dan dipahami pengguna awam

* Ethical guardrails terbukti bekerja: anomaly detection, tombol banding, auto-delete 30 hari

* Bias analysis report menunjukkan pemahaman terhadap kasus-kasus ekstrem

* Kemampuan tim mempertahankan argumen saat diserang pertanyaan teknis dan etika

**Catatan kritis: Aplikasi yang berjalan mulus namun melanggar batasan etika TIDAK mendapat nilai kelulusan.**

# **13\. Persiapan Pertanyaan Serangan (Defense Q\&A)**

## **Teknis: Threshold Kaku**

Serangan: "Sistem menetapkan batas kaku. Siswa dengan gaji Rp 3.005.000 langsung ditolak hanya karena selisih Rp 5.000?"

Jawaban: Sistem kami menggunakan sistem poin scoring dengan 5 kategori, bukan pass/fail biner. Gaji Rp 3,0 juta menghasilkan poin berbeda dari Rp 3,5 juta, dan kuota diisi oleh skor tertinggi. Tidak ada penolakan instan.

## **Etika: Bias Kasus Anomali**

Serangan: "Siswa yatim piatu tinggal dengan kakek yang punya rumah besar tapi tidak berpenghasilan — apakah dia akan didiskriminasi?"

Jawaban: Sistem memiliki anomaly detection. Jika income \= 0 tapi kondisi tidak konsisten dengan indikator lain, proses otomatis dihentikan dan form dikirim ke admin untuk manual review. Kasus yatim-piatu juga mendapat poin tertinggi (+5) di kategori kondisi sosial.

## **Teknis: Kenapa PostgreSQL, bukan langsung proses?**

Serangan: "Kenapa harus simpan ke DB dulu? Bukannya lebih cepat langsung diproses?"

Jawaban: PostgreSQL memisahkan tanggung jawab antara pengumpulan data dan pemrosesan AI. Ini memungkinkan: (1) admin mengaudit semua data, (2) AI bisa dijalankan ulang jika rules diperbarui, (3) history keputusan tersimpan permanen untuk akuntabilitas, dan (4) auto-delete 30 hari bisa diimplementasikan via scheduled job di DB.

## **Transparansi: Explainability**

Serangan: "Darimana pendaftar tahu dia ditolak dengan adil?"

Jawaban: Karena kami menggunakan Forward Chaining, kami melacak setiap aturan yang aktif. Reasoning trace tersimpan di kolom reasoning\_trace (JSONB) di tabel results dan ditampilkan per kategori: misal 'Kategori Kemiskinan: \+5, Kategori Sosial: \+5 (yatim-piatu), Kategori Prestasi: \+3 — Total: 17 poin, posisi antrian saat ini: rank 43 dari 50 slot.'

## **Etika: Penyalahgunaan Fitur Diskualifikasi Admin**

Serangan: "Bagaimana jika admin menyalahgunakan fitur diskualifikasi untuk meloloskan peserta titipan?"

Jawaban: Setiap diskualifikasi wajib disertai alasan tertulis yang tersimpan di kolom disqualify\_reason dan seluruh perubahan rank dicatat otomatis di tabel rank\_history beserta timestamp dan identitas admin. Seluruh log ini dapat diaudit kapan saja oleh reviewer atau manajemen bimbel. Tidak ada aksi admin yang bisa dihapus dari catatan sistem.

*PRD ini merupakan dokumen hidup (v1.3). Setiap perubahan wajib didiskusikan bersama tim dan diupdate di GitHub.*