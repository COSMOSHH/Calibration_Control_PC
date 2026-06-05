from pathlib import Path
import sys


# 独立启动 UI1 时同样把 src 放进导入路径，方便直接双击/命令行调试。
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from thz_calibration.app import main


if __name__ == "__main__":
    # UI1 通过 --config 分发到 PhaseConfigWindow。
    sys.argv = [sys.argv[0], "--config", *sys.argv[1:]]
    main()
