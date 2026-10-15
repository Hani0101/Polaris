---
name: claude-sdk-docs
description: Look up the current official Claude Agent SDK documentation (and installed SDK source) before writing, reviewing, or explaining any code that uses the Claude SDK, so the code follows Anthropic's up-to-date best practices instead of stale memory. Use this skill whenever the user mentions the Claude Agent SDK, claude_agent_sdk, claude-agent-sdk, Claude Code SDK, ClaudeSDKClient, ClaudeAgentOptions, query(), custom SDK tools, create_sdk_mcp_server, @tool, hooks, subagents, sessions, permissions/can_use_tool, MCP servers in the SDK, streaming input/output, structured outputs, or "how do I do X with the SDK" — even if they don't say "documentation". Also use it when editing files that import claude_agent_sdk, when debugging SDK errors, or when deciding between the Agent SDK and the plain Anthropic Client SDK. This project depends heavily on the Claude SDK, so default to using this skill for any SDK question.
---

# Claude SDK docs-first workflow

The Claude Agent SDK changes quickly (renamed from the Claude Code SDK, new options and message types every few weeks). Anything you remember about its API may be outdated, and a confident but stale answer is worse than a slower correct one. So for SDK work, treat the official docs and the installed package as the source of truth, and your memory only as a hint about where to look.

## Which SDK is the question about?

- **Claude Agent SDK** (`claude-agent-sdk` on PyPI, `@anthropic-ai/claude-agent-sdk` on npm): runs the Claude Code agent loop as a library, with built-in tools, hooks, subagents, MCP, sessions, permissions. This is what this project uses (Python). Follow the workflow below.
- **Anthropic Client SDK** (`anthropic` / `@anthropic-ai/sdk`, the Messages API directly): if the question is about this, or the user is deciding between the two, invoke the `claude-api` skill, and see "Choosing between them" in `references/doc-map.md`.

If it's unclear, check what the code imports, then decide.

## Workflow

1. **Establish the installed version.** Run `scripts/sdk_info.py` with the project's interpreter (for this repo `E:\Polaris\.venv\Scripts\python.exe`). It prints the installed `claude-agent-sdk` version, the latest on PyPI, and the package path. Version matters because docs describe the latest release; if the project is behind, an option the docs show may not exist yet, and if it's ahead, the docs may lag.

2. **Find the right doc page.** Use the topic table in `references/doc-map.md` to pick the page (e.g. custom tools, hooks, permissions). If the topic isn't listed or the page 404s, fetch the live index `https://code.claude.com/docs/llms.txt` and look for it there; the index is the authority on what pages currently exist.

3. **Read it.** Fetch the page with WebFetch, using the `.md` URL (clean markdown) and a prompt that asks for exactly what you need, such as the exact signature, required options, and the recommended pattern. For anything that touches the API surface, also read the Python reference (`.../agent-sdk/python.md`). Fetch more than one page when the topic crosses boundaries (a custom tool that needs permissions touches both `custom-tools` and `permissions`).

4. **Check for recent changes** when the task is on a fast-moving area or something behaves unexpectedly: skim the Python changelog (`https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md`) for entries newer than the installed version, and for renames or deprecations of what you're about to use.

5. **Verify against the installed package.** The docs can describe a newer release than the one installed. Before relying on a name, grep the installed source (`<venv>/Lib/site-packages/claude_agent_sdk/`, mainly `types.py`, `__init__.py`, `client.py`, `query.py`) to confirm the class, field, or option actually exists in this version. If docs and installed code disagree, tell the user plainly and either write for the installed version or recommend upgrading, with the reason.

6. **Write or review the code using the documented pattern.** Prefer the approach the docs recommend over a clever alternative, and prefer public exported names over reaching into `_internal`. Where the docs state a best practice (permission modes, handling of every message type, cleanup, error types), apply it and say briefly which doc page it came from so the user can check.

7. **Report sources.** End the answer with the pages you used (URLs) and the SDK version you checked against. This lets the user see the answer is grounded rather than remembered, and tells them where to look when something changes.

## Things worth getting right

These are the places where stale memory most often goes wrong, so confirm each against the docs rather than assuming:

- **Package and import names.** The old "Claude Code SDK" names are retired; the migration guide lists what changed. Don't write code against old names.
- **`query()` vs `ClaudeSDKClient`.** They suit different cases (one-shot vs multi-turn, custom tools and hooks usually need the client or streaming input). Read `streaming-vs-single-mode` before choosing.
- **Handling the message stream.** Match on the message and block types the reference lists, and read `ResultMessage` for success, errors, cost, and the session id instead of guessing from text.
- **Permissions and tool access.** `allowed_tools`, `permission_mode`, and `can_use_tool` interact; read `permissions` and `user-input` before loosening anything. Never default to bypassing permissions just to make an example run.
- **Custom tools.** They are exposed through an in-process MCP server, and their qualified names follow the `mcp__<server>__<tool>` pattern; confirm the current registration API and return format in `custom-tools`.
- **What gets loaded from disk.** Whether `.claude/` settings, skills, and CLAUDE.md are loaded by the SDK depends on options (`setting_sources` and related); confirm in `claude-code-features` rather than assuming, because it changes the agent's behavior and its security surface.
- **Authentication.** The overview's authentication note has changed over time. If the code authenticates with a local Claude login rather than an API key, re-read the current guidance and flag it if that's not suitable for a product other people will use. A local login is fine for a personal spike, but that is the sort of detail the user would want to know before shipping.

## If you can't reach the docs

If WebFetch fails (offline, blocked, 404), say so instead of silently falling back to memory. Then use the installed package as the fallback source: read the relevant docstrings and types in `claude_agent_sdk`, answer from that, and mark the answer as "verified against installed v{version} only, not against current docs".

## Keeping answers short

The goal is correct code, not a lecture. After looking things up, give the user the working code or the direct answer, one line on what the docs recommend and why it matters here, and the sources. Don't paste doc pages back at them.
