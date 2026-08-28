馈源相位校准软件便携版

1. THz_Calibration.exe：启动馈源间相位校准界面（UI0）。
2. THz_Phase_Config.exe：启动馈源阵输出相位配置界面（UI1）。
3. config.ini：外部运行参数。修改后需要完全退出并重新启动软件。
4. output：默认 Excel 输出目录。

目标电脑不需要安装 Python 或 Conda。

真实硬件注意事项：
- STM32/转台可能需要安装对应的 USB 串口驱动。
- TCPIP SOCKET 仪器可在 config.ini 中尝试 visa_backend=py。
- GPIB 通常需要安装厂商 VISA Runtime、GPIB 控制器驱动，并使用 visa_backend=ivi。
- 软件、VISA Runtime 和硬件驱动的位数应保持一致，本发布包为 Windows x64。
