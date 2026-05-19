# 馈源间相位校准上位机

本项目是太赫兹四馈源阵列相位校准上位机，第一版使用 Python + PySide6。当前有两套独立界面：

- `IU0`：馈源间相位校准数据测试窗口，用于 Feed1~Feed4 依次测试、自动扫描、保存 Excel。
- `IU1`：馈源阵输出相位配置窗口，用于手动配置 Feed1~Feed4 相位并下发给 STM32。

当前上位机到 STM32 的协议只发送 `feed_id`、`phase_deg`、`enabled`。幅值不发送；波束指向角用于转台电机/实验记录，当前也不发送给 STM32。

## 启动

安装依赖：

```powershell
pip install -r requirements.txt
```

默认打开 IU0 校准数据测试窗口：

```powershell
python run_app.py
```

分别打开两套 UI：

```powershell
python run_calibration_ui.py
python run_config_ui.py
```

指定串口：

```powershell
python run_calibration_ui.py --serial-port COM3
python run_config_ui.py --serial-port COM3
```

`run_app.py --config` 也可以打开 IU1：

```powershell
python run_app.py --config --serial-port COM3
```

## 默认参数

| 参数 | 默认值 |
|------|--------|
| 频谱仪 VISA 地址 | `TCPIP::10.18.18.2::INSTR` |
| 测试频点 | 212 GHz |
| 波束指向角 | 30 deg |
| 相位范围 | 0 deg 到 354.375 deg |
| 相位步长 | 5.625 deg |
| 每点稳定等待 | 500 ms |
| 每点采样次数 | 3 |
| 功率判定 | 平均值 |
| 保存单位 | uW |
| 默认串口 | COM1 |
| 串口波特率 | 9600 |

这些参数集中在 `src/thz_calibration/config.py`。更详细的参数说明见 `docs/上位机内置参数配置.md`。

## 代码树结构

```text
Calibration_Control_PC/
├─ run_app.py                         # 通用入口；默认 IU0，带 --config 打开 IU1
├─ run_calibration_ui.py              # IU0 校准数据测试窗口入口
├─ run_config_ui.py                   # IU1 相位配置窗口入口
├─ requirements.txt                   # 运行依赖
├─ pyproject.toml                     # Python 项目元信息
├─ src/thz_calibration/
│  ├─ app.py                          # QApplication 初始化、命令行参数分发
│  ├─ config.py                       # 默认参数、路径、设备/频谱仪模式切换
│  ├─ models.py                       # FeedState、ScanConfig、ScanPoint 等数据模型
│  ├─ protocol.py                     # AA/版本/命令/长度/JSON/CRC8/BB 帧编码
│  ├─ utils.py                        # dBm/uW 转换、平均值、相位格式化
│  ├─ calibration/
│  │  └─ engine.py                    # 校准扫描状态机；每点下发、等待、采样、记录
│  ├─ controllers/
│  │  └─ device_controller.py         # 上位机控制入口；FeedState -> 协议帧 -> transport
│  ├─ data/
│  │  └─ excel_exporter.py            # Excel 模板复制、过程表/最终汇总表保存、最佳点读取
│  ├─ instruments/
│  │  └─ spectrum_analyzer.py         # 频谱仪抽象；模拟频谱仪和 VISA/SCPI 频谱仪
│  ├─ transport/
│  │  ├─ base.py                      # 传输层接口和 TransportResponse
│  │  ├─ serial_transport.py          # pyserial 串口发送
│  │  └─ simulated.py                 # 模拟 STM32 ACK，便于无硬件调试
│  └─ ui/
│     ├─ calibration_test_window.py    # IU0 主窗口；Feed1~4 测试按钮和全局设置
│     ├─ phase_config_window.py        # IU1 主窗口；手动相位配置、串口连接、数据发送
│     ├─ common.py                     # UI 共用控件工厂、串口枚举、锁定控件
│     └─ style.py                      # 全局 QSS 样式
├─ docs/
│  ├─ 上位机与STM32通信协议交接说明.md   # 下位机对接协议、测试帧、芯片编码说明
│  ├─ 上位机内置参数配置.md             # 内置参数、运行模式、保存和日志说明
│  ├─ 馈源间相位校准上位机开发进度计划.md # 当前进度和后续计划
│  ├─ 馈源间相位校准数据保存格式/        # Excel 标准模板
│  ├─ 芯片手册/                        # IPS-1924-6C、WQD0032H、STM32 手册
│  └─ 说明文档/                        # UI 参考图、校准步骤图、频率核算表
└─ output/                             # 运行生成的 Excel 输出；不提交 Git
```

