from pathlib import Path
import sys
import traceback


# 运行入口脚本需要把本仓库的 src 加入 sys.path。
# 这样用户可以直接执行 python run_app.py，而不必先安装成 Python 包。
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from thz_calibration.app import main


if __name__ == "__main__":
    # 默认进入 UI0（校准数据测试窗口）；如需 UI1，可使用 run_app.py --config。
    try:
        main()
    except Exception:
        # windowed 冻结程序没有控制台；保留启动异常日志，便于目标电脑现场排查。
        if getattr(sys, "frozen", False):
            log_path = Path(sys.executable).resolve().with_name("startup_error.log")
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        raise
