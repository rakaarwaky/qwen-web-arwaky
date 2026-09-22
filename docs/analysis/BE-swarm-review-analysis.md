# Analisis Lengkap Issue Backend Engineering (BE) — qwen-web-arwaky

**Tanggal analisis:** 2026-09-22
**Sumber:** swarm run `swarm_20260921_131128_4f05e3`, agent `backend-engineer`
**Total issue BE terbuka:** 15 (`#258`–`#271`, `#402`)
**Status:** semua `open`, belum ada yang dikerjakan
**Metode:** setiap klaim issue diverifikasi ulang terhadap kode di `HEAD` (`0d8bafc`), bukan sekadar mengutip issue.

---

## 1. Peta Issue

| # | ID | Severity | Judul singkat | Area | Klaim valid? |
|---|----|----------|---------------|------|--------------|
| 263 | BE-3-001 | CRITICAL | CircuitBreaker & RateLimiter tanpa lock | Concurrency | ✅ Valid (dampak dikoreksi ke bawah) |
| 264 | BE-3-002 | CRITICAL | Swarm `_attachment_paths` KeyError saat cancel | Concurrency | ✅ Valid |
| 270 | BE-5-002 | CRITICAL | Tidak ada tes konkurensi | Test coverage | ✅ Valid |
| 258 | BE-1-001 | WARNING | Envelope async MCP langgar FR-002 | API contract | ✅ Valid |
| 259 | BE-1-002 | WARNING | `process_direct_prompt` tanpa `output_file` | API parity | ✅ Valid |
| 260 | BE-2-001 | WARNING | Sanitasi nama file job kurang lengkap | Robustness | ⚠️ Valid tapi teoretis |
| 261 | BE-2-002 | WARNING | TOCTOU `list_jobs` | Concurrency | ⚠️ Valid, fix usulan salah |
| 265 | BE-3-003 | WARNING | `id(cancel_event)` sebagai registry key | Correctness | ⚠️ Valid tapi risiko sangat kecil |
| 266 | BE-4-001 | WARNING | StreamMonitor evaluasi JS ganda | Performance | ✅ Valid |
| 267 | BE-4-002 | WARNING | SendDispatcher polling boros | Performance | ⚠️ Angka di issue salah |
| 269 | BE-5-001 | WARNING | TEST.md nama modul basi | Dokumentasi | ✅ Valid |
| 271 | BE-5-003 | WARNING | Tidak ada tes path traversal/symlink MCP | Security test | ✅ Valid (sebagian sudah ada) |
| 262 | BE-2-003 | INFO | Filter `.tmp_` pakai substring | Robustness | ⚠️ Valid, fix usulan salah |
| 268 | BE-4-003 | INFO | `lru_cache` blokir hot-reload template | DX | ✅ Valid |
| 402 | BE-1-003 | INFO | Validasi `--text` kosong terlambat | UX/CLI | ✅ Valid |

Ringkasan tema: **6 concurrency/thread-safety, 3 API contract, 2 performance, 2 test coverage, 1 dokumentasi, 1 UX.**

---

## 2. Analisis Per Issue

### 🔴 #263 (BE-3-001) — CircuitBreaker & RateLimiter tanpa `threading.Lock`

**Kode aktual (`modules/shared/src/taxonomy_core_entity.py:30-140`):** terkonfirmasi — tidak ada `threading.Lock` sama sekali di kedua kelas.

```python
def _refresh_state(self) -> None:
    current = time.time()
    while self._failures and (current - self._failures[0]) > self._window_sec:
        self._failures.popleft()
    self._trip = len(self._failures) >= self._threshold
```

**Koreksi penting terhadap issue.** Issue menulis *"worker threads call `record_failure()` / `record_success()` and `RateLimiter.acquire()` concurrently"*. Hasil telusur pemanggil:

- `record_failure()` — dipanggil dari `agent_job_orchestrator.py:261,275,313,337`, yaitu **di dalam worker thread**. → benar-benar konkuren, hingga 10 thread.
- `record_success()` — `agent_job_orchestrator.py:208`, juga worker thread. → konkuren.
- `_rate_limiter.acquire()` — dipanggil dari `_guard_dispatch()` (line 65-70) yang hanya dieksekusi di jalur **submit**, bukan worker. Di MCP, submit berjalan lewat `loop.run_in_executor(None, ...)` sehingga masih bisa paralel, tapi jauh lebih jarang daripada yang digambarkan issue.

