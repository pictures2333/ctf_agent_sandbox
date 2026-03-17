---
name: sandbox-environment-hint
description: Summarizes the current sandbox runtime, enabled background services, installed packages/tools, and operational rules before execution.
---

# Sandbox Environment Hint

## Runtime Summary
- os: Arch Linux
- timezone: {{TIMEZONE}}
- locale: {{LOCALE}}
- services: {{SERVICES}}
- workspace: {{WORKSPACE}}

## Background Services

{{SERVICE_SECTION}}

## Packages, Modules and Tools

{{PACKAGE_SECTION}}

## Rules (Must follow)

- Search package information from [ArchLinux packages](https://archlinux.org/packages/) or [AUR](https://aur.archlinux.org/packages) before install any packages via pacman or yay.
- Python module installation rules:
    - global: use pacman or yay
    - project: use uv (python-uv)
- If the required package is not available in the environment, install it yourself.
- Sudo is available and no password needed.
