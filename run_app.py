from pathlib import Path
import sys


# 运行入口脚本需要把本仓库的 src 加入 sys.path。
# 这样用户可以直接执行 python run_app.py，而不必先安装成 Python 包。
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from thz_calibration.app import main


if __name__ == "__main__":
    # 默认进入 UI0（校准数据测试窗口）；如需 UI1，可使用 run_app.py --config。
    main()
