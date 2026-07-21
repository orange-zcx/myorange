# Makerobo K210 电赛视觉程序

本目录整理了 Makerobo/CanMV K210 在电赛小车视觉学习中使用的程序，包括摄像头测试、颜色识别、0–9 数字识别、串口通信、多目标搜索及 STM32F103 接收示例。

## 使用环境

- Makerobo K210（CanMV 固件）
- CanMV IDE
- OV2640 摄像头及板载 LCD
- KPU MNIST 模型（需要数字识别时）
- K210 外接串口 TX：已验证为 GPIO7
- 串口参数：115200、8N1

## 目录

- `01_basic`：摄像头、LCD 与画面方向测试。
- `02_color`：红色识别、位置判断及串口发送。
- `03_digit_recognition`：数字定位和 0–9 数字识别。
- `04_uart`：GPIO7 串口测试，以及数字识别结果发送。
- `05_target_lock`：抗抖动、多卡片检测和指定数字目标锁定实验。
- `06_diagnostics`：摄像头、LCD、Flash、SD 卡和串口接口检查。
- `stm32f103_examples`：STM32F103 HAL 工程中可参考的 `main.c` 示例。
- `models`：数字识别使用的 KPU 模型。

## 建议学习顺序

1. 运行 `01_basic/k210_camera_test.py`，确认摄像头和 LCD 正常。
2. 运行 `02_color/k210_color_red.py`，学习颜色识别。
3. 运行 `03_digit_recognition/k210_digit_roi_test.py`，确认数字卡片可以被定位。
4. 将 `models/uint8_mnist_cnn_model.kmodel` 烧录到 Flash 地址 `0x300000`。
5. 运行 `03_digit_recognition/k210_digit_recognition_0to9_flash_v2.py`，完成 0–9 数字识别。
6. 运行 `04_uart/k210_uart_confirm_gpio7.py`，确认 K210 与 STM32F103 的串口连线。
7. 运行 `04_uart/k210_digit_recognition_uart_gpio7.py`，把数字识别结果发送给 STM32F103。
8. 最后学习 `05_target_lock` 中的抗抖和指定目标锁定程序。

## 当前推荐程序

- 稳定的 0–9 数字识别：`03_digit_recognition/k210_digit_recognition_0to9_flash_v2.py`
- 数字识别并通过 GPIO7 发送：`04_uart/k210_digit_recognition_uart_gpio7.py`
- K210 全接口检查：`06_diagnostics/k210_interface_check.py`
- 红色目标位置发送：`02_color/k210_red_position_uart.py`

## 模型说明

Flash 版数字识别程序默认从 `0x300000` 加载模型，模型大小为 `550124` 字节。请先使用 K210 烧录工具将 `models/uint8_mnist_cnn_model.kmodel` 写入该地址。SD 卡版本则需要把模型放在 `/sd/KPU/mnist/` 下。

## 接线提示

- K210 TX（GPIO7）连接 STM32F103 USART RX。
- 两块开发板的 GND 必须相连。
- 两块板可以继续分别通过 USB 供电。
- 不要把两个 TX 引脚直接相连。

## 注意

部分 `05_target_lock` 文件属于逐步学习和参数试验版本。实际比赛前应固定摄像头高度、数字卡尺寸、光照环境，并针对现场重新调整阈值、置信度和目标区域。
