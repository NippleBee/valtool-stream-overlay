"""Build on Windows after npm run build; output is a relocatable onedir bundle."""
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct,
)

if sys.platform != "win32":
    raise SystemExit("Build this executable on Windows")

root = Path(SPECPATH).parent
version = tomllib.loads((root / "backend/pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
version_numbers = tuple(int(part) for part in version.split(".")) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_numbers, prodvers=version_numbers,
                      mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable("040904B0", [
        StringStruct("FileDescription", "ValTool Stream Overlay"),
        StringStruct("FileVersion", version),
        StringStruct("ProductName", "ValTool Stream Overlay"),
        StringStruct("ProductVersion", version),
        StringStruct("OriginalFilename", "ValTool Stream Overlay.exe"),
    ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])],
)
frontend = root / "frontend" / "dist"
if not (frontend / "index.html").is_file():
    raise SystemExit("Frontend build missing. Run npm ci and npm run build first.")

datas = [(str(frontend), "frontend/dist"), (str(root / "licenses"), "licenses"),
         (str(root / "LICENSE"), "."), (str(root / "THIRD_PARTY_NOTICES.md"), ".")]
datas += collect_data_files("certifi")
datas.append((str(root / "packaging/app-icon.png"), "."))
# Wheel metadata contains the dependencies' LICENSE/NOTICE files. Only include
# runtime requirements, even when building inside an environment with test tools.
for requirement in (root / "backend/requirements.txt").read_text().splitlines():
    if "==" in requirement:
        datas += copy_metadata(requirement.split("==", 1)[0])
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.is_file():
    datas.append((str(python_license), "licenses/python"))
for package in ("react", "react-dom", "scheduler", "lucide-react", "tailwindcss"):
    folder = root / "node_modules" / package
    notices = [file for file in folder.iterdir() if file.is_file()
               and file.name.upper().startswith(("LICENSE", "NOTICE", "COPYING"))]
    if not notices:
        raise SystemExit(f"Dependency license missing: {package}. Run npm ci before packaging.")
    datas += [(str(file), f"licenses/npm/{package}") for file in notices]
a = Analysis([str(root / "packaging/windows-entry.py")], pathex=[str(root / "backend")],
             datas=datas, binaries=[], hiddenimports=["uvicorn.logging", "uvicorn.loops.asyncio",
             "uvicorn.protocols.http.h11_impl",
             "pystray._win32",
             "uvicorn.lifespan.on"], hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ValTool Stream Overlay",
          icon=str(root / "packaging/app-icon.ico"), version=version_info,
          console=False, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="ValTool Stream Overlay")