Jadi klaim `RateLimiter` di-hit 10 thread sekaligus itu **berlebihan**; yang benar-benar panas adalah `CircuitBreaker`.

**Dampak nyata:** karena GIL, `deque.append`/`popleft` masing-masing atomik, jadi `IndexError` yang disebut issue praktis tidak akan terjadi. Yang riil adalah **race pada urutan compound**: dua thread `record_failure` bersamaan bisa menghasilkan `_trip` yang dihitung dari snapshot berbeda, sehingga breaker bisa trip satu kejadian terlambat. Ini degradasi akurasi, bukan crash.

**Rekomendasi:** tetap kerjakan — tambah `threading.Lock`. Bukan karena bug-nya parah hari ini, tapi karena ini komponen reliability yang harus benar secara kontrak, dan biayanya ~15 baris. Turunkan label dari CRITICAL ke WARNING agar antrean prioritas tidak terdistorsi.

---

### 🔴 #264 (BE-3-002) — `KeyError` pada `_attachment_paths` setelah cancel

**Kode aktual (`modules/core/src/agent_swarm_orchestrator.py`):** terkonfirmasi persis.

- Line 130 (`cancel()`, di dalam lock): `self._attachment_paths.pop(swarm_id, None)`
- Line 149 (`_run_agent`, **di luar lock**, worker thread): `attachment_file=self._attachment_paths[swarm_id]`

Line 137-139 memang ada cek `event.is_set()` di awal tiap attempt, tapi ada jendela antara cek itu dan line 149. `cancel()` juga memanggil `executor.shutdown(cancel_futures=True)` — itu hanya membatalkan future yang **belum mulai**, tidak yang sedang jalan.

**Dampak:** `KeyError` ditangkap oleh `except Exception` generik, lalu agent dilaporkan `failed` dengan pesan error berupa string `KeyError`, padahal seharusnya `cancelled` / `"Cancelled by user"`. Efek ke user: manifest swarm menunjukkan kegagalan palsu, dan retry loop bisa jalan padahal user sudah membatalkan.

**Ini issue paling layak disebut CRITICAL** dari 15 yang ada — satu-satunya yang menghasilkan unhandled exception path + status laporan yang salah, dan gampang direproduksi (cancel swarm saat agent jalan).

**Catatan atas patch usulan:** patch di issue menempatkan snapshot **sebelum** retry loop dan langsung `return` kalau `attachment_path is None`. Itu benar, tapi perlu hati-hati: `_run_agent` juga dipakai untuk role tanpa attachment? Perlu dicek — kalau ada jalur prompt-only, `None` adalah kondisi sah dan early-return akan salah. Dari pembacaan kode, `_attachment_paths[swarm_id]` selalu diset di line 74 saat swarm start, jadi aman, tapi ini harus dikonfirmasi saat implementasi.

---

### 🔴 #270 (BE-5-002) — Tidak ada tes konkurensi

**Terkonfirmasi:** tidak ada `tests/test_concurrency.py` atau sejenisnya. Yang ada:
- `tests/integration_parallel_jobs.py` — hanya menguji *wiring* `max_workers` dan bahwa N job jalan paralel; tidak menguji thread-safety `CircuitBreaker`/`RateLimiter`/`JobManager`.
- `tests/unit_capability_job_manager.py` — single-thread.

**Kritik terhadap patch usulan (penting).** Test yang ditulis di issue **cacat**:

```python
assert cb.is_tripped, "Breaker must trip after >= 5 concurrent failures"
```
Ini akan **hijau bahkan tanpa lock**, karena 10 failure > threshold 5 apa pun urutannya. Test ini tidak mendeteksi race yang seharusnya dijaga. Acceptance criteria-nya sendiri bilang *"trips at exactly the threshold"*, tapi assertion-nya tidak menguji itu.

Test RateLimiter juga bermasalah: thread tidak di-join, pakai `time.sleep(2)` — flaky by design, dan meninggalkan thread menggantung yang bisa mengganggu test lain.

**Rekomendasi:** issue-nya valid dan harus dikerjakan, tapi **jangan pakai patch yang ada**. Tulis test yang benar-benar mendeteksi race (mis. `threading.Barrier` + hitung berapa kali transisi `False→True` teramati, atau injeksi `time.sleep` di titik race). Dan syaratnya: tes ini hanya bermakna **setelah** #263 diperbaiki — kalau ditulis duluan dengan assertion benar, ia akan merah dan memblokir CI.

