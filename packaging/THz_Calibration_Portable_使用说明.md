# THz_Calibration_Portable 使用说明

适用系统：Windows 10 / Windows 11 64 位  
软件组成：UI0 校准测试 + UI1 相位配置  
配置文件：软件目录下的 `config.ini`

## 1. 软件说明

本软件是太赫兹四馈源阵列相位校准与相位下发工具。

- `THz_Calibration.exe`：UI0，依次完成 Feed1 功率测试和 Feed2～Feed4 相位扫描，读取频谱仪功率并生成 Excel。
- `THz_Phase_Config.exe`：UI1，手动设置四路相位，或根据波束指向角计算相位；可叠加 UI0 校准结果并发送给 STM32。
- 目标电脑不需要安装 Python、Conda 或项目依赖。
- `_internal` 是程序运行环境和 Excel 模板，不能删除、改名或单独移动。

当前发送给 STM32 的数据包括：`feed_id`、`phase_deg`、`enabled`。幅值不发送；UI1 的 `φ₀` 当前不参与波束配相计算，也不发送。

## 2. 目录结构

```text
THz_Calibration_Portable/
├─ THz_Calibration.exe
├─ THz_Phase_Config.exe
├─ config.ini
├─ README_zh-CN.txt
├─ THz_Calibration_Portable_使用说明.md
├─ output/                 # 数据输出目录，运行时创建/使用
└─ _internal/              # 运行环境和模板，禁止删除
```

必须先完整解压 ZIP，再运行 EXE。不要在压缩包预览窗口中启动，也不要只把 EXE 复制到桌面；需要桌面入口时请创建快捷方式。

建议解压到具有写权限的目录，例如：

```text
D:\THz_Calibration_Portable
```

不建议放在 `C:\Program Files`、系统临时目录或无写权限的网络目录。

## 3. 需要安装什么软件

### 3.1 仅模拟演示

不需要安装任何额外软件，保持以下模式即可：

```ini
[device]
mode = simulated

[spectrum_analyzer]
mode = simulated

[signal_source]
mode = manual

[turntable]
mode = simulated
```

### 3.2 连接真实设备

| 设备/接口 | 需要安装的内容 |
|---|---|
| STM32 串口 | STM32 虚拟串口驱动，或实际 USB-UART 芯片的 Windows x64 驱动 |
| 转台串口/USB-RS485 | 转台厂家或 USB-RS485 转换器的 Windows x64 驱动 |
| 频谱仪 TCPIP SOCKET | 优先使用软件内置 `pyvisa-py`，通常不用安装厂商 VISA；连接不兼容时再安装厂商 VISA Runtime |
| 频谱仪 GPIB | GPIB 控制器驱动和厂商 VISA Runtime，均使用 64 位版本 |
| 本振/中频信号源自动控制 | 先使用 VISA 工具验证资源名；内置后端不能连接时安装厂商 VISA Runtime |
| 查看 Excel 结果 | 可选安装 Microsoft Excel 或其他兼容 xlsx 的表格软件；软件生成和读取 xlsx 本身不依赖 Excel |

网络仪器还需要：

- 控制电脑与仪器网络互通；
- IP、端口和 VISA 资源名正确；
- Windows 防火墙允许访问现场仪器端口；
- 杀毒软件如拦截 EXE，应按甲方 IT 流程校验并放行交付目录，不建议关闭安全软件。

建议显示分辨率为 1920×1080，Windows 缩放为 100%～125%。

## 4. 配置文件的修改方法

配置文件位于两个 EXE 同级目录：

```text
THz_Calibration_Portable\config.ini
```

修改方法：

1. 退出 UI0 和 UI1。
2. 用记事本或其他纯文本编辑器打开 `config.ini`。
3. 修改并保存，建议保持 UTF-8 编码。
4. 重新启动软件。

注意：配置只在程序启动时读取。修改后必须完全退出并重启，仅点击界面的“重设”不会重新读取配置。

相对输出路径以 `config.ini` 所在目录为基准。实机参数确认后，建议备份一份现场配置。

## 5. config.ini 参数说明

### 5.1 `[device]`：STM32 串口

| 参数 | 默认值/可选值 | 说明 |
|---|---|---|
| `mode` | `simulated` / `serial` | 模拟设备或真实 STM32 串口 |
| `serial_port` | `COM1` | STM32 在设备管理器中的 COM 口 |
| `serial_baudrate` | `9600` | 必须与 STM32 固件一致 |

即使配置为 `simulated`，也可以在 UI0/UI1 中选择 COM 口并点击“串口连接”，切换到真实串口。

### 5.2 `[spectrum_analyzer]`：频谱仪

