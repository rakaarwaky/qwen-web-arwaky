"""Unit tests: import-aware folder compilation (multi-language)."""

from __future__ import annotations

from pathlib import Path

from modules.core.src.capabilities_folder_compiler import FolderCompiler
from modules.shared.src.utility_folder_compiler import (
    collect_folder_files_with_imports,
    compile_files_to_markdown,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


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
