# 上位机与 STM32 通信协议交接说明

本文档面向 STM32 下位机开发者，说明当前 PySide6 上位机已经实现的数据发送链路、串口参数、协议帧结构、字段含义、CRC 算法、测试帧，以及新移相芯片方案下 STM32 侧需要完成的相位编码工作。

当前项目已经从旧方案的“相位 + 幅值”控制切换为“只下发相位”。上位机只发送馈源编号、相位角和使能状态；不再发送幅值字段。STM32 负责把 `phase_deg` 转换为新移相芯片 `IPS-1924-6C` 与串并转换芯片 `WQD0032H` 所需的控制位、电压状态和锁存时序。

## 1. 当前代码位置

| 模块 | 文件 | 说明 |
|------|------|------|
| 协议编码 | `src/thz_calibration/protocol.py` | 帧头、命令字、长度、JSON payload、CRC8、帧尾 |
| 下位机控制 | `src/thz_calibration/controllers/device_controller.py` | 将 `FeedState` 队列编码成协议帧并发送 |
| 串口传输 | `src/thz_calibration/transport/serial_transport.py` | pyserial 串口写入与 `readline()` 读取返回 |
| 模拟传输 | `src/thz_calibration/transport/simulated.py` | 无硬件时模拟 ACK |
| 相位配置 UI | `src/thz_calibration/ui/phase_config_window.py` | 点击“数据发送”后发送相位队列 |
| 配置项 | `src/thz_calibration/config.py` | 串口端口、波特率、模拟/真实模式切换 |

注意：`FeedState` 模型中仍保留内部 `amplitude` 属性，主要用于历史逻辑兼容和仿真流程；`FeedState.as_payload()` 已不序列化该字段，协议帧中不会出现 `amplitude`。

## 2. 串口参数

当前上位机串口配置如下：

| 参数 | 当前值 |
|------|--------|
| 波特率 | `9600` |
| 数据位 | `8` |
| 校验位 | `N` |
| 停止位 | `1` |
| 读取超时 | `0.5 s` |
| DTR | `False` |
| RTS | `False` |

上位机默认运行模式为模拟下位机：

```python
device_mode = "simulated"
```

实机联调时需要在 `src/thz_calibration/config.py` 中切换为：

```python
device_mode = "serial"
```

也可以在界面中选择串口并点击“串口连接”，连接后会使用真实串口发送。

## 3. 总体发送流程

相位配置界面的发送链路如下：

```text
点击“数据发送”
  -> 读取相位发送队列 phase_queue
  -> DeviceController.encode_feed_states()
  -> ProtocolEncoder.encode_set_feeds()
  -> SerialTransport.send()
  -> serial.write(frame)
  -> serial.readline()
  -> 信息反馈窗显示发送数据、HEX 帧、发送成功/失败
```

若发送队列为空，上位机会提示用户先执行“相位确认”或“自动校准”，不会发送空帧。

UI0 校准数据测试界面在扫描过程中也走同一条底层发送链路：

```text
每个相位扫描点
  -> CalibrationEngine.scan_feed()
  -> DeviceController.apply_feed_states()
  -> ProtocolEncoder.encode_set_feeds()
  -> SerialTransport.send()
```

每成功发送一条 `SET_FEEDS` 后，终端会打印一行本次下发的 CE 片选状态和 4 个馈源相位，不打印 HEX，便于联调确认：

```text
校准发送状态：CE1=打开 Feed1=0.000000 deg, CE2=打开 Feed2=5.625000 deg, CE3=关闭 Feed3=0.000000 deg, CE4=关闭 Feed4=0.000000 deg
```

## 4. 二进制帧格式

当前协议沿用旧方案的串口帧风格：

```text
AA + VERSION + CMD + LEN_H + LEN_L + PAYLOAD + CRC8 + BB
```

逐字节说明：