| 参数 | 默认值/可选值 | 说明 |
|---|---|---|
| `mode` | `simulated` / `visa` | 模拟读数或连接真实频谱仪 |
| `profile` | `research` / `xian_gpib` | `research` 使用 TCPIP 地址；`xian_gpib` 使用 GPIB 地址 |
| `visa_backend` | `auto` / `ivi` / `py` | `py` 使用内置 pyvisa-py；`ivi` 使用厂商 VISA Runtime；实机建议明确设置 |
| `visa_address` | `TCPIP0::10.18.18.4::5025::SOCKET` | `research` 档位使用的完整 VISA 资源名 |
| `xian_gpib_address` | `GPIB0::20::INSTR` | `xian_gpib` 档位使用的完整 GPIB 资源名 |
| `timeout_ms` | `5000` | VISA 连接和读写超时，单位 ms |
| `span_ghz` | `0.002` | 扫频宽度，单位 GHz；实际下发前会除以 `frequency_divisor` |
| `scan_points` | `201` | 频谱仪扫频点数 |
| `rbw_hz` | `1000` | 分辨率带宽 RBW，单位 Hz |
| `vbw_hz` | `1000` | 视频带宽 VBW，单位 Hz |
| `frequency_divisor` | `10.0` | 频谱仪观察频率 = UI 校准频率 ÷ 此值 |

`frequency_divisor` 必须按实际扩频/变频链路确认：无扩频模块调试示例为 `10.0`；正式接扩频模块时可能使用 `1.0`，不能直接照抄示例。

每个相位点测量前，软件会配置中心频率、扫宽、点数、RBW、VBW 和频谱仪内置平均次数，清空平均缓存后读取一次 marker 峰值功率。

### 5.3 `[signal_source]`：本振源和中频源

| 参数 | 默认值/可选值 | 说明 |
|---|---|---|
| `mode` | `manual` / `auto` | 手动提示或由 UI0 自动发送 VISA 命令 |
| `lo_visa_address` | `TCPIP0::10.18.18.4::hislip0::INSTR` | 本振源 VISA 资源名 |
| `if_visa_address` | `TCPIP0::10.18.18.3::hislip0::INSTR` | 中频源 VISA 资源名 |
| `timeout_ms` | `5000` | 信号源连接/指令超时，单位 ms |

- `manual`：UI0 只提示需要设置的频率、功率和开关，由操作人员控制仪器。
- `auto`：UI0 开启某一路时，根据内置频率计划下发频率、功率和输出 ON；关闭时下发输出 OFF。
- UI1 的本振/中频按钮当前只改变界面状态并显示反馈，不控制真实信号源。

### 5.4 `[turntable]`：转台

| 参数 | 默认值/可选值 | 说明 |
|---|---|---|
| `mode` | `simulated` / `serial` | 模拟转台或真实 Modbus RTU 转台 |
| `serial_port` | `COM1` | 转台/USB-RS485 的 COM 口，不能和 STM32 使用同一端口 |
| `baudrate` | `38400` | 转台波特率 |
| `slave_id` | `1` | Modbus 从站地址 |
| `pulses_per_degree` | `2000.0` | 每度脉冲数，必须按机械和驱动器参数标定 |
| `move_timeout_s` | `30.0` | 单次运动等待上限，单位 s |
| `poll_interval_s` | `0.05` | 状态轮询间隔，单位 s |
| `settle_time_s` | `0.12` | 到位后的额外稳定时间，单位 s |

UI0 点击“转台连接”后，会把当前位置设为 `0 deg`。点击全局“确认”时，转台会移动到界面中的“波束指向”角度。

### 5.5 `[calibration]`：校准参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `frequency_ghz` | `212.0` | UI0 默认校准频率和 UI1 默认输出频率，单位 GHz |
| `beam_angle_deg` | `30.0` | UI0 默认波束指向/转台目标角，单位 deg |
| `phase_start_deg` | `0.0` | Feed2～Feed4 扫描起点 |
| `phase_end_deg` | `354.375` | 扫描终点 |
| `phase_step_deg` | `5.625` | 扫描步长，同时也是 UI1 相位量化步长 |
| `default_amplitude` | `0.12` | 软件模型保留值，当前不发送给 STM32 |
| `settle_time_ms` | `500` | 每次相位下发后的稳定等待时间，单位 ms |
| `sample_count` | `3` | 频谱仪内置平均次数，不是上位机重复读取次数 |

默认 `0～354.375 deg`、步长 `5.625 deg`，共 64 个相位点。

### 5.6 `[paths]`：输出目录

| 参数 | 默认值 | 说明 |
|---|---|---|
| `output_dir` | `output` | Excel 输出目录；相对路径以 `config.ini` 所在目录为基准，也可填写绝对路径 |

## 6. 常用配置示例

下面的 COM 口、IP、GPIB 地址和换算系数都是示例，实机使用前必须核对现场设备。

