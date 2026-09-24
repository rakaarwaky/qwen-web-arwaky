#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON:-python}"

"$python_bin" -m pytest -q \
  modules/core/tests/unit_browser_adapter.py::test_clean_stale_locks \
  modules/core/tests/unit_capability_file_uploader.py::TestValidateFile::test_file_too_large \
  modules/core/tests/unit_capability_output_saver.py::TestWriteFileAtomic::test_atomic_write \
  modules/core/tests/unit_capability_prompt_injector.py::TestInjectTextStrategies::test_empty_text_raises \
  modules/core/tests/unit_capability_send_dispatcher.py::test_ack_observed_via_user_bubble_count \
  modules/core/tests/unit_capability_stream_monitor.py::TestWaitForResponseEdgeCases::test_returns_stable_text \
  modules/cli/tests/integration_surface_init_cmd.py \
  modules/core/tests/unit_observability_stderr.py::test_cli_mode_still_attaches_stderr_handler \
  modules/core/tests/unit_folder_compiler.py::TestFolderCompilerImportAware::test_compile_folder_include_imports \
  modules/core/tests/unit_capability_job_manager.py::TestJobManager::test_save_and_get_job \
  modules/core/tests/integration_parallel_jobs.py::test_agent_job_orchestrator_runs_n_jobs_in_parallel \
  modules/cli/tests/unit_surface_cli_tui_app.py \
  modules/cli/tests/unit_surface_cli_update_command.py \
  modules/core/tests/unit_agent_swarm_orchestrator.py::test_swarm_retries_transient_agent_failure_and_allows_partial
