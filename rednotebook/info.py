# -----------------------------------------------------------------------
# DayQuay modifications Copyright (c) 2026 Trieflow contributors.
# Based on RedNotebook Copyright (c) 2008-2024 Jendrik Seipp.
# The combined application is distributed under GPL-3.0-or-later because
# it includes GPL-3.0-or-later spellcheck code. See LICENSES and
# win/THIRD-PARTY-NOTICES.txt for complete notices.
# -----------------------------------------------------------------------

import argparse
import builtins


if not hasattr(builtins, "_"):

    def _(string):
        return string


program_name = "DayQuay"
tagline = _("A calm, local desktop journal")
version = "2.42.0+dayquay.1"
author = "DayQuay contributors"
author_mail = "support@trieflow.com"
upstream_author = "Jendrik Seipp <jendrikseipp@gmail.com>"
copyright_ = (
    "DayQuay modifications Copyright © 2026 Trieflow contributors; "
    "RedNotebook Copyright © 2008–2024 Jendrik Seipp"
)
url = "https://dayquay.trieflow.com"
downloads_url = "https://dayquay.trieflow.com"
donation_url = ""
translation_url = ""
bug_url = "https://dayquay.trieflow.com/support"
version_url = ""
contributors_url = "https://github.com/jendrikseipp/rednotebook/graphs/contributors"
discussion_url = "https://dayquay.trieflow.com/support"

developers = [author, f"Upstream: {upstream_author}"]
artists = ["DayQuay mark: Trieflow contributors", "Upstream artwork: Ciaran"]

comments = _(
    """\
DayQuay is a private desktop journal for dated entries, tags, attachments,
search, and verified portable backups. Journal content stays on this device
unless you explicitly export or copy it.
"""
)

journal_path_help = """\
(optional) Specify the directory storing the journal data.
The journal argument can be one of the following:
 - An absolute path (e.g. /home/username/myjournal)
 - A relative path (e.g. ../dir/myjournal)
 - The name of a directory under the DayQuay profile

If omitted, DayQuay uses the last journal. A first launch defaults to the
product-owned data directory (%%APPDATA%%\\DayQuay\\data on Windows).
"""


def get_commandline_parser():
    parser = argparse.ArgumentParser(
        description=comments, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"DayQuay {version}")
    parser.add_argument(
        "--date", dest="start_date", help="load specified date (format: YYYY-MM-DD)"
    )
    parser.add_argument("journal", nargs="?", help=journal_path_help)
    return parser


desktop_file = """\
[Desktop Entry]
Version=1.0
Name=DayQuay
GenericName=Journal
Comment=Local daily journal with verified portable backups
Exec=dayquay
Icon=dayquay
Terminal=false
Type=Application
Categories=Office;
StartupNotify=true
"""
