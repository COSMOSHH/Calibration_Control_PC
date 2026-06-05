from pathlib import Path
import sys


# 独立启动 UI0 时同样把 src 放进导入路径，方便未安装包时本地调试。
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from thz_calibration.app import main


if __name__ == "__main__":
    # 注入 --calibration 只是为了命令行语义清晰；app.main 当前默认也是 UI0。
    sys.argv = [sys.argv[0], "--calibration", *sys.argv[1:]]
    main()
