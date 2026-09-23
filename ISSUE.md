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

## Catatan lingkungan

- Worktree main: `/tmp/qwa-latest` (editable, v6.4.0). Worktree v6.3.0:
  `/tmp/qwa-630`; v6.3.1: `/tmp/qwa-631`.
- Non-headless swarm: `QWA_SWARM_HEADLESS=0`.
- Captcha: `Access Verification` / PUZZLE (`static-captcha-sgp.aliyuncs.com`).
