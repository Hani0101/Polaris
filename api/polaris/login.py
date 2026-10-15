import os


class ApiKeyPresent(RuntimeError):
    """v1 stops so a Claude login is not silently replaced by an API key."""


def assert_claude_login() -> None:
    """Stop before serving if ANTHROPIC_API_KEY is set.

    Decision 0001: Polaris reaches Claude through the Claude login on this
    machine. The Agent SDK treats that environment variable as the API-key
    credential (apiKeySource "ANTHROPIC_API_KEY").
    """

    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        raise ApiKeyPresent(
            "Polaris stopped because ANTHROPIC_API_KEY is set. "
            "v1 uses the Claude login on this machine."
        )


def reject_api_key_credential(source: str) -> None:
    """Stop when the CLI reports any credential other than no API key.

    SystemInitData.apiKeySource is "none" for a claude.ai login. Every other
    reported source is an API key.
    """

    if source == "none":
        return
    raise ApiKeyPresent(
        f"Polaris stopped because Claude reported an API key ({source}). "
        "v1 uses the Claude login on this machine."
    )