### 6.1 无硬件自检

```ini
[device]
mode = simulated

[spectrum_analyzer]
mode = simulated

[signal_source]
mode = manual

[turntable]
mode = simulated
```

### 6.2 STM32 + TCPIP 频谱仪 + 手动信号源 + 串口转台

```ini
[device]
mode = serial
serial_port = COM4
serial_baudrate = 9600

[spectrum_analyzer]
mode = visa
profile = research
visa_backend = py
visa_address = TCPIP0::10.18.18.4::5025::SOCKET
frequency_divisor = 1.0

[signal_source]
mode = manual

[turntable]
mode = serial
serial_port = COM5
baudrate = 38400
slave_id = 1
pulses_per_degree = 2000.0
```

### 6.3 GPIB 频谱仪 + 自动控制信号源

```ini
[spectrum_analyzer]
mode = visa
profile = xian_gpib
visa_backend = ivi
xian_gpib_address = GPIB0::20::INSTR
frequency_divisor = 1.0

[signal_source]
mode = auto
lo_visa_address = TCPIP0::10.18.18.4::hislip0::INSTR
if_visa_address = TCPIP0::10.18.18.3::hislip0::INSTR
timeout_ms = 5000
```

## 7. UI0 校准测试操作

### 7.1 测试前检查

- 检查射频链路、衰减、仪器量程和安全功率。
- 确认 `config.ini` 的 STM32、频谱仪、信号源和转台模式正确。
- 在设备管理器核对 STM32 与转台 COM 口，防止端口互换或被其他程序占用。
- 核对 `frequency_divisor`、扫宽、RBW、VBW、平均次数。
- 备份输出目录中的旧 Excel；软件使用固定文件名，会覆盖同名文件。

### 7.2 连接和全局设置

1. 启动 `THz_Calibration.exe`。
2. STM32：选择串口，点击“刷新”，再点击“串口连接”。
3. 转台：确认机械零位，选择转台串口，点击“刷新”和“转台连接”。连接成功后当前位置会被设为 `0 deg`。
4. 设置校准频率、波束指向、本振功率、中频功率和数据保存目录。
5. 按需要开启本振/中频：`manual` 只提示人工设置；`auto` 会实际下发仪器命令。
6. 点击全局“确认”。软件会锁定全局参数、移动真实转台、同步频谱仪扫频参数，并显示信号源设置提示。

全局“确认”可能导致真实转台运动和真实仪器配置变化，点击前应确认机械区域和射频输出安全。

### 7.3 Feed1～Feed4 顺序

| 阶段 | 打开的馈源 | 操作 |
|---|---|---|
| Feed1 功率测试 | Feed1 | 输入固定相位，点击本区“确认”和“开始测试” |
| Feed2 相位扫描 | Feed1 + Feed2 | Feed1 保持最佳相位，扫描 Feed2 |
| Feed3 相位扫描 | Feed1 + Feed2 + Feed3 | Feed1/2 保持最佳相位，扫描 Feed3 |
| Feed4 相位扫描 | Feed1～Feed4 | Feed1/2/3 保持最佳相位，扫描 Feed4；完成后生成汇总表 |

必须按 Feed1 → Feed2 → Feed3 → Feed4 的顺序执行。Feed2～Feed4 会优先使用当前进程缓存的前序最佳相位；没有缓存时会读取输出目录中的旧表。不要混用不同频点或不同波束角的结果。

扫描期间不要修改频谱仪、信号源、转台或连接线。UI0 没有单独“停止”按钮；强制退出时，当前阶段可能不会生成有效结果。

## 8. UI1 相位配置操作

### 8.1 基础设置

1. 启动 `THz_Phase_Config.exe`。
2. 选择 STM32 COM 口，点击“刷新”和“串口连接”。
3. 设置输出频率、本振功率和中频功率，点击基础设置“确认”。

输出频率会参与波束配相计算。UI1 的本振/中频按钮当前只显示状态，不控制真实信号源。

### 8.2 手动相位模式

1. 不勾选“通过波束指向配相”。
2. 输入 Feed1～Feed4 相位。允许范围为 `0～354.375 deg`，步长为 `5.625 deg`。
3. 按需要设置每路“使能”。
4. 点击“相位确认”。
5. 需要叠加 UI0 最佳相位时点击“自动校准”，否则直接点击“数据发送”。

### 8.3 波束指向配相模式

1. 勾选“通过波束指向配相”。
2. 设置 `θ₀`；四个馈源相位由输出频率、相邻馈源间距 15.52 mm 和 `θ₀` 计算，并量化到 5.625 deg。
3. `φ₀` 当前不参与计算。
4. 点击“相位确认”，再按需要点击“自动校准”和“数据发送”。

