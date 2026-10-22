[English](k5-vs-k5iis.md) | 简体中文

# K-5 1.16 与 K-5 IIs 1.07 对比

K-5（2010）是 K-5 IIs（2013）的前代机型。比较这两个固件，一是用来交叉验证本项目的函数命名，二是确认工厂脚本机制在两代之间是否一致。

## 样本

| 项目 | K-5 1.16 | K-5 IIs 1.07 |
| --- | --- | --- |
| 来源 | 理光官方下载 `k5_v116m.zip`（内含 `fwdc209b.bin`）；分析用的副本取自 [twang2218/pentax-firmware](https://github.com/twang2218/pentax-firmware) `k5/k5-v1.16-fwdc209b.bin`，`tools/firmware_setup.py` 会按哈希校验 | 官方 `k5_2s107.zip` |
| 文件 | `fw/k5-v116-fwdc209b.bin`，0xA80000 字节 | `fw/fwdc218b.bin`，0xAC0000 字节 |
| 解密 | `fw/k5-v116_dec.bin`，SHA-256 `e9dac980fa20a19a9a08a70c355fcdfe319b10789e8b51fb95cc2e370fcb91d8` | `fw/fwdc218b_full_dec.bin` |
| 头部机型码 0x10 | 505（`0x1F9`） | 541（`0x21D`） |
| 头部脚本编号 0x14 | 77430 | 77681 |
| 版本 BCD 0x18 | `01 10 1A 1D` | `01 07 18 10` |
| 副处理器段 | 无 | `0xA80000–0xABFF7F` |

K-5 的容器只有前两段，`tools/pentax_fw.py` 已按文件大小选择分段（`LAYOUTS`），`selftest` 能逐字节还原原文件。解密后命令字符串、路径都是明文，说明 XOR 方案在两代之间没有变化。

## 工厂脚本

- **K-5 的脚本文件名是 `00077430.505`**，同样需要 `DEVELOP.MOD`。格式串 `C:\%08d.%03d` 和 `DEVELOP.MOD` 的异或 0x29 常量副本都在（K-5 `0x10799540` 附近）。
- 命令表与 K-5 IIs 几乎一样，K-5 IIs 只多了 `DIS_AF_F28` 和 `ONLY_AF_F28`（对应 K-5 IIs 新增的 F2.8 AF 传感器），其余 54 个命令字符串、`KB%03d*.ADJ/CSV/BIN/USR/LOG` 文件名、`WAIT...`/`COMPLETE...`/`ERROR...` 提示都相同。
- 所以 `make_debug_card.py` 只要换掉文件名就能给 K-5 用，命令表索引需要按 K-5 的 `ScriptMode_parse_command`（`0x1060B526`）重新核对：少了两个命令，后面的槽位可能前移。本项目没有 K-5 机身，暂不提供 K-5 的卡文件。

## 其他 SD 卡入口

- 共同的路径字符串 54 个：`AUTORUN.541/505`（按机型码拼接）、`CHKDAT`、`SYSPARAM.TXT`、`NOWAIT`、`KBCHG.BIN` 等都在。
- 仅 K-5 IIs 有：`FWDC218B/C/D/S.BIN`、`KB541[B/C/S].BIN`、`SR%04d.bin`；仅 K-5 有：`FWDC209B/C/D.BIN`、`KB505[B/C].BIN`。差别只是机型编号，以及 K-5 IIs 多了副处理器段（`S`）。
- SYSPARAM 键：K-5 IIs 的 96 个键里，K-5 只缺 `ENABLE_RELEASE_LAP_TIME_DISPLAY` 和 `ENABLE_SR_EVALUATION`。指南里建议的第一个 SYSPARAM 实验在 K-5 上不可用。
- `DEBUG MODE`、`DISABLE DEBUG MODE` 等界面字符串两边都有。

## 固件校验标记

两个映像都在相同偏移处有 `0x10001 × 机型码` 后接 `A55A5AA5` 的标记（K-5 是 `0x01F901F9`）：`0x1F8`、`0xFFFF0`、`0x7FFFF8`、`0x800008`、`0x9FFFF8`、`0xA00070`、`0xA77FF8`、`0xA7FBF0`，K-5 IIs 另有副处理器段末尾的 `0xABFFF0`。详见 `firmware-checksum.zh-CN.md`。

## 函数命名迁移

工具：`tools/port_names.py fw/fwdc218b_dec.bin fw/k5-v116_dec.bin tools/names.tsv notes/k5-v116-names.tsv`，纯 Python，不依赖 Ghidra。

- 第一轮按字节模式匹配（把 `LDI:32`/`LDI:20` 立即数和 `CALL` 相对偏移当通配符），唯一命中 34 个。
- 第二轮利用"同一区域内代码整体平移"的特点：按最近的已匹配函数预测位置，消除多重命中（34 个），对零命中的函数在预测位置附近按相同半字比例打分（3 个，得分 0.85–0.94）。
- 合计 **71/75**。交叉校验：匹配函数里指向其他已命名函数的 `LDI:32` 立即数，在 K-5 中都指向对应的迁移地址，**30/30 一致**。
- 平移量随地址单调增长，从 `0x101F55xx` 一带的 `0x1E8` 到 `0x106Exxxx` 一带的 `0x603C`，没有跳变，进一步说明匹配可信。
- 未匹配的 4 个：`ScriptMode_load_script`（最高 0.72）、`fwup_load_image`（0.81）、`SysParam_load`（0.67）、`SwitchTest_draw`（0.50）。它们在两代之间有实质改动（例如 K-5 少了 LAP_TIME 键，SWITCH TEST 少了 F2.8 相关按键），需要在 Ghidra 中从调用者手工确认。

部分关键地址（K-5 1.16）：

| 函数 | K-5 IIs 1.07 | K-5 1.16 |
| --- | --- | --- |
| `Boot_special_poweron` | `0x105E81D8` | `0x105E3DD2` |
| `ScriptMode_files_present` | `0x1060F57A` | `0x1060B154` |
| `ScriptMode_parse_command` | `0x1060F950` | `0x1060B526` |
| `ScriptMode_execute` | `0x1061000E` | `0x1060BBA4` |
| `SysFlags_set_debug_mode` | `0x10615F40` | `0x10611980` |
| `SysFlags_is_debug_mode` | `0x10615F70` | `0x106119B0` |
| `ui_show_debug_mode_label` | `0x10245F40` | `0x10245ACC` |
| `AutoTest_load_autorun` | `0x1060940E` | `0x10604FF0` |
| `fs_stat` | `0x106C1D86` | `0x106BD40C` |

完整列表见 `notes/k5-v116-names.tsv`。

## Ghidra 项目

K-5 单独放在 `ghidra/K5/K5v116.gpr`（程序 `k5-v116_dec.bin`，FR81 大端，基址 `0x10000000`），种子来自 `tools/gen_seeds.py`（`notes/k5-v116-seeds.txt`），分析日志 `notes/k5-v116-analyze.log`（只保留在本地），统计 `notes/k5-v116-ghidra-report.txt`。没有并入 `K5IIs.gpr`，是为了不和正在运行的 GhidraMCP 服务争项目锁。

全量分析耗时 1719 秒，已成功保存。两边的统计对照如下：

| 指标 | K-5 1.16 | K-5 IIs 1.07 |
| --- | --- | --- |
| 函数 | 30457 | 33927 |
| 指令 | 1453481 | 1537956 |
| 错误书签 | 1928（`0x10100000` 区 1902） | 2381（`0x10100000` 区 2363） |
| 未解析操作码前几名 | `0793`×129、`9F6F`×67、`9F2B`×37、`07A1`×33 | `0793`×205、`9F6F`×69、`07A1`×48、`0798`×44 |

两者的错误都集中在 `0x10100000–0x101FFFFF`，未解析的操作码也基本相同（`07xx`、`9Fxx`、`BExx`、`17xx`）。说明这个区域在两代机身里是同一类代码或数据，FR81 语言模块解不出来，而不是 K-5 IIs 独有的问题。K-5 的代码量约为 K-5 IIs 的 94%。
