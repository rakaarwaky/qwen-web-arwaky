# v5.0.0 Release Verification — Prompt-Only (Pipeline 2)

This is a release-verification fixture for **qwen-web-arwaky v5.0.0**.

## Task
Jawab dalam satu kalimat: sebutkan 3 warna pelangi dalam bahasa Indonesia.

## Verification Purpose
Memastikan pipeline `prompt-only` (file tanpa attachment) tetap berfungsi
pada rilis 5.0.0 setelah refactor `SharedFlowOrchestrator` dan perbaikan
AES (0 violations). Jawaban singkat mempercepat validasi e2e.