**Urutan yang benar: #263 dulu, baru #270.**

---

### 🟡 #258 (BE-1-001) — Envelope async MCP langgar FR-002

Sudah dianalisis terpisah. Ringkas: `process_prompt_file_only` (line 260-280) dan `process_prompt_with_attachment` (line 339-360) pada jalur `async_run=True` (default) mengembalikan JSON tanpa `status`, `result`, `run_id` — sementara `_format_success_payload` (line 49-71) dan FRD FR-002 mewajibkan `status`. Konsumen AI agent harus bercabang pada dua skema untuk tool yang sama.

Fix: tambah `"status": "ACCEPTED"`. Backward compatible, 2 baris.

**Catatan tambahan dari pembacaan kode yang tidak disebut issue:** `get_job_status` (line 421-435) dan `list_jobs` (line 478) **juga** tidak punya field `status`. Kalau mau konsisten, sekalian tambahkan di sana (`RUNNING`/`COMPLETED`/`FAILED`). Kalau tidak, kita cuma menambal sebagian dan masalah yang sama muncul lagi di tool lain.

---

### 🟡 #259 (BE-1-002) — `process_direct_prompt` tanpa `output_file`

**Terkonfirmasi 3 lapis:**
- `contract_core_aggregate.py:79-85` — kontrak **sudah** punya `output_file`.
- `agent_direct_prompt_orchestrator.py:64-70` — implementasi **sudah** punya `output_file`.
- `root_mcp_main_entry.py:111-134` — schema MCP **tidak** mendeklarasikan `output_file`.
- `surface_mcp_tool_command.py:203` — signature MCP **tidak** menerima `output_file`.

Jadi kemampuannya sudah ada di core, hanya tidak diekspos di permukaan MCP. Ini bukan fitur baru, ini **menyambung kabel yang sudah terpasang**. Rasio benefit/effort paling tinggi di antara semua issue.

Efeknya sekarang: CLI punya `prompt-direct -o FILE`, MCP tidak. Melanggar paritas CLI↔MCP (PRD Goal 3).

