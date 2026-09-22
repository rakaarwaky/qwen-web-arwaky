"""Unit tests: import-aware folder compilation (multi-language)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.core.src.capabilities_folder_compiler import FolderCompiler
from modules.shared.src.utility_folder_compiler import (
    collect_folder_files,
    collect_folder_files_with_imports,
    compile_files_to_markdown,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _clear_workspace_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep boundary tests hermetic: a stray QWEN_WORKSPACE_ROOT in the CI or
    developer environment must not shrink the default boundary for the legacy
    tests above (they rely on the folder-parent fallback)."""
    monkeypatch.delenv("QWEN_WORKSPACE_ROOT", raising=False)


class TestCollectFolderFilesWithImports:
    def test_python_import_from_outside_folder(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        ext = tmp_path / "utils"
        _write(target / "a.py", "from utils.helper import run\n\ndef main():\n    run()\n")
        _write(ext / "helper.py", "def run():\n    print('hi')\n")

        files, origins = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert "a.py" in names
        assert "helper.py" in names
        helper = next(f for f in files if f.name == "helper.py")
        assert origins[helper] == ("a.py",)

    def test_python_relative_import(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "pkg" / "a.py", "from .util import x\n")
        _write(target / "pkg" / "util.py", "x = 1\n")
        files, _ = collect_folder_files_with_imports(target)
        assert any(f.name == "util.py" for f in files)

    def test_js_import_from_outside(self, tmp_path: Path) -> None:
        target = tmp_path / "app"
        lib = tmp_path / "lib"
        _write(target / "index.js", "import { helper } from '../lib/helper';\nconsole.log(helper());\n")
        _write(lib / "helper.js", "export function helper() { return 1; }\n")
        files, origins = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert "index.js" in names
        assert "helper.js" in names

    def test_c_include_from_outside(self, tmp_path: Path) -> None:
        target = tmp_path / "src"
        inc = tmp_path / "include"
        _write(target / "main.c", '#include "../include/header.h"\nint main() { return 0; }\n')
        _write(inc / "header.h", "#ifndef HEADER_H\n#define HEADER_H\n#endif\n")
        files, _ = collect_folder_files_with_imports(target)
        assert any(f.name == "header.h" for f in files)

    def test_cycle_protection(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "a.py", "import b\n")
        _write(tmp_path / "b.py", "import a\n")
        files, _ = collect_folder_files_with_imports(target)
        # a.py in folder, b.py imported once (no infinite loop)
        assert [f.name for f in files].count("b.py") == 1

    def test_import_depth_limit(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "a.py", "import m1\n")
        _write(tmp_path / "m1.py", "import m2\n")
        _write(tmp_path / "m2.py", "import m3\n")
        _write(tmp_path / "m3.py", "x = 1\n")
        files, _ = collect_folder_files_with_imports(target, import_depth=1)
        names = {f.name for f in files}
        assert "m1.py" in names
        assert "m2.py" not in names  # beyond import_depth=1
        files2, _ = collect_folder_files_with_imports(target, import_depth=3)
        assert "m3.py" in {f.name for f in files2}

    def test_rust_crate_import_from_outside(self, tmp_path: Path) -> None:
        # crate root = rust_project/ (Cargo.toml); folder target = src/
        # models.rs/user.rs di dalam folder; shared/util.rs DI LUAR folder
        crate = tmp_path / "rust_project"
        _write(crate / "Cargo.toml", '[package]\nname="demo"\n')
        _write(crate / "src" / "main.rs", "mod models;\nuse crate::shared::util;\nfn main() { util::run(); }\n")
        _write(crate / "src" / "models.rs", "pub mod user;\n")
        _write(crate / "src" / "models" / "user.rs", "pub struct User;\n")
        _write(crate / "shared" / "util.rs", "pub fn run() {}\n")

        files, origins = collect_folder_files_with_imports(crate / "src")
        names = {f.name for f in files}
        assert {"main.rs", "models.rs", "user.rs", "util.rs"} <= names
        util = next(f for f in files if f.name == "util.rs")
        assert origins[util] == ("main.rs",)

    def test_typescript_import_from_outside(self, tmp_path: Path) -> None:
        target = tmp_path / "app"
        shared = tmp_path / "shared"
        _write(target / "main.ts", "import { format } from '../shared/format';\nformat(1);\n")
        _write(shared / "format.ts", "export function format(n: number) { return n.toFixed(2); }\n")
        files, _ = collect_folder_files_with_imports(target)
        assert any(f.name == "format.ts" for f in files)

    def test_tsconfig_path_alias_from_outside(self, tmp_path: Path) -> None:
        # tsconfig: "@lib/*" -> "lib/*" (baseUrl = project root)
        project = tmp_path / "ts_project"
        _write(project / "tsconfig.json", '{"compilerOptions": {"baseUrl": ".", "paths": {"@lib/*": ["lib/*"]}}}')
        _write(project / "src" / "main.ts", "import { helper } from '@lib/helper';\nhelper();\n")
        _write(project / "lib" / "helper.ts", "export function helper() { return 1; }\n")

        files, origins = collect_folder_files_with_imports(project / "src")
        names = {f.name for f in files}
        assert "main.ts" in names
        assert "helper.ts" in names
        helper = next(f for f in files if f.name == "helper.ts")
        assert origins[helper] == ("main.ts",)

    def test_tsconfig_exact_alias(self, tmp_path: Path) -> None:
        # alias tanpa wildcard: "utils" -> "lib/utils.ts"
        project = tmp_path / "ts_project"
        _write(project / "tsconfig.json", '{"compilerOptions": {"baseUrl": ".", "paths": {"utils": ["lib/utils.ts"]}}}')
        _write(project / "src" / "main.ts", "import { x } from 'utils';\n")
        _write(project / "lib" / "utils.ts", "export const x = 1;\n")

        files, _ = collect_folder_files_with_imports(project / "src")
        assert any(f.name == "utils.ts" for f in files)

    def test_external_stdlib_not_included(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "a.py", "import os\nimport json\n")
        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert names == {"a.py"}


class TestCompileMarkdownOrigins:
    def test_external_file_marked_imported_by(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "a.py", "from utils.helper import run\n")
        _write(tmp_path / "utils" / "helper.py", "def run(): pass\n")

        files, origins = collect_folder_files_with_imports(target)
        md = compile_files_to_markdown(files, target, origins=origins)
        assert "*(imported by a.py)*" in md
        assert "../utils/helper.py" in md


class TestFolderCompilerImportAware:
    def test_compile_folder_include_imports(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "a.py", "from utils.helper import run\nrun()\n")
        _write(tmp_path / "utils" / "helper.py", "def run(): pass\n")

        compiler = FolderCompiler(input_dir=tmp_path / "out")
        out = compiler.compile_folder(target, include_imports=True)
        content = out.read_text(encoding="utf-8")
        assert "helper.py" in content
        assert "imported by" in content

    def test_compile_folder_without_imports(self, tmp_path: Path) -> None:
        target = tmp_path / "target"
        _write(target / "a.py", "from utils.helper import run\n")
        _write(tmp_path / "utils" / "helper.py", "def run(): pass\n")

        compiler = FolderCompiler(input_dir=tmp_path / "out")
        out = compiler.compile_folder(target, include_imports=False)
        content = out.read_text(encoding="utf-8")
        assert "helper.py" not in content

    def test_compile_folder_follows_markdown_links(self, tmp_path: Path) -> None:
        target = tmp_path / "docs_pack"
        _write(target / "README.md", "# Pack\n\nSee [the API](../reference/api.md).\n")
        _write(tmp_path / "reference" / "api.md", "# API\n\nEndpoint list.\n")

        compiler = FolderCompiler(input_dir=tmp_path / "out")
        out = compiler.compile_folder(target)
        content = out.read_text(encoding="utf-8")
        assert "../reference/api.md" in content
        assert "*(imported by README.md)*" in content
        assert "Endpoint list." in content


class TestMarkdownLinkChain:
    def test_inline_link_from_outside_folder(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "index.md", "Read [the guide](../shared/guide.md) first.\n")
        _write(tmp_path / "shared" / "guide.md", "# Guide\n\nbody\n")

        files, origins = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert {"index.md", "guide.md"} <= names
        guide = next(f for f in files if f.name == "guide.md")
        assert origins[guide] == ("index.md",)

    def test_markdown_chains_through_two_hops(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "index.md", "[a](../ref/api.md)\n")
        _write(tmp_path / "ref" / "api.md", "[b](./details.md)\n")
        _write(tmp_path / "ref" / "details.md", "deep detail\n")

        # Default import_depth=1: api.md is included (hop 1), details.md is not (hop 2).
        files, origins = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert {"index.md", "api.md"} <= names
        assert "details.md" not in names

        # Explicit import_depth=3: details.md is included (hop 2).
        files2, _ = collect_folder_files_with_imports(target, import_depth=3)
        assert "details.md" in {f.name for f in files2}

    def test_anchor_and_query_stripped(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "[x](../ref/api.md#section) and [y](../ref/b.md?q=1)\n")
        _write(tmp_path / "ref" / "api.md", "api\n")
        _write(tmp_path / "ref" / "b.md", "b\n")

        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert {"api.md", "b.md"} <= names

    def test_external_urls_and_bare_anchors_skipped(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(
            target / "a.md",
            "[site](https://example.com/docs/x.md) [mail](mailto:a@b.c) [top](#intro) [rel](../ref/real.md)\n",
        )
        _write(tmp_path / "ref" / "real.md", "real\n")
        _write(tmp_path / "ref" / "x.md", "must not be picked by the url\n")

        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert "real.md" in names
        assert "x.md" not in names

    def test_image_embeds_not_collected(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "![diagram](../assets/arch.png) [doc](../ref/real.md)\n")
        _write(tmp_path / "assets" / "arch.png", "\x89PNG\r\n\x1a\n fake png ")
        _write(tmp_path / "ref" / "real.md", "real\n")

        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert "real.md" in names
        assert "arch.png" not in names

    def test_link_inside_code_block_ignored(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(
            target / "a.md",
            "Docs live elsewhere.\n\n```markdown\nexample [x](../ref/secret.md)\n```\n\n"
            "~~~\nanother [y](../ref/other.md)\n~~~\n",
        )
        _write(tmp_path / "ref" / "secret.md", "hidden\n")
        _write(tmp_path / "ref" / "other.md", "hidden\n")

        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert names == {"a.md"}

    def test_reference_style_definition(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", 'See [the spec][spec-id].\n\n[spec-id]: ../ref/spec.md "Title"\n')
        _write(tmp_path / "ref" / "spec.md", "spec\n")

        files, origins = collect_folder_files_with_imports(target)
        spec = next(f for f in files if f.name == "spec.md")
        assert origins[spec] == ("a.md",)

    def test_inline_yaml_link_outside_folder(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "See the deployment config: [config](../ref/deployment.yaml)\n")
        _write(tmp_path / "ref" / "deployment.yaml", "apiVersion: v1\nkind: ConfigMap\n")

        files, origins = collect_folder_files_with_imports(target)
        config = next(f for f in files if f.name == "deployment.yaml")
        assert origins[config] == ("a.md",)

    def test_reference_style_yml_link_outside_folder(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(
            target / "a.md",
            "See [the compose config][compose].\n\n[compose]: ../ref/docker-compose.yml\n",
        )
        _write(tmp_path / "ref" / "docker-compose.yml", "services:\n  app:\n    image: example\n")

        files, origins = collect_folder_files_with_imports(target)
        config = next(f for f in files if f.name == "docker-compose.yml")
        assert origins[config] == ("a.md",)

    def test_angle_bracket_target_with_space(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "[x](<../ref/my file.md>) [y](../ref/percent%20name.md)\n")
        _write(tmp_path / "ref" / "my file.md", "spaced\n")
        _write(tmp_path / "ref" / "percent name.md", "encoded\n")

        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert {"my file.md", "percent name.md"} <= names

    def test_directory_link_resolves_index(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "[guide](../guide/) and [readme](../manual/)\n")
        _write(tmp_path / "guide" / "index.md", "index body\n")
        _write(tmp_path / "manual" / "README.md", "readme body\n")

        files, _ = collect_folder_files_with_imports(target)
        names = {f.name for f in files}
        assert {"index.md", "README.md"} <= names

    def test_wikilink_resolves_folder_wide_by_stem(self, tmp_path: Path) -> None:
        # Index.md sits in a subfolder; the stem-only wikilink still finds it.
        target = tmp_path / "vault"
        _write(target / "a.md", "See [[Setup]] and [[nested/Deep|deep dive]].\n")
        _write(target / "nested" / "Deep.md", "deep\n")
        _write(target / "notes" / "Setup.md", "setup\n")

        files, _ = collect_folder_files_with_imports(target)
        assert {f.name for f in files} == {"a.md", "Deep.md", "Setup.md"}

    def test_wikilink_without_extension_outside_folder(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "Link target is extension-less: [[../shared/Setup]]\n")
        _write(tmp_path / "shared" / "Setup.md", "setup\n")

        files, origins = collect_folder_files_with_imports(target)
        setup = next(f for f in files if f.name == "Setup.md")
        assert origins[setup] == ("a.md",)

    def test_markdown_cycle_protection(self, tmp_path: Path) -> None:
        target = tmp_path / "docs"
        _write(target / "a.md", "[b](../ref/b.md)\n")
        _write(tmp_path / "ref" / "b.md", "[a](../docs/a.md)\n")

        files, _ = collect_folder_files_with_imports(target)
        assert [f.name for f in files].count("b.md") == 1


class TestImportBoundaryConfinement:
    """Issue #342: import resolution must not escape the workspace boundary.

    The compiled markdown is uploaded to a third-party service; following an
    import/reference outside the workspace would silently exfiltrate files.
    """

    def test_import_outside_explicit_boundary_refused(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        target = ws / "target"
        _write(target / "a.py", "from ...secrets.cfg import KEY\nprint(KEY)\n")
        _write(tmp_path / "secrets" / "cfg.py", "KEY = 'hunter2'\n")

        skipped: list[Path] = []
        files, _ = collect_folder_files_with_imports(target, boundary_root=ws, skipped=skipped)
        assert {f.name for f in files} == {"a.py"}
        assert [p.name for p in skipped] == ["cfg.py"]

    def test_import_inside_explicit_boundary_kept(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        target = ws / "target"
        _write(target / "a.py", "from utils.helper import run\nrun()\n")
        _write(ws / "utils" / "helper.py", "def run(): pass\n")

        files, origins = collect_folder_files_with_imports(target, boundary_root=ws)
        helper = next(f for f in files if f.name == "helper.py")
        assert origins[helper] == ("a.py",)

    def test_env_workspace_root_confines_imports(self, tmp_path: Path, monkeypatch) -> None:
        ws = tmp_path / "ws"
        target = ws / "target"
        _write(target / "a.py", "from ...secrets.cfg import KEY\n")
        _write(tmp_path / "secrets" / "cfg.py", "KEY = 'hunter2'\n")
        monkeypatch.setenv("QWEN_WORKSPACE_ROOT", str(ws))

        files, _ = collect_folder_files_with_imports(target)
        assert {f.name for f in files} == {"a.py"}

    def test_default_parent_boundary_blocks_far_escape(self, tmp_path: Path, monkeypatch) -> None:
        """Without env/param the boundary is folder.parent: ../.. escapes are refused."""
        monkeypatch.delenv("QWEN_WORKSPACE_ROOT", raising=False)
        ws = tmp_path / "ws"
        target = ws / "target"
        _write(target / "a.py", "from ...evil import payload\n")  # resolves to tmp_path/evil.py
        _write(tmp_path / "evil.py", "payload = 1\n")

        skipped: list[Path] = []
        files, _ = collect_folder_files_with_imports(target, skipped=skipped)
        assert {f.name for f in files} == {"a.py"}
        assert [p.name for p in skipped] == ["evil.py"]

    def test_markdown_exfiltration_link_refused(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        docs = ws / "docs"
        _write(docs / "a.md", "See [config](../../secrets/deployment.yaml)\n")
        _write(tmp_path / "secrets" / "deployment.yaml", "password: hunter2\n")

        skipped: list[Path] = []
        files, _ = collect_folder_files_with_imports(docs, boundary_root=ws, skipped=skipped)
        assert {f.name for f in files} == {"a.md"}
        assert [p.name for p in skipped] == ["deployment.yaml"]

    def test_symlinked_import_resolves_out_of_boundary(self, tmp_path: Path) -> None:
        """A candidate inside the boundary by name but symlinked outside is refused
        (candidates are resolved before the boundary check)."""
        ws = tmp_path / "ws"
        target = ws / "target"
        _write(target / "a.py", "import linked\n")
        outside = _write(tmp_path / "real_secret.py", "TOKEN = 'abc'\n")
        link = ws / "linked.py"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("symlinks not supported on this platform")

        skipped: list[Path] = []
        files, _ = collect_folder_files_with_imports(target, boundary_root=ws, skipped=skipped)
        assert "linked.py" not in {f.name for f in files}
        assert "real_secret.py" not in {f.name for f in files}

    def test_base_folder_files_never_refused(self, tmp_path: Path) -> None:
        """The boundary only constrains *imported* files, not the scanned folder itself."""
        ws = tmp_path / "ws"
        target = ws / "target"
        target.mkdir(parents=True)
        _write(target / "a.py", "x = 1\n")
        _write(target / "b.py", "y = 2\n")

        files, _ = collect_folder_files_with_imports(target, boundary_root=target)
        assert {f.name for f in files} == {"a.py", "b.py"}

    def test_secret_and_env_files_excluded_from_compilation(self, tmp_path: Path) -> None:
        """Secret files (.env, .pem, .key) must be automatically excluded from compilation."""
        target = tmp_path / "app"
        target.mkdir(parents=True)
        _write(target / "main.py", "import os\n")
        _write(target / ".env", "SECRET=123\n")
        _write(target / ".env.local", "SECRET=local\n")
        _write(target / "cert.pem", "---CERT---\n")
        _write(target / "id_rsa", "---KEY---\n")

        files = collect_folder_files(target)
        assert [f.name for f in files] == ["main.py"]
