[English](memory-map.md) | 简体中文

# 内存映射与基础 API

## 固件容器布局（`fw/fwdc218b.bin`，0xAC0000 字节）

| 文件范围 | IV 位置 | 内容 | 解密后 |
| --- | --- | --- | --- |
| `0x000000–0x0000FF` | - | 明文头：魔数 `HOKKTKIYHTNTMU`、0x10 处的机型码 541（`0x21D`）、0x14 处的脚本编号 77681（`0x12F71`）、0x18 处的版本 BCD `01 07 18 10`、版权和机型字符串、0xFC 处的 `69FDABE0` | - |
| `0x000100–0x9FFFFF` | 0x000000 | FR80 主固件 | 映射到 `0x10000000` |
| `0xA00100–0xA7FFFF` | 0xA00000 | 第二段（升级代码中称作 C 段，大小 0x80000，写入偏移 0x500000×2） | - |
| `0xA80000–0xABFF7F` | 0xABFF80 | **副处理器固件**：ARM Cortex-M，小端，Thumb 指令 | `fw/subcpu_arm.bin` |
| `0xABFF80–0xABFFFF` | - | 第三段的 IV | - |

解密和加密工具是 `tools/pentax_fw.py`（`decode` / `encode` / `selftest` / `extract-sub`）。
解密后再加密能逐字节还原原文件（selftest 结果 `roundtrip identical: True`）；前两段的结果与 pfwtool 完全一致。
完整解密映像 `fw/fwdc218b_full_dec.bin` 的 SHA-256 为 `a31b6c8e88fefc634280235a3540486475aa349927b93137f0cfdf287eb4f4d3`。

副处理器固件开头是向量表：初始 SP 为 `0x200037B8`，复位向量为 `0x00000231`（Thumb）。
字符串包括 `NBADC0-init.`、`MSHS:Lo in TxRx`、`DUST-0 end.`、`PH-OFF !!!`、`CPU-VER %d`，推测负责防抖（SR）和除尘。
要分析时，在 Ghidra 中以 `ARM:LE:32:Cortex`、基址 0 导入即可，目前还没做。

升级加载函数（`fwup_load_image` @ `0x104B6A0E`）会校验文件大小：

| 文件 | 预期大小 |
| --- | --- |
| `FWDC218D.BIN` | 0xA00000 |
| `FWDC218C.BIN` | 0x80000 |
| `FWDC218B.BIN` | 0xA80000 或 0xAC0000 |

## 运行时地址空间（主 CPU，FR80）

| 地址 | Ghidra 内存块 | 说明 | 依据 |
| --- | --- | --- | --- |
| `0x00000000–0x00000FFF` | `IO_LO` | FR 内部 IO 寄存器，插件 pspec 已定义符号 | FR 架构惯例 |
| `0x10000000–0x10ABFFFF` | `ram`（映像） | 代码和只读数据；运行时直接读文件头（`DAT_10000010/14`） | 78% 的间接调用目标落在函数序言上 |
| `0xC0000000–0xC0FFFFFF` | `SDRAM_WORK` | 全局变量和单例，例如 `0xC006C090`（ScriptMode）、`0xC000468C`（0/1/2 模式值，选择 `DEBUG MODE`/`PC VENDOR` 标签文字，不是调试模式开关） | LDI:32 引用集中在 0xC000–0xC00F |
| `0xFFF00000–0xFFFFFFFF` | `IO_HI` | 外设寄存器，引用集中在 0xFFFFFxxx（6858 处） | LDI:32 引用分布 |

## RTOS 与基础库

- 固件里**没有**使用 `INT #0x40`（富士通 μITRON 的调用约定），所以插件自带的 `ResolveUTronSyscalls` 不适用。
  系统服务通过普通函数调用实现，例如 `mutex_lock` / `mutex_unlock`（`0x101F5510` / `0x101F5524`）。
- 代码是 C++ 风格：虚表格式为 `{int16 this_adj, int16 0, fnptr}`，单例通过 `*_instance()` 懒初始化。
- 已命名的函数（来源：`tools/names.tsv`，已写回 Ghidra 项目）：
  - 内存与字符串：`op_new`、`op_delete`、`sprintf`、`strcmp`
  - 文件系统：`fs_stat`、`FileSystem_instance`
  - 按键：`key_is_pressed` 和 `key_lookup`（按键码转成"字节下标 + 掩码"，表在 `0x1077C7B0`）
  - 固件头：`fwhdr_get_model_code`、`fwhdr_get_script_id`
  - 开机流程：`Boot_*`
  - 脚本模式：`ScriptMode_*`
  - 系统标志：`SysFlags_*` / `flags_*`

## 系统标志（持久化）

所有标志都位于同一个设置对象里，值为 `0x5AA5A55A` 表示开启，`0xFFFFFFFF` 表示关闭。修改后由 `SysFlags_commit` 写回存储。

| 偏移 | 标志 | 对应脚本命令 |
| --- | --- | --- |
| +0x04 | DEBUG_MODE | `[DEBUG_MODE EN/DIS]` |
| +0x08 | CFDOOR_OPEN | `[CFDOOR_OPEN EN/DIS]` |
| +0x0C | WRITE_CF_VNDR（推测） | `[WRITE_CF_VNDR EN/DIS]` |
| +0x10 | SCRIPT_EN_MODE | `[SCRIPT_EN_MODE EN/DIS]` |
| +0x18 | SW_DEBUG_MENU | `[SW_DEBUG_MENU EN/DIS]` |

## 辅助工具

| 工具 | 用途 |
| --- | --- |
| `tools/gh.py` | 调用 GhidraMCP HTTP 接口：反编译、交叉引用、字符串、反汇编清单（`lst` 需要 `GHIDRA_MCP_ALLOW_SCRIPTS=1`） |
| `tools/mkfunc.py` | 从任意地址往回找函数序言，并在 Ghidra 中建函数 |
| `tools/callers.py` | 搜索 32 位立即数和相对 CALL 形式的调用者，弥补 Ghidra 交叉引用缺失 |
