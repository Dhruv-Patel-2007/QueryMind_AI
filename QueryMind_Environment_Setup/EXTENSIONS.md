# QueryMind AI - IDE Extensions Inventory

This document details all extensions installed in the primary development editor (**Antigravity IDE**), including their publisher, version, purpose, and status.

---

## 1. Installed & Verified Extensions

| Extension ID | Publisher | Version | Purpose & Workflow Role | Status |
| :--- | :--- | :--- | :--- | :--- |
| `charliermarsh.ruff` | Astral Software | `2026.94.0` | Ultra-fast Python linter and code formatter. Formats on save and organizes imports. | **Active & Configured** |
| `ms-pyright.pyright` | Microsoft | `1.1.402` | High-performance Python static type checker and language server (open-source engine of Pylance). | **Active & Verified** |
| `ms-python.python` | Microsoft | `2026.4.0` | Core Python language support, environment discovery, and debugger hooks. | **Active & Verified** |
| `ms-python.debugpy` | Microsoft | `2026.6.0` | Python interactive debugger for FastAPI endpoints and ML script debugging. | **Active & Verified** |
| `ms-python.vscode-python-envs` | Microsoft | `1.20.1` | Management and UI switching of Python virtual environments. | **Active & Verified** |
| `dbaeumer.vscode-eslint` | Microsoft | `3.0.34` | Integrates ESLint into Antigravity IDE for React/TypeScript static analysis. | **Active & Configured** |
| `esbenp.prettier-vscode` | Prettier | `12.4.0` | Opinionated code formatter for JS, TS, JSX, TSX, CSS, JSON, and Markdown. | **Active & Configured** |
| `bradlc.vscode-tailwindcss` | Tailwind Labs | `0.16.0` | Intelligent Tailwind CSS class completion, linting, and hover previews. | **Active & Configured** |
| `alexcvzz.vscode-sqlite` | Alexandre V | `0.14.1` | SQLite database explorer, table schema visualizer, and SQL query runner. | **Active & Configured** |
| `yzhang.markdown-all-in-one` | Yu Zhang | `3.6.2` | Comprehensive Markdown editing support, table formatting, and shortcuts. | **Active & Verified** |
| `bierner.markdown-mermaid` | Matt Bierner | `1.32.1` | Native Mermaid flowchart and sequence diagram rendering in Markdown preview. | **Active & Verified** |
| `eamodio.gitlens` | GitKraken / Eric Amodio | `19.5.0` | Rich inline Git blame, commit history navigation, and repository insights. | **Active & Verified** |
| `usernamehw.errorlens` | Alexander | `3.30.0` | Inline display of errors, warnings, and linting hints directly on code lines. | **Active & Verified** |
| `ms-toolsai.jupyter` | Microsoft | `2025.9.1` | Jupyter notebook execution and exploration for data analysis tasks. | **Active & Verified** |
| `pkief.material-icon-theme` | Philipp Kief | `5.40.0` | Developer file and folder icons for intuitive file tree navigation. | **Active & Verified** |

---

## 2. Note on Pylance vs. Pyright

- **Pylance (`ms-python.vscode-pylance`):**
  - **Status:** Not distributed on open VS Code extension registries.
  - **Reason:** Pylance is closed-source and licensed by Microsoft exclusively for official Microsoft-branded VS Code binaries.
  - **Solution / Alternative:** The open-source language server that powers Pylance is **Pyright** (`ms-pyright.pyright`). Furthermore, the official Microsoft Python extension (`ms-python.python`) includes built-in type checking (`"python.analysis.typeCheckingMode": "basic"`), providing complete IntelliSense, code completion, and static type analysis without requiring closed-source binaries.

---

## 3. Optional Extensions Not Installed (And Rationale)

1. **`dsznajder.es7-react-js-snippets` (React Snippets):**
   - **Rationale:** Optional convenience snippets. Modern TypeScript + Vite + Tailwind templates generate clean code with native snippet support, avoiding snippet clutter.
2. **Additional SQLite extensions:**
   - **Rationale:** `alexcvzz.vscode-sqlite` is already installed and verified. Installing duplicate SQLite extensions causes keybinding conflicts and redundant UI sidebars.
3. **Third-party AI extensions:**
   - **Rationale:** Antigravity IDE already provides built-in DeepMind agent capabilities natively.
