# -----------------------------------------------------------------------
# Jotmorrow modifications Copyright (c) 2026 Trieflow contributors.
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


program_name = "Jotmorrow"
tagline = _("A calm, local desktop journal")
version = "1.0.1"
author = "Jotmorrow contributors"
author_mail = "support@trieflow.com"
upstream_author = "Jendrik Seipp <jendrikseipp@gmail.com>"
copyright_ = (
    "Jotmorrow modifications Copyright © 2026 Trieflow contributors; "
    "RedNotebook Copyright © 2008–2024 Jendrik Seipp"
)
url = "https://jotmorrow.trieflow.com"
downloads_url = "https://jotmorrow.trieflow.com"
donation_url = ""
translation_url = ""
bug_url = "https://jotmorrow.trieflow.com/support"
version_url = ""
contributors_url = "https://github.com/jendrikseipp/rednotebook/graphs/contributors"
discussion_url = "https://jotmorrow.trieflow.com/support"

developers = [author, f"Upstream: {upstream_author}"]
artists = ["Jotmorrow mark: Trieflow contributors", "Upstream artwork: Ciaran"]

comments = _(
    """\
Jotmorrow is a private desktop journal for dated entries, tags, attachments,
search, and verified portable backups. Journal content stays on this device
unless you explicitly export or copy it.
"""
)

journal_path_help = """\
(optional) Specify the directory storing the journal data.
The journal argument can be one of the following:
 - An absolute path (e.g. /home/username/myjournal)
 - A relative path (e.g. ../dir/myjournal)
 - The name of a directory under the Jotmorrow profile

If omitted, Jotmorrow uses the last journal. A first launch defaults to the
product-owned data directory (%%APPDATA%%\\DayQuay\\data on Windows).
"""


def get_commandline_parser():
    parser = argparse.ArgumentParser(
        description=comments, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"Jotmorrow {version}")
    parser.add_argument(
        "--date", dest="start_date", help="load specified date (format: YYYY-MM-DD)"
    )
    parser.add_argument("journal", nargs="?", help=journal_path_help)
    return parser


desktop_file = """\
[Desktop Entry]
Version=1.0
Name=Jotmorrow
GenericName=Journal
Comment=Local daily journal with verified portable backups
Exec=jotmorrow
Icon=jotmorrow
Terminal=false
Type=Application
Categories=Office;
StartupNotify=true
"""
