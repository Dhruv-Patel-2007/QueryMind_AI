# QueryMind AI - Environment & Workspace Configuration

This document specifies all configuration settings established for the QueryMind AI project workspace.

---

## 1. Workspace Configuration File (`.vscode/settings.json`)

The workspace-level configuration is located at:
`c:\Users\OMEN\OneDrive\Desktop\STUDY\Projects\Nlp\QueryMind-AI\.vscode\settings.json`

```json
{
  "python.defaultInterpreterPath": "C:\\Users\\OMEN\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
  "python.analysis.typeCheckingMode": "basic",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit",
    "source.organizeImports.ruff": "explicit"
  },
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[javascriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[json]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[jsonc]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[css]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[markdown]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "files.exclude": {
    "**/.git": true,
    "**/.svn": true,
    "**/.hg": true,
    "**/CVS": true,
    "**/.DS_Store": true,
    "**/Thumbs.db": true,
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/.mypy_cache": true,
    "**/.ruff_cache": true
  },
  "files.watcherExclude": {
    "**/.git/objects/**": true,
    "**/.git/subtree-cache/**": true,
    "**/node_modules/**": true,
    "**/.venv/**": true,
    "**/dist/**": true,
    "**/build/**": true
  },
  "terminal.integrated.defaultProfile.windows": "PowerShell",
  "sqlite.recordsPerPage": 50,
  "markdown-preview-enhanced.enableMermaid": true
}
```

---

## 2. Explanation of Configured Settings

1. **Python Default Interpreter:**
   - Mapped explicitly to Python 3.11 (`C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe`).
   - Ensures that the IDE targets the stable 3.11 runtime rather than the host's bleeding-edge 3.14 installation.
2. **Automated Code Formatting on Save (`editor.formatOnSave: true`):**
   - **Python:** Handled by **Ruff** (`charliermarsh.ruff`) for sub-millisecond linting, formatting, and import sorting.
   - **Frontend & Web:** Handled by **Prettier** (`esbenp.prettier-vscode`) across TypeScript, JSX/TSX, CSS, JSON, and Markdown.
3. **Automated Code Actions on Save:**
   - Automatically organizes Python imports (`source.organizeImports.ruff`).
   - Automatically resolves auto-fixable ESLint issues for TypeScript/React (`source.fixAll.eslint`).
4. **Cache & Artifact Exclusions:**
   - Hides generated clutter from the file explorer: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`.
   - Excludes heavy transient folders (`node_modules`, `.venv`, `dist`, `build`) from file watchers to preserve CPU and RAM.
5. **Terminal Configuration:**
   - Defaults integrated terminal sessions to Windows PowerShell.
6. **Database & Diagramming:**
   - Sets SQLite pagination to 50 records per page for responsive query browsing.
   - Enables Mermaid rendering for documentation architecture diagrams.

---

## 3. Global System & PATH Impact
- **No global environment variables were modified.**
- **No existing user settings were overwritten.**
- **No system PATH modifications were made**, preserving complete safety across all other projects on your machine.

