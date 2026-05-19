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

## 文档与模板

- 说明资料、界面参考图和频率核算表放在 `docs/说明文档/`。
- Excel 兼容模板放在 `docs/馈源间相位校准数据保存格式/`。
- 芯片手册放在 `docs/芯片手册/`。
- 上位机与 STM32 对接协议见 `docs/上位机与STM32通信协议交接说明.md`。

## 联调日志

`run_calibration_ui.py` 执行校准扫描时，每成功下发一个相位点，会在终端打印一行当前发送的 CE 片选状态和 4 个馈源相位，便于确认校准过程中的实际发送值：

```text
校准发送状态：CE1=打开 Feed1=0.000000 deg, CE2=打开 Feed2=5.625000 deg, CE3=关闭 Feed3=0.000000 deg, CE4=关闭 Feed4=0.000000 deg
```

配置界面 `run_config_ui.py` 的“数据发送”仍在界面信息反馈窗中显示发送内容和发送结果。

波束指向角用于转台电机/实验记录，当前不会发送给 STM32；下位机只接收 Feed 相位和使能状态。

完成 Feed4 测试后，上位机会自动汇总 Feed1~Feed4 已保存的最佳点，生成 `output/CalData_MultiFeed_BDp30_212.xlsx`。
