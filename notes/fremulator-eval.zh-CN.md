[English](fremulator-eval.md) | 简体中文

# FrEmulator 评估（时间盒）

对象：[simeonpilgrim/nikon-firmware-tools](https://github.com/simeonpilgrim/nikon-firmware-tools) 的 `Java/Emulator`。这是 Nikon Expeed（FR80 主核 + TX19 副核）的整机模拟器。问题是：它能不能直接跑 K-5 IIs 的 FR80 代码，替代或补充现在用的 Ghidra P-code 模拟（`tools/emulate_parse.py`）。

结论：**能**。`ScriptMode_parse_command` 在 FrEmulator 上跑出的结果与 Ghidra P-code 模拟逐条一致，速度快得多，而且不依赖 Ghidra/GhidraMCP。适合做"给定输入、跑一个纯计算函数"的批量验证；整机启动则需要外设模型，不在本次范围内。

## 1. 构建

- 仓库克隆到 `tools/nikon-firmware-tools/`（已加入 `.gitignore`）。
- 本机没有 Ant，`tools/fremu/build.sh` 直接用 `javac` 编译：JDK 25，`-source 8 -target 8`，349 个源文件，大约 7 秒。
- 唯一的障碍：`com.nikonhacker.ApplicationInfo` 原本由 Ant 从 `src/template/` 生成，脚本用 `sed` 代替。
- 依赖都在仓库的 `lib/` 里，不需要联网。

## 2. 测试程序

`tools/fremu/K5ParseHarness.java`，调用约定与 `emulate_parse.py` 相同：

- 映像 `fw/fwdc218b_dec.bin` 装到 `0x10000000`；
- 映射 `0xC0000000` 起 16 MiB 的 RAM；
- R4 = 对象、R5 = 命令串、R6 = 0x30 字节的 `cmd[]`（`cmd[0x25]` 预置 0xFF），RP 指向哨兵地址 `0x10ABFFF0`；
- 直接循环调用 `FrEmulator.onClockTick()`，PC 到达哨兵就停止，不用 MasterClock 和外设。

```bash
tools/fremu/build.sh "DEBUG_MODE EN" "REGION_CODE 3"
```

## 3. 结果

| 项目 | Ghidra P-code（`emulate_parse.py`） | FrEmulator（`K5ParseHarness`） |
| --- | --- | --- |
| 60 个命令（56 个正例 + 4 个反例） | `notes/emulate_parse_all.txt` | `notes/fremulator_parse_all.txt` |
| 返回值和 `cmd[]` 槽位 | — | **60/60 完全一致** |
| 总耗时 | 需要启动 GhidraMCP 服务器（分钟级），每批数秒 | 0.93 秒（含 JVM 启动） |
| 依赖 | Ghidra 工程 + MCP 服务器 + 允许内联脚本 | 只要 JDK |

每条命令执行 132 到约 1300 条指令。

指令覆盖：用同仓库的反汇编器 `Dfr` 把脚本模式代码区 `0x10600000–0x10620000`（128 KB，约 5.3 万条指令）反汇编，没有出现未识别的操作码。用到的指令包括 `LDI:20`、`ENTER/LEAVE`、`STM1/LDM1`、`DIV0S..DIV4S`、`BANDL/BORH/BTSTH` 等 FR80 指令。K-5 IIs 的主核与 Nikon Expeed 同属 FR80 系列，指令集兼容。

## 4. 局限

- 外设：模拟器的 IO 监听器（`Expeed4006IoListener` 等）按 Nikon 的寄存器布局实现，与 Pentax/Milbeaut 的外设地址不对应。任何访问 `0xFFFxxxxx` IO 或依赖中断、定时器的代码都需要另写模型。
- 系统服务：K-5 IIs 用的 RTOS 调用（`INT #0x40` 一类）在 FrEmulator 里按 Nikon 的约定处理，没有验证。
- 所以它目前只适合跑纯计算或纯内存的函数，例如命令解析、`SYSPARAM.TXT` 解析（`FUN_104A5ED2`）、校验和、解密等。

## 5. 能否用来模拟 AUTORUN 解释器

`AutoTest_load_autorun`（`0x1060940E`）本身只负责读文件：取大小（上限 20000 字节）、分配缓冲区、`Autorun_read` 读入，然后把缓冲区交给解释器对象（`param_1+0x60`）的四个方法：

| 地址 | 推测作用 |
| --- | --- |
| `0x1060A3E2` | 设置源码缓冲区和长度 |
| `0x1060A3EC` | 预处理/扫描（内部调用 `FUN_10609C18`） |
| `0x1060A48C` | 建立标号表等 |
| `0x1060A75A` | 从第 0 行开始执行 |

这些方法只操作内存里的源码缓冲区。因此可以跳过文件读取，在模拟内存里直接放入脚本文本，再依次调用上面四个方法。

- **解析和控制流**（`GOTO/GOSUB/IF/WHILE`、变量）属于纯计算，值得用 FrEmulator 跑。
- **会碰硬件的命令**：`PRINT`（屏幕）、`FILEOUT`/`FSEARCH`（文件系统）、`TIMERON`（定时器）、拍摄类命令。需要在其 `CALL` 目标处加断点，返回桩值；这和 `K5ParseHarness` 用 RP 哨兵地址停机是同一种做法。
- 前置工作：先逆向解释器对象的构造函数和字段布局（这四个方法在 Ghidra 里还没有建立成函数）。

结论：值得做，但属于下一步的独立任务，不在这次时间盒内。

## 6. 建议

1. 以后批量验证纯函数时优先用 FrEmulator，Ghidra P-code 留作交叉核对。
2. 下一个值得移植的是 `SYSPARAM.TXT` 解析器 `FUN_104A5ED2`：给定文件内容，直接读出对象各字段，验证 `sd-file-entrypoints.zh-CN.md` 中的键名和偏移。
3. 如果将来要跑开机流程，可以借鉴它的 `Platform` / `IoListener` 结构，为 K-5 IIs 的 IO 地址写最小桩，但工作量较大，需要单独评估。
