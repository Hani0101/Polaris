# Claude Agent SDK doc map

Docs base: `https://code.claude.com/docs/en/agent-sdk/` (append `.md` to any page for clean markdown).
`platform.claude.com/docs/en/agent-sdk/*` redirects to the same pages.
Live index of every page: `https://code.claude.com/docs/llms.txt` (verify here if a page below 404s; pages get renamed).

## Topic → page

| Topic / user says | Page |
|---|---|
| What is it, capabilities, which Claude tool to use | `overview` |
| First agent, install, auth setup | `quickstart` |
| Old Claude Code SDK names, upgrading | `migration-guide` |
| Errors, CLI not found, things not working | `troubleshooting` |
| **Python API reference** (classes, options, types, messages) | `python` |
| TypeScript API reference | `typescript` |
| `ClaudeAgentOptions` fields, model, system prompt basics | `configuration` |
| How the loop runs, turns, stop conditions, `max_turns` | `agent-loop` |
| `query()` vs `ClaudeSDKClient`, streaming input | `streaming-vs-single-mode` |
| Streaming partial messages / token deltas | `streaming-output` |
| JSON-schema / structured results | `structured-outputs` |
| Custom tools, `@tool`, `create_sdk_mcp_server` | `custom-tools` |
| External MCP servers (stdio / HTTP / SSE) | `mcp` |
| Many tools, tool search | `tool-search` |
| Subagents, `AgentDefinition` | `subagents` |
| Changing the system prompt, CLAUDE.md, presets | `modifying-system-prompts` |
| Skills in the SDK | `skills` |
| Plugins in the SDK | `plugins` |
| Which `.claude/` settings, skills, commands get loaded | `claude-code-features` |
| Permission modes, `allowed_tools`, `can_use_tool` | `permissions` |
| Approval prompts, asking the user questions | `user-input` |
| Hooks (PreToolUse, PostToolUse, etc.) | `hooks` |
| Sessions, resume, fork | `sessions` |
| Session persistence to external storage | `session-storage` |
| File checkpoints / rewind | `file-checkpointing` |
| Cost and token usage | `cost-tracking` |
| OpenTelemetry tracing | `observability` |
| Todo tracking | `todo-tracking` |
| Running in production, containers | `hosting` |
| Sandboxing, hardening, credential handling | `secure-deployment` |
| Worked examples | `examples` |

Example fetch: `https://code.claude.com/docs/en/agent-sdk/custom-tools.md`

## Other sources worth knowing

- Python changelog: https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md
- Python repo (source, issues, examples dir): https://github.com/anthropics/claude-agent-sdk-python
- TypeScript changelog: https://github.com/anthropics/claude-agent-sdk-typescript/blob/main/CHANGELOG.md
- Demo apps: https://github.com/anthropics/claude-agent-sdk-demos
- Built-in tool names and behavior: `https://code.claude.com/docs/en/tools-reference`
- Headless CLI (`claude -p`) for non-Python/TS use: `https://code.claude.com/docs/en/headless`

## Choosing between them

| Need | Use |
|---|---|
| Claude Code's agent loop and built-in tools (files, shell, web) embedded in your own app | Agent SDK (this skill) |
| Direct Messages API calls, you control the tool loop | Anthropic Client SDK (`claude-api` skill); beta tool runner can drive the loop: https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner |
| Anthropic-hosted agent in a managed sandbox | Managed Agents: https://platform.claude.com/docs/en/managed-agents/overview |
| Interactive terminal work | Claude Code CLI |
