from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata


project_root = Path(SPECPATH).resolve().parent
template_dir = project_root / "docs" / "馈源间相位校准数据保存格式"
frequency_plan = project_root / "docs" / "说明文档" / "中频和本振频率核算表.xlsx"

datas = [
    (str(template_dir), "docs/馈源间相位校准数据保存格式"),
    (str(frequency_plan), "docs/说明文档"),
    *copy_metadata("pyvisa-py"),
]

analysis = Analysis(
    [str(project_root / "run_app.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules(
        "pyvisa_py",
        filter=lambda name: not name.startswith("pyvisa_py.testsuite"),
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "unittest",
        "tkinter",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(analysis.pure)

calibration_exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="THz_Calibration",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

phase_config_exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="THz_Phase_Config",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

bundle = COLLECT(
    calibration_exe,
    phase_config_exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="THz_Calibration_Portable",
)
