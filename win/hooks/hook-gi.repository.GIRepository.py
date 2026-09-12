"""Collect the GIRepository 3 runtime used by current MSYS2 PyGObject."""

from PyInstaller.utils.hooks.gi import GiModuleInfo


def hook(hook_api):
    module_info = GiModuleInfo("GIRepository", "3.0", hook_api=hook_api)
    if not module_info.available:
        raise RuntimeError("GIRepository 3.0 is required to build Jotmorrow")
    binaries, datas, hiddenimports = module_info.collect_typelib_data()
    hook_api.add_datas(datas)
    hook_api.add_binaries(binaries)
    hook_api.add_imports(*hiddenimports)
