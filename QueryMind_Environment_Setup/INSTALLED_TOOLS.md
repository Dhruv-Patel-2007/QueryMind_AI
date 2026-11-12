# QueryMind AI - Installed Tools & Runtimes

This document catalogues all foundational software, runtimes, and developer utilities verified for the QueryMind AI project environment.

---

## 1. Tool Summary Table

| Tool | Installed Version | Binary Path | Verification Command | Installation Source / Distribution | Purpose in QueryMind AI |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Git** | `2.55.0.windows.3` | `C:\Program Files\Git\cmd\git.exe` | `git --version` | Official Git for Windows installer | Version control, branch management, collaboration |
| **Python (Target)** | `3.11.9` | `C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe` | `python --version` | Official Python Software Foundation (x64) | Primary backend runtime (FastAPI, scikit-learn, pandas, nltk, sqlglot) |
| **Pip (Python 3.11)** | `24.0` | `C:\Users\OMEN\AppData\Local\Programs\Python\Python311\Scripts\pip.exe` | `python -m pip --version` | Bundled with Python 3.11 | Python package and virtual environment dependency manager |
| **Python (Secondary)** | `3.14.7` | `C:\Users\OMEN\AppData\Local\Programs\Python\Python314\python.exe` | `python --version` | Official Python Software Foundation (x64) | Secondary/host Python version; preserved untouched |
| **Node.js** | `v24.18.0` | `C:\Program Files\nodejs\node.exe` | `node --version` | Official Node.js Windows x64 Installer | Frontend runtime (Vite, React, TypeScript compiler) |
| **npm** | `11.16.0` | `C:\Program Files\nodejs\npm.cmd` | `npm --version` | Bundled with Node.js | Frontend package management |
| **Antigravity IDE** | `1.107.0` | `C:\Users\OMEN\AppData\Local\Programs\Antigravity IDE\Antigravity IDE.exe` | `antigravity-ide --version` | Official Google Antigravity IDE standalone release | Primary AI-assisted pair-programming IDE |
| **VS Code** | `1.143.1` | `C:\Users\OMEN\AppData\Local\Programs\Microsoft VS Code\Code.exe` | `code --version` | Official Microsoft VS Code release | Secondary code editor & diff viewer |
| **Windows Terminal** | Installed | `C:\Users\OMEN\AppData\Local\Microsoft\WindowsApps\wt.exe` | `where.exe wt` | Microsoft Store / Windows Package | Modern tabbed terminal emulator |
| **SQLite Engine** | `3.45.1` (Py 3.11)<br>`3.50.4` (Py 3.14) | Built into Python runtimes | `python -c "import sqlite3; print(sqlite3.sqlite_version)"` | Python Standard Library | Embedded relational database engine for QueryMind SQL exploration |
| **Google Chrome** | `156.0.8078.49` | `C:\Program Files\Google\Chrome\Application\chrome.exe` | Browser inspection | Official Google Chrome installer | Modern browser for React web dashboard testing & debugging |
| **Microsoft Edge** | `156.0.4314.50` | `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` | Browser inspection | Pre-installed Windows system browser | Secondary modern Chromium web browser |

---

## 2. Verification Commands & Outputs

### Git Verification
```powershell
PS> git --version
git version 2.55.0.windows.3

PS> git config user.name
Dhruv Patel

PS> git config user.email
dhruvpatel13022007@gmail.com
```

### Python 3.11 Verification
```powershell
PS> & "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe" --version
Python 3.11.9

PS> & "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe" -m pip --version
pip 24.0 from C:\Users\OMEN\AppData\Local\Programs\Python\Python311\Lib\site-packages\pip (python 3.11)

PS> & "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe" -c "import sqlite3; print(sqlite3.sqlite_version)"
3.45.1
```

### Virtual Environment Creation Test (Python 3.11)
```powershell
PS> & "C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe" -m venv test_venv
PS> & ".\test_venv\Scripts\python.exe" --version
Python 3.11.9
PS> & ".\test_venv\Scripts\python.exe" -m pip --version
pip 24.0 from ...\test_venv\Lib\site-packages\pip (python 3.11)
```
*Result: PASSED (Test virtual environment was cleanly verified and removed).*

### Node.js & npm Verification
```powershell
PS> node --version
v24.18.0

PS> npm --version
11.16.0
```

### Antigravity IDE Verification
```powershell
PS> & "C:\Users\OMEN\AppData\Local\Programs\Antigravity IDE\bin\antigravity-ide.cmd" --version
1.107.0
9e3a5da5d6731effd57d47d88bbe5df14ac6ccdd
x64
```

