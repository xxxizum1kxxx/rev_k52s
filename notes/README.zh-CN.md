[English](README.md) | 简体中文

# Pentax K-5 IIs 固件 1.07 分析记录

## 样本

固件本体**不包含**在本仓库中。请从理光官网获取，再用 `tools/firmware_setup.py` 准备 `fw/` 目录（见根目录 README）。工具会校验以下哈希：

| 文件 | SHA-256 |
| --- | --- |
| `k5_2s107.zip`（官方下载） | `c2352d91669c8dce47fe84298baa47dedaa438b156a834a8a8a130f84e14db1f` |
| `fw/fwdc218b.bin`（原始，加扰） | `36b626a9ecd02e22161a1f3ef4e764f7641c2565bb82c866977aeb9eaad5ac97` |
| `fw/fwdc218b_dec.bin`（pfwtool 解密） | `8379b15c058dfa6cb597ef159b3920c50722c033c7e83a0e8a55a46a91ffecd1` |

大小 0xAC0000。头部 `HOKKTKIYHTNTMU`，`Copyright` 位于 0x24，对应 pfwtool 的大端分支：
`[0x100, 0xA00000)` 和 `[0xA00100, 0xA80000)` 两段用 IV@0 去混淆。
`0xA80000` 起的尾段是 ARM 副处理器映像，已由 `tools/pentax_fw.py` 解密，见 `memory-map.zh-CN.md`。

## 加载
- 语言：`fr81:BE:16:default`，编译器规格 `fcc911`（FR81 = FR80 + FPU 的超集）
- 基址：**文件偏移 0 对应 0x10000000**（整个映像线性映射）
  - 证据 1：`LDI:32 #imm,Ri` 后接 `CALL @Ri` 共 128,493 处，目标地址减去 0x10000000 后，有 99,755 处（78%）正好落在 FR 函数序言上（`ST RP,@-R15` / `ENTER` / `STM1`）。其他候选基址都不超过 20%。
  - 证据 2：字符串引用语义正确，例如 `0x10245F6A` 引用 `"DEBUG MODE"`（0x10710AD8）。
  - 另有候选 0x0F87A000 / 0x0F86D000，命中数虽高，但属于假命中：这些立即数实际指向 0x102xxxxx 的函数，只是碰巧落在文件 0x97xxxx 一带的字符串密集区。
- 大致布局（按文件偏移）：
  - `0x000000`：文件头
  - `0x100000–0x1FFFFF`：表格和数据，混有疑似压缩数据
  - `0x200000–0x6FFFFF`：主代码
  - `0x700000+`：字符串和资源
- 外设和 IO 地址：代码中大量出现 `0xFFFxxxxx` 和 `0xC000xxxx`（例如 `_DAT_c000468c` 是 0/1/2 的模式值，决定标签显示 `DEBUG MODE` 还是 `PC VENDOR`，并不是调试模式开关，见 `debug-mode-consumers.zh-CN.md` 第 5 节），尚未建立内存块。

## Ghidra 分析结果（`notes/ghidra_report.txt`）
- 种子函数 9514 个（`tools/gen_seeds.py` → `notes/seed_functions.txt`），自动分析后共 33,927 个函数、1,537,956 条指令。
- 解码失败 2,381 处，其中 2,363 处在 0x101xxxxx 数据区，属于把数据误当成代码。主代码区 0x10200000–0x106FFFFF 只有 2 处。
  **结论：现有 FR81 SLEIGH 已能完整覆盖 FR80 代码，暂时不需要补指令。**
- 反编译正常，例如：
  - `FUN_10245f40`：`ui_show_debug_mode_label`，`_DAT_c000468c` 为 0 时显示 `"DEBUG MODE"`，否则显示 `"PC VENDOR"`
  - `FUN_1060f57a`：用 `C:\%08d.%03d` 拼出调试脚本文件名

## 隐藏功能解锁（阶段二）文档

- `notes/memory-map.zh-CN.md`：容器布局、地址空间、系统标志
- `notes/sd-file-entrypoints.zh-CN.md`：全部 SD 卡入口文件
- `notes/debug-script.zh-CN.md`：工厂脚本的文件名、进入条件、命令表、执行语义
- `notes/emulate_parse_all.txt`：P-code 模拟验证结果
- `docs/debug-mode-guide.zh-CN.md`：用户指南和实机测试记录表
- `notes/debug-mode-consumers.zh-CN.md`：DEBUG_MODE 的全部读取点、TEST MODE 菜单页、菜单内退出方式
- `notes/firmware-checksum.zh-CN.md`：升级器的机型标记检查、字和为 0 规则、`pentax_fw.py checksum/fix`
- `notes/k5-vs-k5iis.zh-CN.md`：与 K-5 1.16 的对比和函数名移植（`tools/port_names.py`）
- `notes/fremulator-eval.zh-CN.md`、`notes/fremulator_parse_all.txt`：Nikon FrEmulator 运行 `parse_command` 的评估（`tools/fremu/`）
- 工具：
  - 卡文件与模拟：`tools/make_debug_card.py`、`tools/emulate_parse.py`
  - 固件处理：`tools/firmware_setup.py`、`tools/pentax_fw.py`
  - 分析辅助：`tools/port_names.py`、`tools/containing.py`、`tools/dump_decomp.py`
  - FrEmulator 构建：`tools/fremu/build.sh`

原始反编译输出（`notes/dec_*.c`）属于受版权保护固件的派生内容，不提交到仓库，可以用 `tools/dump_decomp.py` 在本地重新生成。

## 后续线索
- `C:\%08d.bin`（0x1078F4CC）、`C:\%08d.jpg`（0x1078F4D8）。
- AUTORUN 解释器中与相机操作有关的命令表（见 `fremulator-eval.zh-CN.md` 第 5 节）。

## 环境与使用
- Ghidra 12.1.4：`~/tools/ghidra_12.1.4_PUBLIC`，已安装扩展 `ghidra-fr60`（FR60 和 FR81）和 `GhidraMCP` 7.0.0（从源码按 12.1.4 编译）。
- GhidraMCP 源码（`tools/ghidra-mcp`，tag v7.0.0-rc.3）在本地改过 `build.gradle`：把 Java 21 toolchain 换成 `options.release = 21`，这样可以用本机的 JDK 25 编译。重新编译时要保留这处修改。
- Ghidra 项目：`ghidra/K5IIs.gpr`，程序名 `fwdc218b_dec.bin`。项目里嵌有固件字节，已加入 git 忽略列表。
- AI 对接（`.cursor/mcp.json` → `bridge-mcp-ghidra` → `127.0.0.1:8089`），两种方式二选一：
  - 无 GUI：`tools/ghidra-mcp-headless.sh`
  - GUI：`~/tools/ghidra_12.1.4_PUBLIC/ghidraRun`，打开项目，在 `File > Configure > Utility` 勾选 GhidraMCPPlugin
  - 两者不能同时打开同一项目（项目锁）。
- 重新导入和分析（约 30 分钟）：

```sh
GHIDRA_HEADLESS_MAXMEM=8G $GHIDRA_HOME/support/analyzeHeadless ghidra K5IIs \
  -import fw/fwdc218b_dec.bin -overwrite -loader BinaryLoader -loader-baseAddr 0x10000000 \
  -processor fr81:BE:16:default -cspec fcc911 -scriptPath tools/ghidra_scripts \
  -preScript SeedFunctions.java notes/seed_functions.txt \
  -postScript ReportStats.java notes/ghidra_report.txt -analysisTimeoutPerFile 7200
```
