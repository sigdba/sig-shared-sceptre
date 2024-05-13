# Contributing to this Project

## Workstation Setup

### NixOS

```bash
nix-shell -p python311 --command "python -m venv .venv --copies"
pipenv lock
direnv allow
```
