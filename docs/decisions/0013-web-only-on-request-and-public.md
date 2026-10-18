---
status: accepted
---

# The web is used only on request, and only public pages

Polaris reaches the web in two ways. The learner can add a web page as a resource by its link (RS-22). Polaris code fetches it once, takes its text out, and keeps it like a file. And the learner can send a message in web mode (CH-23). For that reply only, the teaching agent can use the web search and page reading tools that ship with the Claude Agent SDK.

Web mode is off by default and is decided by code, not by the agent. Searching sends the learner's question to a search provider, and every page that comes back is untrusted text the agent then reads. Asking first keeps both of those under the learner's control. The web tools are always registered, so a session's agent does not restart when web mode changes. A PreToolUse hook denies every web call unless the current reply was sent in web mode, and it caps a reply at 4 calls (CH-25). The hook runs before the allow list, and its deny wins.

Only public addresses are read. Polaris runs on the learner's machine next to its own API, which holds the profile, so a page could try to make the agent read `localhost` and leak what it finds. Before every page read, the hook resolves the address and refuses it unless every address the host resolves to is public (CH-26). For a link the learner adds, Polaris's fetcher does the same check, connects to the address it checked, and checks each redirect again (RS-23).

Consequences:

- Polaris checks a page the agent reads, but the SDK's tool makes the request. A host that resolves to a public address for the check and a local one for the request (DNS rebinding) is not blocked for web mode. A link the learner adds is not exposed to this, because Polaris's fetcher connects to the address it checked. This is accepted for one learner on their own machine, and is revisited before hosting.
- A web-mode reply cites pages as plain links (CH-24). Nothing checks in code that a cited page was really read in that reply. A web page resource is checked like any other resource, so a flashcard deck can cite it (decision 0012).
- The fetcher checks certificates through the operating system (`truststore`), so it accepts the same sites a browser does.
- A web page resource is not refreshed (RS-24). The learner removes it and adds it again.
