---
name: pfc-package-management
description: >
  Manage Python packages in PFC's embedded Python 3.6 environment.
  Use when import fails with ModuleNotFoundError, need to install/uninstall packages,
  or resolve version conflicts.
---

# PFC Package Management

Manage packages in PFC's embedded Python environment (Python 3.6.1, pip 9.x, numpy 1.13.0).

**Key variable** (from `<env>`):
- `{pfc_path}` - PFC installation directory

---

## Install Pattern

Preferred path: run pip through PFC's embedded interpreter from shell.

```bash
"{pfc_path}/exe64/python36/python.exe" -m pip show package_name
"{pfc_path}/exe64/python36/python.exe" -m pip install --user package_name
```

Fallback path (if shell install fails): run in PFC GUI IPython console.

```python
import pip
pip.main(['install', '--user', 'package_name'])
```

**Always use `--user`** to avoid permission issues with PFC installation directory.

---

## Critical: Restart After Install

Installed packages won't be available until pfc-bridge restarts. Python caches loaded modules.

**Workflow**:
1. Install package with `pip.main()`
2. Restart pfc-bridge
3. Verify with `import package_name`

---

## PFC Pre-installed Packages

PFC 7.0 includes these packages—do NOT override them:

| Package | Version | Note |
|---------|---------|------|
| numpy | 1.13.0 | **Critical**: Many packages depend on this |
| scipy | bundled | |
| matplotlib | bundled | |
| pytz | bundled | |

**Check before installing**:
```python
import numpy; print(numpy.__version__, numpy.__file__)
```

If path shows `C:\Program Files\Itasca\...`, it's PFC's bundled version.

---

## Compatibility Table (numpy 1.13.0)

| Package | Compatible Version | Command |
|---------|-------------------|---------|
| pandas | **0.19.2** | `pip.main(['install', '--user', 'pandas==0.19.2'])` |
| tabulate | latest | `pip.main(['install', '--user', 'tabulate'])` |

**Warning**: Newer pandas versions require numpy >= 1.15.4 and will fail.

---

## Quick Reference

| Operation | Command |
|-----------|---------|
| Install | `"{pfc_path}/exe64/python36/python.exe" -m pip install --user pkg` |
| Upgrade | `"{pfc_path}/exe64/python36/python.exe" -m pip install --user --upgrade pkg` |
| Uninstall | `"{pfc_path}/exe64/python36/python.exe" -m pip uninstall -y pkg` |
| List all | `"{pfc_path}/exe64/python36/python.exe" -m pip list` |
| Show info | `"{pfc_path}/exe64/python36/python.exe" -m pip show pkg` |
| Force reinstall | `"{pfc_path}/exe64/python36/python.exe" -m pip install --user --force-reinstall --no-cache-dir pkg` |

---

## Troubleshooting

### Module still not found after install
First, restart pfc-bridge to reload Python modules.

If still failing, verify install target is PFC Python (not system Python):
```bash
"{pfc_path}/exe64/python36/python.exe" -c "import sys; print(sys.executable)"
```

### "Ghost install": pip says installed but ModuleNotFoundError persists
Pip metadata may be corrupted (files missing but records remain). Force reinstall:
```python
import pip
pip.main(['install', '--user', '--force-reinstall', '--no-cache-dir', 'package_name'])
```
Then restart pfc-bridge.

### Package overrides PFC's bundled package
If you accidentally installed a newer numpy:
```python
import pip
pip.main(['uninstall', 'numpy', '-y'])
# Then restart pfc-bridge
```

### Permission denied
Always use `--user` flag.

If shell command still fails, run install from PFC GUI IPython console:
```python
import pip
pip.main(['install', '--user', 'package_name'])
```

### Import error after install (version conflict)
Check which version is loaded:
```python
import package_name
print(package_name.__version__, package_name.__file__)
```

If path shows `AppData\Roaming\Python\...`, it's user-installed and may conflict with PFC.
