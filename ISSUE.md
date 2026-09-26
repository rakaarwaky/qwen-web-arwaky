# ISSUE: Large-attachment send regresi (main vs v6.3.0)

## Status ter-verify (manual, non-headless, attachment 16KB = swarm input)

| Versi | Bot-verification (captcha) | Hasil pipeline prompt-with-attachment |
| --- | --- | --- |
| **v6.3.0** | tidak muncul | **BERHASI end-to-end** — menunggu sabar sampai parsing selesai, send, ACK, output ter-copy |
| **v6.3.1** | tidak muncul | **gagal `SendDispatchError`** — tidak menunggu parsing selesai dengan benar |
| **main latest** (PR #420/#421/#422) | **muncul saat swarm** | **gagal `SendDispatchError`** — tidak menunggu parsing selesai dengan benar |

Catatan:
- v6.3.0 dan v6.3.1 sama-sama bebas bot-verification (kode send-path keduanya identik).
- Hanya v6.3.0 yang terverifikasi sukses end-to-end di pipeline prompt-with-attachment.
- Bot-verification hanya muncul di main **saat swarm 10-parallel** (user memantau 10 tab
  non-headless); saat attachment tunggal main kadang sukses (38s) dan kadang gagal —
  transien, bergantung kondisi parse-rate Qwen.

## Gejala di main / v6.3.1

- `SendDispatchError: Send control dispatch timed out waiting for document parsing
  or user turn ACK`.
- Di trace: `FILE_UPLOADED` → `DOCUMENT_PARSED` fire, `PROMPT_INJECTED` fire, tapi
  stage send/klik-send tidak sampai ACK.

## Akar masalah (hipotesis terkuat)

Klien main **tidak menunggu parse Qwen selesai dengan benar** sebelum meng-click send,
lalu melakukan re-click send berulang (loop ACK + Enter fallback + re-click saat toast
"still parsing"). Akibat:
- send ter-click saat Qwen belum commit turn → ACK tak teramati → timeout →
  `SendDispatchError`.
- Re-click agresif + concurrency-10 swarm memicu risk-control Qwen →
  **bot-verification (PUZZLE captcha)** muncul; halaman pindah ke captcha,
  user-bubble tak pernah commit.

Perilaku v6.3.0: menunggu sabar sampai document selesai di-parse (tanpa re-click
agresif), sehingga bebas captcha dan berhasil.

## Yang harus di-verify / dikerjakan

- [ ] Bandingkan perilaku kirim-send v6.3.0 vs v6.3.1 vs main secara pasti
      (apa yang membuat main/v6.3.1 tidak menunggu parsing dengan benar).
      Catatan: diff kode send-path v6.3.0 vs v6.3.1 = kosong (identik), jadi
      perbedaan hasil kemungkinan karena kondisi Qwen saat test, BUKAN kode.
- [ ] Perbaiki agar main menunggu parsing selesai sebelum send (meniru v6.3.0):
      hentikan re-click send agresif saat card/toast parsing masih aktif.
- [ ] Mitigasi captcha di swarm: backoff antar-agent, kurangi concurrency,
      jeda antar-klik-send; deteksi captcha → hentikan run alih-alih loop.
- [ ] Pastikan gate-reject tetap retryable tanpa memicu re-click berulang.
- [ ] Re-dogfood: attachment tunggal + swarm 10-role sampai 10/10 tanpa
      bot-verification.

## Terselesaikan: thinking card ter-scrape sebagai jawaban (PR #461, 2026-09-26)

Run `20260926_014817_5cd3cc` menulis output 32 byte berisi hanya `Thought stopped`
padahal Qwen masih thinking. Dua sebab, keduanya sudah diperbaiki dan diverifikasi:

1. **Kartu thinking jadi "jawaban".** `JS_GET_RESPONSE_TEXT` tidak menyaring kartu
   thinking yang render di dalam container assistant-message yang sama. Begitu fase
   thinking selesai, `innerText` kartu itu berubah jadi status line pendek
   (`Thought stopped`), dan monitor stabilize di atas kartu — bukan jawaban asli.
   Perbaikan: array `THINKING_CARD_MARKERS` di dalam JS; node yang seluruh teksnya
   persis salah satu marker di-skip, scanner lanjut ke node lebih lama.

2. **Ceiling 120s memotong fase thinking yang masih hidup.** `request_timeout`
   diperlakukan stream monitor sebagai *wall-clock ceiling* (`elapsed >= timeout_sec`),
   bukan idle budget. Fase thinking panjang tidak emit forward event selama
   durasinya, jadi ceiling 120s lebih dulu menembus dari stall detector 300s.
   Perbaikan: default `request_timeout` 120 → 600s di tiga call site, plus env
   override `QWEN_REQUEST_TIMEOUT_SEC` (nilai invalid/tidak-positif jatuh ke default).

Verifikasi setelah merge — run `20260926_023444_f5705c` dengan input yang sama:

| Metrik | Sebelum (1215cd3c… / 014817) | Sesudah (023444_f5705c) |
| --- | --- | --- |
| Hard timeout | 120s | 600s |
| Elapsed sampai stabil | 120s (terbunuh) | 426s (selesai normal) |
| Output | 32 byte (`Thought stopped`) | 40,718 byte (15 issue report) |
| Stabil pada | thinking card | jawaban asli |

Regression test: 6 marker-sanity + 5 env-override + 2 live-Chromium DOM
(`TestThinkingCardIsNotAnAnswer`, `TestRequestTimeoutBudget`,
`TestThinkingCardDomExtraction`) di `modules/core/tests/unit_capability_stream_monitor.py`.
Total suite: 809 passed, 1 xfailed.

Belum terselesaikan dari kasus ini: **thinking *detection* masih salah baca** —
`is_thinking_active` hanya mengenali teks yang mengandung `"thinking"`, sehingga
kartu berstatus `Thought stopped` terbaca sebagai "tidak thinking" (that's why the
TUI showed "streaming" while Qwen was thinking). Status *display* itu belum
diperbaiki; yang diperbaiki adalah sampling output-nya. Jika TUI masih menampilkan
"streaming" saat model berpikir, selector thinking-card perlu diperluas.

## Catatan lingkungan

- Worktree main: `/tmp/qwa-latest` (editable, v6.4.0). Worktree v6.3.0:
  `/tmp/qwa-630`; v6.3.1: `/tmp/qwa-631`.
- Non-headless swarm: `QWA_SWARM_HEADLESS=0`.
- Captcha: `Access Verification` / PUZZLE (`static-captcha-sgp.aliyuncs.com`).