| 偏移 | 长度 | 字段 | 当前值/说明 |
|------|------|------|-------------|
| 0 | 1 | 帧头 | `0xAA` |
| 1 | 1 | 协议版本 | `0x01` |
| 2 | 1 | 命令字 | 见“命令字” |
| 3 | 1 | Payload 长度高字节 | 大端序 |
| 4 | 1 | Payload 长度低字节 | 大端序 |
| 5 | N | Payload | UTF-8 JSON 字节流 |
| 5+N | 1 | CRC8 | 对 `VERSION + CMD + LEN_H + LEN_L + PAYLOAD` 计算 |
| 6+N | 1 | 帧尾 | `0xBB` |

长度字段只表示 Payload 的字节数，不包含帧头、版本、命令字、长度字段、CRC、帧尾。

## 5. 命令字

| 命令 | 值 | 上位机当前使用情况 | Payload |
|------|----|--------------------|---------|
| `PING` | `0x01` | 预留/测试 | `{}` |
| `SET_FEEDS` | `0x10` | 当前主要使用 | `{"feeds":[...]}` |
| `SHUTDOWN_ALL` | `0x11` | 已有编码函数，界面暂未重点使用 | `{"enabled":false}` |

当前相位配置界面点击“数据发送”使用 `SET_FEEDS`。

## 6. Payload 格式

Payload 是 UTF-8 JSON。上位机编码时使用紧凑格式，不额外插入空格：

```python
json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
```

### 6.1 SET_FEEDS

Payload 结构：

```json
{
  "feeds": [
    {
      "feed_id": 1,
      "phase_deg": 0.0,
      "enabled": true
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 范围/说明 |
|------|------|-----------|
| `feeds` | array | 馈源状态数组；当前 UI 通常一次发送 4 个馈源 |
| `feed_id` | int | `1`~`4`，分别对应 CE1~CE4 |
| `phase_deg` | float | 相位角，单位 degree；上位机按度发送，不直接发送芯片 bit code |
| `enabled` | bool | 当前馈源是否使能 |

CE 对应关系：

| Feed | 片选 |
|------|------|
| Feed1 | CE1 |
| Feed2 | CE2 |
| Feed3 | CE3 |
| Feed4 | CE4 |

新项目不再发送幅值字段；STM32 侧解析 `SET_FEEDS` 时不应等待或校验 `amplitude`。如果收到旧版本工具发来的 `amplitude`，建议忽略该字段，以保持向前兼容。

### 6.2 SHUTDOWN_ALL

Payload：

```json
{"enabled":false}
```

建议下位机收到后关闭所有馈源输出，或将 4 个馈源全部置为禁用状态。

### 6.3 PING

Payload：

```json
{}
```

用于后续连通性测试。当前 UI 暂未把 `PING` 做成按钮。

## 7. CRC8 算法

当前上位机 CRC8 参数：

| 参数 | 当前值 |
|------|--------|
| 初值 | `0x00` |
| 多项式 | `0x07` |
| 输入反射 | 否 |
| 输出反射 | 否 |
| 结果异或 | 无 |
| 计算范围 | `VERSION + CMD + LEN_H + LEN_L + PAYLOAD` |

Python 参考实现：

```python
def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc <<= 1
            crc &= 0xFF
    return crc
```

C 参考实现：

```c
#include <stdint.h>
#include <stddef.h>

uint8_t crc8_calc(const uint8_t *data, size_t len)
{
    uint8_t crc = 0x00;

    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8; ++bit) {
            if (crc & 0x80) {
                crc = (uint8_t)((crc << 1) ^ 0x07);
            } else {
                crc = (uint8_t)(crc << 1);
            }
        }
    }

    return crc;
}
```

下位机校验时，应从版本字节开始计算，到 Payload 最后一个字节结束。

## 8. STM32 串口解析建议

STM32 串口接收可按以下状态机解析：

1. 在字节流中寻找 `0xAA`。
2. 读取固定头部：`VERSION, CMD, LEN_H, LEN_L`。
3. 检查版本号是否为 `0x01`。
4. 计算 Payload 长度：`payload_len = (LEN_H << 8) | LEN_L`。
5. 读取 `payload_len` 字节 Payload。
6. 读取 CRC8。
7. 读取帧尾，要求为 `0xBB`。
8. 对 `VERSION + CMD + LEN_H + LEN_L + PAYLOAD` 计算 CRC8，并与收到的 CRC 比较。
9. Payload 按 UTF-8 JSON 解析。
10. 根据 `CMD` 执行相应动作。

伪代码：

```c
if (frame[0] != 0xAA) {
    // find next frame head
}