### 8.4 重要按钮

| 按钮 | 作用 |
|---|---|
| 初始同步 | 以期望 0 deg 为基础，读取 UI0 最佳相位偏移并写入发送队列；缺表的馈源保持 0 deg |
| 自动校准 | 把当前期望相位叠加 UI0 最佳相位偏移，会覆盖发送队列中的相位 |
| 数据发送 | 发送四路 `feed_id`、`phase_deg`、`enabled`，反馈窗显示完整 HEX 和发送结果 |
| 馈源使能 | 切换任一路使能时，会立即发送包含四路状态的完整帧 |

UI1 从 `config.ini` 的 `[paths] output_dir` 读取 UI0 校准表。若 UI0 在界面中临时选择了其他保存目录，应把有效表复制到配置的输出目录，或同步修改 `config.ini` 后重启 UI1。

## 9. 输出文件

| 文件名 | 生成时机 | 内容 |
|---|---|---|
| `TestData_Feed1_BDp30_212.xlsx` | Feed1 完成 | Feed1 单馈源功率测试 |
| `CalProcess_Feed2wrt1_BDp30_212.xlsx` | Feed2 完成 | Feed2 相对 Feed1 的扫描过程 |
| `CalProcess_Feed3wrt12_BDp30_212.xlsx` | Feed3 完成 | Feed3 相对 Feed1/2 的扫描过程 |
| `CalProcess_Feed4wrt123_BDp30_212.xlsx` | Feed4 完成 | Feed4 相对 Feed1/2/3 的扫描过程 |
| `CalData_MultiFeed_MultiBeamDir_212to224_6bit.xlsx` | Feed4 完成后 | 四馈源、多频点/多波束方向汇总 |

结果功率单位为 `uW`，过程表最大功率点会标红。

文件名为固定名称，不自动添加时间戳。每轮正式测试后建议立即复制到以下格式的归档目录：

```text
YYYYMMDD_频点GHz_波束角deg_样机编号
```

同时保存本轮 `config.ini` 副本。

## 10. 常见故障

| 现象 | 检查和处理 |
|---|---|
| 双击 EXE 无界面 | 确认已完整解压、`_internal` 齐全；检查杀毒软件拦截；不要只复制 EXE |
| 配置修改不生效 | 关闭 UI0/UI1 全部进程；确认修改的是 EXE 同级 `config.ini`，且文件没有变成 `config.ini.txt` |
| 串口列表没有目标 COM | 安装 x64 驱动，检查数据线和设备管理器，然后点击“刷新” |
| 串口连接失败/被占用 | 关闭串口助手；核对 COM 口和波特率；确认 STM32 与转台未使用同一端口 |
| 频谱仪连接失败 | 核对 `mode/profile/backend/资源名`；先在厂家工具中验证；TCPIP SOCKET 可试 `py`，GPIB 一般使用 `ivi` |
| 频谱仪连接但读不到有效功率 | 核对 `frequency_divisor`、中心频率、扫宽、marker、线缆和量程 |
| 信号源按钮无硬件动作 | UI1 按钮只做状态提示；需要 UI0 且 `signal_source.mode=auto` 才自动下发 |
| 转台方向或角度错误 | 停止测试，核对设零、站号、`pulses_per_degree`、机械方向和接线 |
| UI1 自动校准提示缺数据 | 检查 `[paths] output_dir` 中是否有本轮 UI0 的四个有效过程表 |
| Excel 未生成/保存失败 | 确认目录可写、磁盘空间充足，并关闭正在打开的同名 xlsx |
| 界面显示不完整 | 使用 1920×1080，Windows 缩放调为 100%～125% |

## 11. 安全注意事项

- 信号源 `auto` 模式会实际开启射频输出，连接被测件、衰减器和仪器前不得开启。
- 转台连接会设零，全局确认可能驱动转台运动；先清空运动区域并确认限位、急停和线缆余量。
- `frequency_divisor`、`pulses_per_degree`、GPIB/COM/IP 等关键参数必须由设备负责人复核。
- 固定文件名会覆盖旧结果，正式测试前先备份。
- 不得删除 `_internal`、替换其中 DLL/模板，或把 EXE 拆分到其他目录。

## 12. 建议验收项

- 两个 EXE、`config.ini`、本说明和 `_internal` 齐全。
- 未安装 Python/Conda 的目标电脑可以启动 UI0 和 UI1。
- 修改 `config.ini` 后，重启软件可以读取新默认值和输出目录。
- 模拟模式可以完成 Feed1～Feed4，并生成四个过程表和汇总表。
- UI1 模拟模式可以完成相位确认、自动校准和数据发送，反馈窗显示完整帧。
- 按项目范围分别验证 STM32、频谱仪、转台和信号源的真实连接。

