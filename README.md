# 馈源间相位校准上位机

第一版上位机使用 Python + PySide6。界面分为两套：`IU0` 风格的馈源间相位校准数据测试窗口，以及 `IU1` 风格的馈源阵输出相位配置窗口。

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

这些参数内置在 [上位机内置参数配置.md](E:/文档/项目/504所项目/Calibration_Control_PC/docs/上位机内置参数配置.md:1)，不在界面中展开。

## 启动

```powershell
pip install -r requirements.txt
python run_app.py
```

`run_app.py` 默认打开 IU0 馈源间相位校准数据测试窗口。两套 UI 也可以分别用独立入口打开：

```powershell
python run_calibration_ui.py
python run_config_ui.py
```

串口默认值在 `src/thz_calibration/config.py` 中配置，也可以启动时传入：

```powershell
python run_calibration_ui.py --serial-port COM3
python run_config_ui.py --serial-port COM3
```

当前工程已预留模拟 STM32 和模拟频谱仪模式，方便先跑通上位机流程。真实 STM32 协议和芯片移位寄存器格式后续在对应模块替换。
