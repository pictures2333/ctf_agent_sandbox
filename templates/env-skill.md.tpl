---
name: sandbox-environment-hint
description: Auto-generated sandbox environment summary. Use this to understand installed tools and service topology before operating.
---

# Sandbox Environment Hint

## Runtime Summary
- timezone: {{TIMEZONE}}
- locale: {{LOCALE}}
- services: {{SERVICES}}
- agent_cli_tools: {{AGENT_CLI_TOOLS}}
- workspace: {{WORKSPACE}}

## Agent CLI Tools
{{TOOL_SECTION}}

## Built-in Notes
- This skill is generated automatically during `assemble` and `build_image`.
- Service-specific skills are mounted only when their service plugin is enabled.

## Background Services
{{SERVICE_SECTION}}

{{PACKAGE_SECTION}}