## 模块职责

| 模块 | 主要职责 | 常见修改场景 |
|------|----------|--------------|
| `config.py` | 管理默认频点、相位范围、串口、VISA、模拟/真实模式、模板路径 | 改默认串口、切换真实 STM32/频谱仪、改采样次数或等待时间 |
| `models.py` | 定义扫描和发送用的数据结构 | 新增 payload 字段、调整扫描参数模型 |
| `protocol.py` | 生成 STM32 串口协议帧 | 改帧头帧尾、命令字、CRC、JSON 格式 |
| `device_controller.py` | 统一设备控制接口 | 增加新的下位机命令，如查询状态、关闭单个 Feed |
| `serial_transport.py` | 实际串口收发 | 改波特率行为、ACK/NACK 读取方式、超时 |
| `simulated.py` | 模拟下位机 | 无硬件时调试 UI 和流程 |
| `spectrum_analyzer.py` | 频谱仪读数 | 改 SCPI 指令、接真实频谱仪、优化模拟数据 |
| `engine.py` | 校准扫描主流程 | 改逐点发送逻辑、稳定等待、采样策略、终端日志 |
| `excel_exporter.py` | Excel 导出和最佳点读取 | 改模板单元格、最终汇总表、输出文件名 |
| `calibration_test_window.py` | IU0 界面和按钮逻辑 | 改校准界面布局、按钮流程、Feed1~4 扫描入口 |
| `phase_config_window.py` | IU1 手动配置界面 | 改手动相位配置、串口连接、数据发送反馈 |
| `common.py` | UI 共用小工具 | 改输入框、数字框、串口列表等共用控件 |
| `style.py` | UI 样式 | 改整体视觉、控件尺寸、颜色 |

## 关键数据流

### IU0 校准扫描

```text
run_calibration_ui.py
  -> thz_calibration.app.main()
  -> CalibrationTestWindow._run_scan(feed_id)
  -> CalibrationTestWindow._feed_states_for_scan(feed_id)
  -> CalibrationEngine.scan_feed()
  -> DeviceController.apply_feed_states()
  -> ProtocolEncoder.encode_set_feeds()
  -> SerialTransport.send() 或 SimulatedTransport.send()
  -> SpectrumAnalyzer.read_peak_power_dbm()
  -> ExcelExporter.save_scan_result()
  -> Feed4 完成后 ExcelExporter.save_multi_feed_result()
```

当前校准步骤按“逐个加入馈源”执行：

| 测试阶段 | 打开的 CE | 关闭的 CE | 说明 |
|----------|-----------|-----------|------|
| Feed1 功率测试 | CE1 | CE2~CE4 | 人工设置 Feed1 初始相位，测单馈源功率 |
| Feed2 相位校准 | CE1、CE2 | CE3、CE4 | Feed1 保持最佳相位，扫描 Feed2 |
| Feed3 相位校准 | CE1、CE2、CE3 | CE4 | Feed1/2 保持最佳相位，扫描 Feed3 |
| Feed4 相位校准 | CE1~CE4 | 无 | Feed1/2/3 保持最佳相位，扫描 Feed4 |

Feed4 测试完成后，程序会读取前面所有输出表中的最佳点，自动生成：

```text
output/CalData_MultiFeed_BDp30_212.xlsx
```

### IU1 手动相位配置

```text
run_config_ui.py
  -> thz_calibration.app.main(--config)
  -> PhaseConfigWindow
  -> 相位确认/自动校准/初始同步
  -> phase_queue
  -> DeviceController.encode_feed_states()
  -> DeviceController.apply_feed_states()
  -> ProtocolEncoder.encode_set_feeds()
```

IU1 的“数据发送”会在界面信息反馈窗打印每个 Feed 的相位、使能状态、完整 HEX 帧和发送结果。

## STM32 发送协议

当前主要命令为 `SET_FEEDS`，payload 示例：

```json
{"feeds":[{"feed_id":1,"phase_deg":0.0,"enabled":true},{"feed_id":2,"phase_deg":5.625,"enabled":true},{"feed_id":3,"phase_deg":0.0,"enabled":false},{"feed_id":4,"phase_deg":0.0,"enabled":false}]}
```

注意：

- `feed_id` 对应 CE1~CE4。
- `phase_deg` 是角度值，不是芯片最终 6-bit code。
- `enabled=false` 表示该 Feed 当前关闭。
- 不发送幅值/幅度。
- 不发送波束指向角。
- STM32 负责把 `phase_deg` 转成 IPS-1924-6C / WQD0032H 所需控制位。