**Ada open question dari agent** (lihat #271): *"Should MCP `process_direct_prompt` support `output_file` given that direct prompts are inherently ephemeral?"* — ini butuh keputusan produk, lihat Bagian 5.

---

### 🟡 #260 (BE-2-001) — Sanitasi nama file job

**Kode aktual (`capabilities_job_manager.py:32-34`):** terkonfirmasi, hanya ganti `/` dan `\`.

**Tapi:** job ID digenerate internal oleh `_generate_job_id()` (`agent_job_orchestrator.py:72-75`):
```python
ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
rand = uuid.uuid4().hex[:6]
return JobId(f"{prefix}_{ts}_{rand}")
```
Hasilnya selalu `file_20260922_131128_a1b2c3` — **alfanumerik + underscore, panjang tetap ~28 karakter**. Contoh `file_2026:09:21_test` di issue tidak mungkin terjadi dari jalur normal.

**Namun ada permukaan serang nyata:** `get_job_status(job_id)` di MCP menerima `job_id` **dari user/agent** dan meneruskannya ke `_job_file_path()` (line 47). Sanitasi `/` dan `\` memang mencegah traversal dasar, tapi ini artinya fungsi itu memang menerima input tak terpercaya, sehingga hardening tetap masuk akal sebagai defense-in-depth.

**Verdict:** valid sebagai hardening, bukan sebagai bug. Prioritas rendah. Patch usulan (regex + SHA-256 suffix) bagus dan aman.

---

### 🟡 #261 (BE-2-002) — TOCTOU `list_jobs`

**Kode aktual (line 71-89):** terkonfirmasi ada jeda antara `path.stat()` (line 80) dan `self.get_job(job_id)` (line 86).

**Tapi race-nya jauh lebih jinak dari yang digambarkan.** `save_job` memakai `atomic_write_text` → `_atomic_write` (`utility_core_io_writer.py:21-40`) yang menulis ke temp lalu `tmp_path.replace(target)`. `Path.replace` adalah `rename()` — **atomik di POSIX**. Jadi pembaca tidak akan pernah melihat JSON separuh jadi. Klaim issue *"partial JSON read"* **tidak akurat**.

Sisa risiko riil: file dihapus antara `stat` dan `get_job` → `get_job` return `None` → list lebih pendek dari `limit`. Kosmetik.

**Patch usulan justru merugikan.** Backfill loop yang diusulkan akan, ketika ada 1 file hilang, membaca file **tambahan yang lebih tua** untuk mengisi kuota. Artinya `list_jobs(limit=10)` bisa mengembalikan job ke-11 tanpa penanda — mengubah semantik "10 terbaru" menjadi "10 yang berhasil dibaca". Untuk UI daftar job, itu membingungkan.

**Rekomendasi:** ambil hanya bagian docstring-nya (dokumentasikan best-effort / eventual consistency). **Tolak backfill loop-nya.** Atau downgrade ke INFO.

---

### 🟡 #265 (BE-3-003) — `id(cancel_event)` sebagai registry key

**Terkonfirmasi di dua file:**
- `agent_prompt_file_orchestrator.py:94,107,141,175`
- `agent_attachment_prompt_orchestrator.py:101,114,150,194`

Klaim teknisnya benar: `id()` = alamat memori, bisa didaur ulang setelah GC.

**Tapi probabilitas praktisnya hampir nol.** Agar bug terjadi, harus: `_RunState` di-pop dari registry (line 175, di `finally`) → `Event` di-GC → `Event` baru dialokasi di alamat sama → lalu ada `request_cancel` yang memegang referensi ke Event **lama**. Masalahnya, kalau pemanggil masih pegang referensi ke Event lama, Event itu **tidak akan di-GC** — jadi alamatnya tidak bisa didaur ulang. Skenario ini secara logis hampir tidak bisa terjadi.

**Nilai sebenarnya bukan bug-fix, tapi kualitas kode:** `dict[int, _RunState]` menghilangkan makna semantik key, bikin debugging susah, dan pola `id()`-as-key adalah code smell yang bikin reviewer berikutnya berhenti dan berpikir. Patch UUID membuatnya self-documenting.

**Verdict:** kerjakan sebagai refactor kebersihan saat menyentuh file itu, bukan sebagai perbaikan bug tersendiri. Downgrade ke INFO.

---

### 🟡 #266 (BE-4-001) — StreamMonitor evaluasi JS redundan

**Kode aktual (`capabilities_stream_monitor.py`):** terkonfirmasi.
```
line 195:  is_thinking = self.is_thinking_active(page)
line 196:  is_complete = self.is_generation_complete(page)
line 82-87: def is_generation_complete(...): ... return not self.is_thinking_active(page)
```
`is_thinking_active` benar-benar dipanggil **dua kali per siklus poll**.

**Dampak:** dengan poll 1 detik dan 10 slot paralel, itu 10 evaluasi JS mubazir per detik + 10 round-trip IPC Chromium yang tidak perlu. Bukan bottleneck fatal, tapi murni pemborosan — hasil kedua pasti sama dengan yang pertama dalam siklus yang sama.

**Perhatian pada patch usulan:** patch mengganti `is_generation_complete(page)` dengan inline `(not stop_visible) and (not is_thinking)`. Ini **mengasumsikan** isi `is_generation_complete` hanya itu. Dari line 82-87 memang tampak begitu, tapi inlining logika dari method publik ke call-site berarti kalau nanti `is_generation_complete` diubah, call-site ini diam-diam jadi tidak sinkron. **Lebih baik:** ubah signature jadi `is_generation_complete(page, *, thinking: bool | None = None)` supaya logika tetap terpusat.

---

### 🟡 #267 (BE-4-002) — SendDispatcher polling boros

**Kode aktual (`capabilities_send_dispatcher.py:219-235`):** terkonfirmasi ada loop dengan `_is_file_card_parsing` dan `_is_parse_toast_visible`.

**Angka di issue salah.** Issue menulis *"`page.wait_for_timeout(200)` ... ~600 iterations"*. Kode aktualnya:
- Jalur parsing: `page.wait_for_timeout(500)` (line 227 dan 233), bukan 200ms.
- `wait_for_timeout(200)` hanya di ujung loop ketika **tidak** sedang parsing.

Jadi selama fase parsing panjang (yang justru jadi premis issue), interval sudah 500ms, bukan 200ms. Estimasi "12.000 IPC calls" overstated sekitar 2,5×.

**Masalah intinya tetap valid:** dengan `click_timeout_ms=120_000`, polling 500ms selama 90 detik parsing = ~180 iterasi × ~15 locator query = ~2.700 IPC call yang sebagian besar sia-sia karena state tidak mungkin berubah secepat itu.

**Verdict:** valid tapi prioritas rendah. Ini murni optimisasi; tidak ada bug fungsional. Adaptive backoff bagus, tapi acceptance criteria *"detected within 500ms"* jadi kontradiktif kalau interval dinaikkan ke 1s — kriteria itu perlu direvisi jadi ~1s.

---

### 🟡 #269 (BE-5-001) — TEST.md nama modul basi

**Terkonfirmasi, dan lebih parah dari yang ditulis issue.** `TEST.md:20-32` mereferensikan:

| Disebut TEST.md | Realita |
|---|---|
| `prompt_injector.py` | → `capabilities_prompt_injector.py` |
| `prompt_injector.py::type_slowly` | **method tidak ada lagi** |
| `file_uploader.py::upload_file_attachment` | → `capabilities_file_uploader.py`, nama method beda |
| `sender.py` | → `capabilities_send_dispatcher.py` |
| `streamer.py` | → `capabilities_stream_monitor.py` |
| `browser.py` | → `capabilities_browser_adapter.py` |
| `qwen_client.py` | **file tidak ada sama sekali** |

Ditambah `TEST.md:188` masih menyebut `test_qwen_client_behavior.py` yang juga tidak ada.

**Kenapa ini lebih penting dari kelihatannya:** TEST.md memposisikan diri sebagai *"behavior regression lock"* dan *"single source of truth"*. Dokumen yang mengklaim jadi source of truth tapi menunjuk 6 file hantu itu lebih berbahaya daripada tidak ada dokumen — developer baru (atau agent swarm berikutnya) akan mengikutinya dan tersesat. Ironisnya, swarm ini sendiri kemungkinan besar terganggu oleh TEST.md yang basi.

**Ini pekerjaan dokumentasi murni, zero risk, dan langsung meningkatkan kualitas semua review swarm berikutnya.** Nilai leverage-nya tinggi meski labelnya cuma WARNING.

---

### 🟡 #271 (BE-5-003) — Tidak ada tes path traversal/symlink MCP

**Sebagian sudah ada.** `tests/unit_mcp_hardening.py:16-27` sudah punya `test_prompt_path_rejects_files_outside_workspace` yang memakai `QWEN_WORKSPACE_ROOT` dan mengecek `PATH_OUTSIDE_WORKSPACE`. Jadi klaim *"no test covers the `QWEN_WORKSPACE_ROOT` environment variable override path"* **tidak akurat**.

**Yang benar-benar belum ada:**
- Tes symlink escape (symlink di dalam workspace → `/etc/passwd`)
- Tes traversal `..`
- Tes untuk `_validate_attachment_path` (hanya `_validate_prompt_path` yang diuji)
- Tes ketika root sendiri adalah symlink

Analisis issue soal `Path.resolve()` sudah benar: karena `resolve()` mengikuti symlink **sebelum** `relative_to(root)`, kode saat ini sebenarnya **sudah aman**. Jadi ini menambahkan tes untuk perilaku yang sudah benar — nilainya sebagai **kunci regresi**, bukan menambal lubang.

**Verdict:** kerjakan, murah, dan ini permukaan keamanan. Tapi jangan bikin file baru `tests/test_mcp_path_validation.py` — repo ini pakai konvensi penamaan `unit_*` / `integration_*` tanpa prefix `test_`. Masukkan ke `tests/unit_mcp_hardening.py` yang sudah ada. Patch usulan melanggar konvensi repo.

⚠️ **Issue #271 juga membawa muatan ekstra:** body-nya berisi *Open Questions*, *Violations*, *Action Items*, *Fixed Code*, dan tabel *Severity* untuk **seluruh review** — bukan hanya BE-5-003. Jadi #271 sebenarnya adalah ringkasan laporan yang ter-import jadi issue biasa. Sebaiknya bagian itu dipecah ke issue tracking terpisah (atau jadi meta-issue) supaya tidak hilang.

---

### 🔵 #262 (BE-2-003) — Filter `.tmp_` pakai substring

**Kode aktual (line 77):** `if ".tmp_" in path.name: continue` — terkonfirmasi.

**Pola temp file sebenarnya (`utility_core_io_writer.py:31`):**
```python
tmp_path = target.with_suffix(f".tmp_{target.name}")
```
Untuk `file_123.json` → `with_suffix(".tmp_file_123.json")` → hasilnya `file_123.tmp_file_123.json`.

**Patch usulan salah.** Issue mengusulkan:
```python
if path.name.startswith(".tmp_") or ".tmp_" in path.stem:
```
- `path.name.startswith(".tmp_")` → **tidak pernah true**, karena temp file bernama `file_123.tmp_file_123.json`, bukan `.tmp_...`.
- `".tmp_" in path.stem` → stem dari `file_123.tmp_file_123.json` adalah `file_123.tmp_file_123`, yang mengandung `.tmp_` → true. Tapi ini **persis substring check yang sama**, cuma dipindah ke `.stem`. Job bernama `batch.tmp_cleanup` tetap akan tersaring — **masalah aslinya tidak terselesaikan**.

Jadi patch ini tidak memperbaiki apa pun.

**Ditambah:** job ID digenerate internal dan tidak pernah mengandung `.tmp_` (lihat #260). Jadi bug ini tidak bisa dipicu dari jalur normal.

**Verdict:** **tutup sebagai won't-fix**, atau kalau mau benar, solusinya adalah mengubah `_atomic_write` supaya pakai direktori temp terpisah / prefix yang tidak ambigu, bukan menambal filter. Jangan merge patch yang ada.

---

### 🔵 #268 (BE-4-003) — `lru_cache` blokir hot-reload template

**Terkonfirmasi:** `utility_core_prompt_template.py:25` → `@lru_cache(maxsize=1)` pada `_discovered_roles()`.

Analisisnya tepat: untuk CLI (proses sekali jalan) ini benar dan optimal. Untuk MCP server yang long-running, template `.md` baru tidak akan terlihat sampai server di-restart.

**Pertanyaannya adalah produk, bukan teknis:** apakah "tambah template saat server hidup" itu use case nyata bagi kita? Kalau template jarang berubah, restart MCP server itu murah dan `lru_cache` lebih baik (nol overhead, deterministik). Kalau kita membayangkan user mengarang template sambil agent jalan, TTL cache masuk akal.

**Catatan patch:** patch usulan memakai `global` + `import time` **di dalam fungsi**, yang jelek secara gaya dan kemungkinan besar akan ditolak linter repo (`lint_arwaky.config.yaml`). Kalau dikerjakan, pakai pendekatan yang lebih bersih (mis. cek `mtime` direktori, atau fungsi `invalidate_template_cache()` eksplisit).

---

### 🔵 #402 (BE-1-003) — Validasi `--text` kosong terlambat

**Terkonfirmasi (`root_cli_main_entry.py:215`):**
```python
inline_prompt_text=text if action == "prompt-direct" else None,
```
Tidak ada cek empty/whitespace. Validasi baru terjadi di `dispatch_run` dengan pesan generik.

**Dampak:** `qwen-web-arwaky prompt-direct -t ""` akan membangun config, menginisialisasi observability, baru gagal. Boros dan pesan errornya tidak memenuhi standar "what/why/how-to-fix" yang kita tulis sendiri di CLI FRD NFR.

**Catatan:** ini satu-satunya issue dengan nomor jauh (#402 vs #258-271), padahal ID-nya `BE-1-003` yang seharusnya berurutan setelah #259 (`BE-1-002`). Kemungkinan ter-import ulang/terlambat. Perlu dicek apakah ada duplikatnya.

Prioritas rendah tapi fix-nya sepele (~6 baris) dan langsung memperbaiki UX CLI.

---

## 3. Penilaian Kualitas Review Swarm Ini

Ini penting supaya kita tahu seberapa jauh boleh percaya output swarm berikutnya.

**Yang bagus:**
- Semua 15 issue menunjuk file & fungsi yang **benar-benar ada** — tidak ada halusinasi lokasi.
- Temuan #264, #258, #259, #269 akurat dan berguna.
- Setiap issue punya acceptance criteria — bisa langsung jadi definition of done.

**Yang harus diwaspadai:**
- **3 patch usulan salah atau merugikan** (#262 tidak memperbaiki apa pun, #261 mengubah semantik API, #270 test-nya tidak mendeteksi race yang dituju).
- **Angka dilebih-lebihkan** (#267 salah baca 500ms jadi 200ms; #271 mengklaim tes tidak ada padahal sebagian ada).
- **Severity meleset.** #263 dilabeli CRITICAL padahal efeknya degradasi akurasi; #262 dan #265 secara praktis tidak bisa dipicu. Sementara #269 (dokumen source-of-truth yang menyesatkan) cuma WARNING padahal leverage-nya tinggi.
- **Konvensi repo diabaikan** — patch mengusulkan `tests/test_*.py` padahal repo pakai `unit_*.py` / `integration_*.py`.

**Kesimpulan:** perlakukan output swarm sebagai **petunjuk lokasi masalah yang bagus, tapi patch-nya harus selalu direview manual.** Jangan pernah auto-merge diff dari issue ini.

---

## 4. Rekomendasi Prioritas

Diurutkan berdasarkan (dampak nyata × kepastian) ÷ effort — **bukan** berdasarkan label severity dari swarm.

### Gelombang 1 — kerjakan sekarang (total ~2-3 jam)
| # | Alasan |
|---|--------|
| **#264** | Satu-satunya bug yang benar-benar menghasilkan status salah + exception path. Reproducible. |
| **#258** | 2 baris, backward compatible, menutup pelanggaran kontrak API. |
| **#259** | Kemampuan sudah ada di core, tinggal disambung. Rasio benefit/effort tertinggi. |
| **#269** | Zero risk, dan memperbaiki source-of-truth yang menyesatkan semua pekerjaan berikutnya. |

### Gelombang 2 — cycle ini (~4-6 jam)
| # | Alasan |
|---|--------|
| **#263** | Benarkan thread-safety. Prasyarat untuk #270. |
| **#270** | Kunci regresi, **tapi tulis ulang test-nya**, jangan pakai patch issue. |
| **#271** | Tes keamanan, murah. Masukkan ke `unit_mcp_hardening.py`. |
| **#266** | Buang kerja mubazir 2× per poll. Pakai parameter, bukan inline. |

### Gelombang 3 — kalau ada waktu
#402 (UX cepat) · #260 (hardening) · #268 (butuh keputusan produk dulu) · #267 (optimisasi murni)

### Tutup / tolak patch
- **#262** — tutup won't-fix. Patch usulan tidak memperbaiki apa pun, dan bug tidak bisa dipicu.
- **#261** — downgrade ke INFO, ambil docstring-nya saja, **tolak backfill loop**.
- **#265** — downgrade ke INFO, kerjakan sebagai refactor oportunistik.

---

## 5. Pertanyaan yang Butuh Keputusanmu

Empat hal ini tidak bisa aku putuskan sendiri karena menyangkut arah produk, bukan benar/salah teknis.

1. **`output_file` untuk `process_direct_prompt` (#259).** Agent sendiri bertanya apakah direct prompt memang sengaja dibuat ephemeral. Kalau desainnya memang "direct = sekali pakai, tidak disimpan", maka #259 bukan bug melainkan keputusan sadar dan harus ditutup. Kalau tujuannya paritas penuh CLI↔MCP, maka kerjakan.

2. **Perilaku `RateLimiter` saat limit tercapai.** Sekarang `acquire()` **memblokir** thread. Untuk MCP, ini berarti tool call menggantung sampai kuota tersedia — client bisa timeout tanpa pesan jelas. Alternatifnya kembalikan error `RATE_LIMITED` + `retry_after` supaya agent bisa menunggu sendiri. Ini mengubah kontrak API, jadi butuh keputusan.

3. **Penyimpanan `JobManager`: file-per-JSON atau SQLite.** Issue #260, #261, #262 semuanya adalah gejala dari desain file-per-job. Kalau kita pindah ke SQLite, ketiganya hilang sekaligus dan kita dapat atomicity gratis. Tapi kita kehilangan inspectability (`cat job.json`) yang mungkin memang sengaja dipilih. Tambal satu-satu, atau ganti fondasinya?

4. **Hot-reload template (#268).** Apakah "user menambah template `.md` saat MCP server hidup" itu skenario nyata? Kalau tidak, `lru_cache` sudah benar dan issue ditutup. Kalau iya, kita bayar kompleksitas cache invalidation.

5. **Lingkup eksekusi.** Apakah kamu ingin satu PR besar berisi Gelombang 1, atau satu PR per issue supaya review dan revert lebih gampang?

---

*Catatan: analisis ini murni membaca kode — belum ada satu baris pun yang diubah di repo.*
