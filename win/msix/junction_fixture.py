"""Shared Windows junction creation for native qualification tests only.
Copyright 2026 Trieflow LLC. MIT licensed.
"""

import subprocess


class WindowsJunctionFixture:
    def create_windows_junction(self, link, target):
        # MSYS2's native Python can spell absolute paths D:/...; cmd's mklink
        # builtin needs Windows operands. Keep argv quoting for spaces and refuse
        # shell syntax/expansion in these test-owned paths before invoking cmd.
        paths = [str(path).replace("/", "\\") for path in (link, target)]
        for path in paths:
            self.assertFalse(
                any(c in path for c in '"%!&|^<>()') or any(ord(c) < 32 for c in path),
                "Unsafe cmd syntax in junction fixture path",
            )
        result = subprocess.run(
            ["cmd.exe", "/d", "/v:off", "/c", "mklink", "/J", *paths],
            capture_output=True,
            text=True,
            errors="replace",
        )
        self.assertEqual(
            result.returncode, 0, f"mklink failed for {paths!r}: {result.stdout} {result.stderr}"
        )
        return result