完整协议、CRC8、测试 HEX、芯片真值表见 `docs/上位机与STM32通信协议交接说明.md`。

## 运行模式

默认使用模拟下位机和模拟频谱仪，方便无硬件调试：

```python
device_mode = "simulated"
spectrum_analyzer_mode = "simulated"
```

实机联调时在 `src/thz_calibration/config.py` 中切换：

```python
device_mode = "serial"
spectrum_analyzer_mode = "visa"
```

也可以在 UI 里选择串口并点击“串口连接”，使当前窗口切到真实串口发送。

## Excel 输出

模板目录：

```text
docs/馈源间相位校准数据保存格式/
```

输出目录：

```text
output/
```

主要输出文件：

| 文件 | 生成时机 | 内容 |
|------|----------|------|
| `TestData_Feed1_BDp30_212.xlsx` | Feed1 测试完成 | Feed1 单馈源功率测试结果 |
| `CalProcess_Feed2wrt1_BDp30_212.xlsx` | Feed2 校准完成 | Feed2 相对 Feed1 的扫描过程 |
| `CalProcess_Feed3wrt12_BDp30_212.xlsx` | Feed3 校准完成 | Feed3 相对 Feed1/2 的扫描过程 |
| `CalProcess_Feed4wrt123_BDp30_212.xlsx` | Feed4 校准完成 | Feed4 相对 Feed1/2/3 的扫描过程 |
| `CalData_MultiFeed_BDp30_212.xlsx` | Feed4 校准完成后自动生成 | Feed1~4 最佳相位和功率汇总 |

输出文件固定同名覆盖，不追加时间戳。每个过程表最大功率点会标红。

## 联调日志

`run_calibration_ui.py` 执行校准扫描时，每成功下发一个相位点，会在终端打印一行当前发送的 CE 片选状态和 4 个馈源相位：

```text
校准发送状态：CE1=打开 Feed1=0.000000 deg, CE2=打开 Feed2=5.625000 deg, CE3=关闭 Feed3=0.000000 deg, CE4=关闭 Feed4=0.000000 deg
```

这行日志来自 `CalibrationEngine._format_feed_phase_log()`，用于确认校准过程每次实际下发的馈源开关和相位组合。终端日志不打印完整 HEX，避免扫描过程输出过长。

## 常见修改入口

| 需求 | 优先查看 |
|------|----------|
| 改默认频点、步长、串口、采样次数 | `src/thz_calibration/config.py` |
| 改 STM32 payload 字段 | `src/thz_calibration/models.py`、`src/thz_calibration/protocol.py` |
| 改串口发送/ACK 读取 | `src/thz_calibration/transport/serial_transport.py` |
| 改校准流程、Feed 开关逻辑、终端日志 | `src/thz_calibration/calibration/engine.py`、`src/thz_calibration/ui/calibration_test_window.py` |
| 改 Feed2~4 前序最佳相位继承 | `src/thz_calibration/ui/calibration_test_window.py` |
| 改 Excel 单元格或最终汇总表 | `src/thz_calibration/data/excel_exporter.py` |
| 改频谱仪 SCPI 指令 | `src/thz_calibration/instruments/spectrum_analyzer.py` |
| 改 IU0 布局 | `src/thz_calibration/ui/calibration_test_window.py` |
| 改 IU1 布局或手动发送反馈 | `src/thz_calibration/ui/phase_config_window.py` |
| 改整体样式 | `src/thz_calibration/ui/style.py` |

## 验证命令

语法检查：

```powershell
python -B -c "import pathlib; files=[pathlib.Path('run_app.py'), pathlib.Path('run_calibration_ui.py'), pathlib.Path('run_config_ui.py'), *pathlib.Path('src').rglob('*.py')]; [compile(path.read_text(encoding='utf-8'), str(path), 'exec') for path in files]; print('compiled', len(files), 'files')"
```

检查当前 payload 不包含幅值和波束字段：

```powershell
python -B -c "import sys; sys.path.insert(0, 'src'); from thz_calibration.protocol import ProtocolEncoder; from thz_calibration.models import FeedState; payload=ProtocolEncoder().encode_set_feeds([FeedState(1,0,enabled=True),FeedState(2,5.625,enabled=True),FeedState(3,0,enabled=False),FeedState(4,0,enabled=False)])[5:-2].decode('utf-8'); print(payload)"
```

检查最终汇总表生成：

```powershell
python -B -c "import sys; sys.path.insert(0, 'src'); from thz_calibration.data import ExcelExporter; print(ExcelExporter().save_multi_feed_result(212, 30))"
```
