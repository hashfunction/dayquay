# Based on PyInstaller 6.22's GtkSource hook. PyInstaller's bootloader
# exception and full license are recorded in win/THIRD-PARTY-NOTICES.txt.
from PyInstaller.utils.hooks.gi import GiModuleInfo, collect_glib_share_files


def hook(hook_api):
    module_info = GiModuleInfo("GtkSource", "4", hook_api=hook_api)
    if not module_info.available:
        raise RuntimeError("GtkSource 4 is required to build Jotmorrow")
    binaries, datas, hiddenimports = module_info.collect_typelib_data()
    datas += collect_glib_share_files(f"gtksourceview-{module_info.version}")
    hook_api.add_datas(datas)
    hook_api.add_binaries(binaries)
    hook_api.add_imports(*hiddenimports)

