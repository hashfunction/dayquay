from rednotebook import info


def test_commandline_help_renders_windows_profile_example():
    help_text = info.get_commandline_parser().format_help()

    assert "%APPDATA%\\DayQuay\\data" in help_text