uint8_t version = frame[1];
uint8_t cmd = frame[2];
uint16_t payload_len = ((uint16_t)frame[3] << 8) | frame[4];
uint8_t *payload = &frame[5];
uint8_t recv_crc = frame[5 + payload_len];
uint8_t tail = frame[6 + payload_len];

if (version != 0x01) {
    // version error
}

if (tail != 0xBB) {
    // tail error
}

uint8_t calc_crc = crc8_calc(&frame[1], 4 + payload_len);
if (calc_crc != recv_crc) {
    // crc error
}

// parse payload JSON and execute command
```

## 9. 新移相芯片对接要点

### 9.1 相关手册

本节依据以下芯片手册整理，最终硬件实现以手册和实际 PCB 连接为准：

| 手册 | 用途 |
|------|------|
| `docs/芯片手册/数控移相芯片IPS-1924-6C.pdf` | 6 位数控移相器，相位值与 V1~V12 控制电压关系 |
| `docs/芯片手册/串并转换芯片WQD0032H.pdf` | 6 位串并转换驱动器，TTL 串行输入转 -5V~0V 互补输出 |

旧方案中的幅相 DAC 编码、幅值电压计算、10-bit DAC 设定值不适用于当前新项目。

### 9.2 上位机相位值与 STM32 编码边界

上位机只发送：

```text
feed_id + phase_deg + enabled
```

上位机不发送以下内容：

- 幅值/幅度。
- 波束指向角；该参数用于转台电机和实验记录，当前不下发给 STM32。
- 6-bit 相位编码。
- V1~V12 的 0/-5V 电压表。
- WQD0032H 的串行 bit 流。

STM32 收到 `phase_deg` 后建议先做归一化：

```c
phase_norm = phase_deg % 360.0;
if (phase_norm < 0) {
    phase_norm += 360.0;
}
```

当前上位机校准扫描点为 `0, 5.625, 11.25, ..., 354.375`，共 64 点。若下位机需要把相位角转换为 6-bit 索引，可按 5.625° 量化：

```c
phase_index = round(phase_norm / 5.625) & 0x3F;
```

IPS-1924-6C 手册真值表使用负相位标注，例如 `-5.625°`、`-90°`、`-354.375°`。上位机界面的正相位值与芯片负相移之间的符号关系，需要在整机 RF 联调时确认。若硬件定义为“上位机正相位 = 芯片负相移补偿量”，则 STM32 可直接按 `phase_index` 选择对应负相移状态；若方向相反，则需要使用：

```c
chip_index = (64 - phase_index) & 0x3F;
```

无论采用哪种符号约定，最终 V1~V12 输出必须以 IPS-1924-6C 手册真值表为准。

### 9.3 IPS-1924-6C 控制电压真值表

IPS-1924-6C 是 19~24GHz GaAs MMIC 6 位数控移相器，控制电压为 `0V / -5V`。手册中 V1~V12 为控制端口，典型真值表如下：

| V1 | V2 | V3 | V4 | V5 | V6 | V7 | V8 | V9 | V10 | V11 | V12 | 相位 |
|----|----|----|----|----|----|----|----|----|-----|-----|-----|------|
| -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | 基态 |
| 0 | -5 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5.625° |
| -5 | 0 | 0 | -5 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -11.25° |
| -5 | 0 | -5 | 0 | 0 | -5 | -5 | 0 | -5 | 0 | -5 | 0 | -22.5° |
| -5 | 0 | -5 | 0 | -5 | 0 | 0 | -5 | -5 | 0 | -5 | 0 | -45° |
| -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | 0 | -5 | -5 | 0 | -90° |
| -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | 0 | -5 | 0 | -5 | -180° |
| 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | 0 | -5 | -354.375° |

实现提示：

- `V1/V2`、`V3/V4`、`V5/V6`、`V7/V8`、`V9/V10`、`V11/V12` 是 6 组互补控制端。
- 基态下每组为 `奇数 V = -5V，偶数 V = 0V`。
- 选中某一相位控制位时，对应互补对翻转为 `奇数 V = 0V，偶数 V = -5V`。
- `-180°` 行请按手册执行：该行同时给出了 `V9/V10` 与 `V11/V12` 的翻转状态，固件不要沿用旧方案或凭旧 DAC 公式推断。
- 64 个具体相位点的最终编码应在 STM32 固件中用查表方式固化，并在逻辑分析仪 + 实测功率联调中验证。

### 9.4 WQD0032H 串并转换与输出关系

WQD0032H 是 6 位串并转换驱动器，输入兼容 TTL，输出为 `-5V~0V` 互补信号，适合驱动 IPS-1924-6C 的 6 组互补控制端。

关键时序与逻辑：

| 项目 | 手册约定 |
|------|----------|
| `SEL` | 低电平选通；高电平时 CK/DATA 被封锁 |
| `CK` | 下降沿触发 DATA 进入内部 6-bit 移位寄存器 |
| `DARY` | 上升沿触发 6 位缓冲器输出 |
| 串入顺序 | `D1` 最先串入，`D6` 最后串入 |
| 级联 | 多片级联时 CK 和 DARY 可并联；N 片扩展为 6N 位 |
| 输入逻辑 | 逻辑 0 对应 0V，逻辑 1 对应 5V；手册建议 0~3.3V 输入性能更佳 |
| 输出逻辑 | 逻辑 0 对应 -5V，逻辑 1 对应 0V |

WQD0032H 数据真值表：

| 串行输入 Dx | 输出 TPx | 输出 TNx |
|-------------|----------|----------|
| 0 | 0 | 1 |
| 1 | 1 | 0 |

结合输出逻辑电平可得到：

| 串行输入 Dx | TPx 电压 | TNx 电压 |
|-------------|----------|----------|
| 0 | -5V | 0V |
| 1 | 0V | -5V |

若 PCB 按 `TPx -> V奇数`、`TNx -> V偶数` 连接，则：

| Dx | IPS 控制对状态 | 含义 |
|----|----------------|------|
| 0 | `V奇数=-5V, V偶数=0V` | 基态/该位未选中 |
| 1 | `V奇数=0V, V偶数=-5V` | 该位选中 |

若 PCB 连接相反，则 bit 需要取反。下位机固件应以实际原理图为准确认 TP/TN 与 V1~V12 的对应关系。

建议的单片 WQD0032H 与 IPS 控制对映射如下，最终以 PCB 为准：

| WQD 位 | IPS 控制对 | 手册相位权重参考 |
|--------|------------|------------------|
| D1 / TP1/TN1 | V1/V2 | 5.625° |
| D2 / TP2/TN2 | V3/V4 | 11.25° |
| D3 / TP3/TN3 | V5/V6 | 22.5° |
| D4 / TP4/TN4 | V7/V8 | 45° |
| D5 / TP5/TN5 | V9/V10 | 90° |
| D6 / TP6/TN6 | V11/V12 | 180° 分支，注意按手册真值表验证 |

### 9.5 STM32 输出时序建议

对某个 Feed 写入相位时，建议流程如下：

1. 根据 `feed_id` 选择 CE1~CE4 对应的 WQD0032H `SEL` 或板级片选。
2. 将 `phase_deg` 归一化并量化到 64 个相位点。
3. 查表得到 6 位串行数据 `D1..D6`。
4. `SEL` 拉低选通。
5. 按 `D1 -> D6` 顺序输出 DATA，每一位在 `CK` 下降沿移入。
6. 6 位全部移入后，给 `DARY` 一个上升沿锁存输出。
7. 根据硬件需要释放 `SEL`。
8. 若 CE1~CE4 独立，则对每个 Feed 重复以上过程；若硬件采用级联，则按级联总位数 `6N` 组织 bit 流。

## 10. 测试帧

以下测试帧由当前上位机代码实际生成，可直接用于 STM32 串口接收和 CRC 校验联调。

### 10.1 SET_FEEDS 示例

Payload：

```json
{"feeds":[{"feed_id":1,"phase_deg":0.0,"enabled":true},{"feed_id":2,"phase_deg":30.0,"enabled":true},{"feed_id":3,"phase_deg":60.0,"enabled":true},{"feed_id":4,"phase_deg":90.0,"enabled":true}]}
```

Payload 长度：

```text
194 bytes = 0x00C2
```

整帧长度：

```text
201 bytes
```

CRC8：

```text
0x13
```

完整 HEX：

```text
aa 01 10 00 c2 7b 22 66 65 65 64 73 22 3a 5b 7b 22 66 65 65 64 5f 69 64 22 3a 31 2c 22 70 68 61 73 65 5f 64 65 67 22 3a 30 2e 30 2c 22 65 6e 61 62 6c 65 64 22 3a 74 72 75 65 7d 2c 7b 22 66 65 65 64 5f 69 64 22 3a 32 2c 22 70 68 61 73 65 5f 64 65 67 22 3a 33 30 2e 30 2c 22 65 6e 61 62 6c 65 64 22 3a 74 72 75 65 7d 2c 7b 22 66 65 65 64 5f 69 64 22 3a 33 2c 22 70 68 61 73 65 5f 64 65 67 22 3a 36 30 2e 30 2c 22 65 6e 61 62 6c 65 64 22 3a 74 72 75 65 7d 2c 7b 22 66 65 65 64 5f 69 64 22 3a 34 2c 22 70 68 61 73 65 5f 64 65 67 22 3a 39 30 2e 30 2c 22 65 6e 61 62 6c 65 64 22 3a 74 72 75 65 7d 5d 7d 13 bb
```

### 10.2 SHUTDOWN_ALL 示例

Payload：

```json
{"enabled":false}
```

Payload 长度：

```text
17 bytes = 0x0011
```

整帧长度：

```text
24 bytes
```

CRC8：

```text
0xB0
```

完整 HEX：

```text
aa 01 11 00 11 7b 22 65 6e 61 62 6c 65 64 22 3a 66 61 6c 73 65 7d b0 bb
```

### 10.3 PING 示例

Payload：

```json
{}
```

Payload 长度：

```text
2 bytes = 0x0002
```

整帧长度：

```text
9 bytes
```

CRC8：

```text
0xDC
```

完整 HEX：

```text
aa 01 01 00 02 7b 7d dc bb
```

## 11. 返回 ACK/NACK

当前上位机串口发送后调用：

```python
response = self._serial.readline()
```

当前逻辑还没有强制解析正式 ACK/NACK；只要串口写入没有异常，`SerialTransport` 会认为发送动作完成。如果下位机有返回内容，上位机会把返回字节转成 HEX 消息保存到 `TransportResponse.message`。

建议 STM32 第一阶段先返回简单 ASCII 行，便于上位机 `readline()` 捕获：

```text
ACK\n
```

或：

```text
NACK:<错误码>\n
```

建议错误码：

| 错误码 | 含义 |
|--------|------|
| `CRC` | CRC 校验失败 |
| `TAIL` | 帧尾错误 |
| `LEN` | 长度错误 |
| `JSON` | JSON 解析失败 |
| `CMD` | 未支持命令 |
| `FEED` | Feed 编号非法 |
| `PHASE` | 相位范围非法 |
| `CODE` | 相位码查表失败 |
| `SHIFT` | WQD0032H 串行移位失败 |
| `LATCH` | DARY 锁存失败 |

后续如果需要更严格的返回协议，可扩展为同样的 `AA + VERSION + CMD + LEN + PAYLOAD + CRC + BB` 返回帧，但当前上位机尚未实现返回帧解析。

## 12. STM32 执行建议

收到 `SET_FEEDS` 后建议按以下顺序执行：

1. 校验帧头、帧尾、长度、CRC。
2. 解析 JSON。
3. 遍历 `feeds` 数组。
4. 校验 `feed_id` 是否为 1~4。
5. 校验 `enabled` 是否为布尔值。
6. 校验 `phase_deg` 是否在可接受范围内，建议按 `phase_deg % 360` 归一化。
7. 根据 `feed_id` 选择对应 CE：
   - 1 -> CE1
   - 2 -> CE2
   - 3 -> CE3
   - 4 -> CE4
8. 根据 IPS-1924-6C 手册和实际 PCB 连接，将 `phase_deg` 转换为 6 位 WQD0032H 串行数据。
9. 按 WQD0032H 手册要求完成 `SEL`、`DATA`、`CK`、`DARY` 时序。
10. 全部馈源写入成功后返回 `ACK\n`。

如果某个 Feed 写入失败，建议停止后续写入并返回 `NACK:SHIFT\n`、`NACK:LATCH\n` 或更具体的错误码。

## 13. 上位机当前行为注意事项

1. 配置界面点击“数据发送”前，必须先执行“相位确认”或“自动校准”，否则发送队列为空。
2. 点击“数据发送”后，信息反馈窗会打印：
   - 每个 Feed 的相位和使能状态。
   - 完整发送帧 HEX。
   - 发送成功或失败信息。
3. 当前上位机在相位校准流程中也会调用同一套 `SET_FEEDS` 协议。
4. 校准扫描每成功下发一条数据，终端会打印一行 `CE1~CE4` 打开/关闭状态和 `Feed1~Feed4` 的相位值，用于确认发送序列。
5. 第一版幅度对齐未实现，且新项目协议不再发送幅值字段。
6. 64 个相位点到 WQD0032H bit 流、TP/TN 与 V1~V12 的连接关系、ACK/NACK 正式返回格式仍需由下位机方案冻结后更新。

## 14. 联调清单

- [ ] STM32 能在串口字节流中正确定位 `0xAA` 帧头。
- [ ] STM32 能正确解析大端 Payload 长度。
- [ ] STM32 CRC8 与本文测试帧一致。
- [ ] STM32 能解析 `SET_FEEDS` JSON。
- [ ] STM32 不再要求 `amplitude` 字段。
- [ ] Feed1~Feed4 与 CE1~CE4 映射正确。
- [ ] `phase_deg` 归一化和 5.625° 量化正确。
- [ ] 上位机正相位与 IPS 手册负相位的符号约定已通过 RF 联调确认。
- [ ] IPS-1924-6C 的 V1~V12 真值表查表正确。
- [ ] WQD0032H 的 `D1..D6` 串入顺序正确。
- [ ] WQD0032H 的 `SEL`、`CK`、`DATA`、`DARY` 时序正确。
- [ ] TP/TN 与 V1~V12 的 PCB 连接方向确认，必要时完成 bit 取反。
- [ ] 成功执行后返回 `ACK\n`。
- [ ] 异常场景返回可诊断的 `NACK:<错误码>\n`。
- [ ] 配置界面信息反馈窗能看到发送 HEX 和发送成功信息。
- [ ] 校准扫描终端能逐条打印实际下发的 CE1~CE4 片选状态和 Feed1~Feed4 相位值。
