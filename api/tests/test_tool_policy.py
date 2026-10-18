from pathlib import Path

from polaris.animation_writer import animation_writer_options
from polaris.key_check import key_check_options
from polaris.profile_pass import profile_pass_options
from polaris.session_title import title_options
from polaris.teaching import teaching_options
from polaris.tool_policy import DISALLOWED_TOOLS


def test_every_agent_disallows_shell_and_file_writes(tmp_path: Path) -> None:
    all_options = [
        teaching_options(cwd=tmp_path),
        animation_writer_options(cwd=tmp_path),
        key_check_options(cwd=tmp_path),
        profile_pass_options(cwd=tmp_path),
        title_options(cwd=tmp_path),
    ]
    assert DISALLOWED_TOOLS == ["Bash", "Write", "Edit"]
    for options in all_options:
        assert options.disallowed_tools == DISALLOWED_TOOLS
