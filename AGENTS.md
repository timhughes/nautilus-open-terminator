# AI Agent & Contributor Workflow

This repository uses a structured multi-agent workflow. Any AI agent working in this repository **must** follow these conventions and spawn the specialized subagents below before concluding work.

## Repository Layout

- `src/open-terminator.py` — Nautilus (`4.0` / `3.0`) Python extension.
- `tests/` — Standard-library `unittest` suite (`make check`).
- `po/` — `gettext` `.pot` template and `.po` translations (`make` compiles to `locale/`).
- `io.github.timhughes.nautilus_open_terminator.metainfo.xml` — AppStream metadata.
- `Makefile` — Build, test (`make check`), and install (`install`, `install-user`) rules.
- `debian/`, `nautilus-open-terminator.spec`, `PKGBUILD` — Distro packaging for Debian, Fedora, and Arch Linux.
- `.github/workflows/release.yml` — CI builds for Debian, Fedora, and Arch, plus automated GitHub Releases on `v*` tags.

## Required Subagent Workflow

1. **Peer Reviewer Subagent (`peer-reviewer`)**
   - **When:** After any code, packaging, metadata, or CI change.
   - **Responsibilities:**
     - Verify GNOME & Nautilus best practices (`Nautilus` 4.0/3.0 compatibility, isolated `gettext.translation` domain, XDG Base Directory compliance, valid AppStream `.metainfo.xml`).
     - Verify security best practices (use `subprocess.Popen([...])` without `shell=True`, use `--` before SSH targets, validate ports, quote remote paths with `shlex.quote`, least-privilege GitHub Actions `permissions`, pass untrusted/context values via `env:`).

2. **QA Subagent (`qa-engineer`)**
   - **When:** After code or test changes.
   - **Responsibilities:**
     - Verify the primary developer added/updated unit tests in `tests/` for all changed behavior and edge cases.
     - Verify `make check` (`py_compile`, `unittest`, `appstreamcli validate`) runs cleanly with all tests passing.

3. **Release Manager Subagent (`release-manager`)**
   - **When:** After the final code, `Makefile`, packaging, or documentation edits, before committing for release or publishing a tag.
   - **Responsibilities:**
     - Verify `README.md` documents all user-facing `Makefile` targets (`install-user`, `install`, `check`, `deb`, `rpm`, `arch`, `dist`), GitHub Releases installation, dependencies, and translation instructions, and that `AGENTS.md` reflects the current repository workflow.
     - Verify all versioned metadata (`debian/changelog`, `nautilus-open-terminator.spec`, `PKGBUILD`, `io.github.timhughes.nautilus_open_terminator.metainfo.xml`) is consistent and up to date.
     - Determine the appropriate Semantic Versioning bump (**major**, **minor**, or **patch**) based on changes since the last release/tag.
     - Shepherd the release:
       1. Run `make check` locally and verify all `peer-reviewer` and `qa-engineer` findings are resolved.
       2. Commit and push changes to `master` (or `main`), then monitor GitHub Actions (`gh run watch`) until `lint-and-validate`, `build-debian`, `build-fedora`, and `build-arch` all pass.
       3. Only after all CI builds and tests succeed, create an annotated tag (`git tag -a vX.Y.Z -m "Release vX.Y.Z"`) and push it (`git push origin vX.Y.Z`) to trigger the `release` job.
       4. Monitor the tagged workflow run to confirm the GitHub Release and `.deb`, `.rpm`, and Arch `.pkg.tar.*` assets are published cleanly.
