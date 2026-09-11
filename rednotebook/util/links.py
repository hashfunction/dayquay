"""GTK-free parsing of RedNotebook image and named-link markup."""

import re


PIC_NAME = r"\S.*?\S|\S"
PIC_EXT = r"(?:png|jpe?g|gif|eps|bmp|svg)"
REGEX_PIC = re.compile(rf'(\["")({PIC_NAME})("")(\.{PIC_EXT})(\?\d+)?(\])', flags=re.I)
REGEX_NAMED_LINK = re.compile(r'(\[)(.*?)(\s"")(\S.*?\S)(""\])', flags=re.I)


def iter_reference_targets(text):
    """Yield targets only from image and named-link markup recognized by the renderer."""
    for match in REGEX_PIC.finditer(text):
        yield match.group(2) + match.group(4)
    for match in REGEX_NAMED_LINK.finditer(text):
        yield match.group(4)
