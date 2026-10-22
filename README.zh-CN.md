[English](README.md) | 简体中文

# PENTAX K-5 IIs 固件 1.07：工厂调试模式研究

> [!IMPORTANT]
> **AI 生成内容声明。** 本仓库几乎所有的分析、工具和文档，都是在仓库所有者的指导下，由 AI 编程代理完成的（Cursor 中的大语言模型通过 GhidraMCP 操作 Ghidra）。
> - 结论来自静态分析和模拟，**尚未在实机上验证**，可能有错。
> - 运行代码前请先阅读代码；在实机测试确认之前，请把所有结论当作假设。

> [!IMPORTANT]
> **无许可证（No license）。** 本仓库有意不附带任何许可证文件，作者保留全部权利。
> - 根据 GitHub 服务条款，你可以在 GitHub 上查看和 fork 本仓库。
> - 除此之外，不授予任何使用、复制、修改或再分发的许可。
> - 文中引用的第三方项目适用各自的许可证。

> [!WARNING]
> **不含任何理光 / PENTAX 固件。** 本仓库不包含以下任何内容：
> - 固件映像（`fwdc218b.bin` 等）及其解密或解压后的版本；
> - 由固件生成的 Ghidra 项目和原始反编译输出；
> - ROM 或校准数据导出。
>
> 这些文件归理光所有，受版权保护；理光的下载页面写明"転載禁止"（禁止转载）。
> - 仓库里**有**的是：原创的笔记、地址表、为实现互操作而引用的少量标识符字符串，以及处理**你自己从理光官网下载的**固件文件的工具。
> - 获取方法见[获取固件](#获取固件)。
> - 请不要提交或分享固件、解密映像或相机导出文件（`KB541*.BIN`、`*.ADJ` 等）。

> [!CAUTION]
> **风险自负。** 工厂模式可能清除校准数据、消耗快门寿命，甚至让相机无法使用。
> - 本项目是独立研究，与理光映像株式会社（RICOH IMAGING COMPANY, LTD.）无关，也未获其认可。
> - PENTAX 和 RICOH 是其各自所有者的商标。
> - 本项目的任何步骤都不修改固件，但你对自己相机的操作由你自己负责。

## 这是什么

K-5 IIs 的固件里（对比可知 K-5 也一样）有一个工厂脚本模式，后来的理光机型（例如 GR IV）也沿用了这套机制。它由 SD 卡上的两个文件驱动：

- `00077681.541`：文本脚本，命令形如 `[DEBUG_MODE EN]`、`[OPEN_DEBUG_MENU]`
- `DEVELOP.MOD`：标记文件

卡仓门打开时开机，相机就会执行这个脚本。由此可以进入：

- 隐藏的 **Development Menu 1–5**：按键测试、快门计数、版本信息、校准数据和 ROM 备份；
- 普通菜单里的 **TEST MODE** 页；
- **`SYSPARAM.TXT`** 图像管线调试开关；
- 类 BASIC 的 **AUTORUN** 测试语言。

以上全部通过静态逆向发现；脚本解析器还在两个模拟器中运行了固件自身的代码加以核对。下一步是实机测试。

## 快速上手（测试者）

需要：固件 1.07 的 K-5 IIs、充满的电池、一张在相机里格式化过的 SD 卡、Python 3。

1. 完整阅读 [docs/debug-mode-guide.zh-CN.md](docs/debug-mode-guide.zh-CN.md)。
2. 把 `sdcard/devmenu/` 里的两个文件复制到卡的根目录。它们是工具生成的文件，不是固件。
   - 其他预置在 `sdcard/` 下，也可以用 `python3 tools/make_debug_card.py write <卡根目录> --preset <名称>` 生成。
3. 卡仓门**打开**的状态下开机，应当出现 Development Menu。不改动任何项目，按 `[MENU]` 退出。
4. 填写指南第 6 节的测试记录表并反馈。导出文件只报告大小，不要发送文件本身。

这一步不需要下载固件，卡文件是自包含的。

## 获取固件

只有复现分析、运行模拟器或重新生成卡文件时才需要固件。理光只允许机主在同意其软件使用条款后下载。

1. 打开理光官方页面，阅读使用条款：
   - K-5 IIs 1.07：<https://www.ricoh-imaging.co.jp/english/support/digital/k-5_2_s.html>（日文：<https://www.ricoh-imaging.co.jp/japan/support/download/digital/k5_2_s.html>）
   - K-5 1.16（仅用于对比）：<https://www.ricoh-imaging.co.jp/english/support/digital/k-5_s.html>
   - `python3 tools/firmware_setup.py open` 会在浏览器中打开 K-5 IIs 的页面。
2. 自行下载 `k5_2s107.zip`（Windows/Mac 通用 zip；K-5 是 `k5_v116m.zip`）。
3. 用辅助工具在本地校验、解压、解密：

```bash
python3 tools/firmware_setup.py info                 # 官方地址和预期的 SHA-256
python3 tools/firmware_setup.py import ~/Downloads/k5_2s107.zip
python3 tools/firmware_setup.py status
```

`import` 会先校验压缩包和 `fwdc218b.bin` 的 SHA-256，然后把以下文件写入已被 git 忽略的 `fw/` 目录：
- `fwdc218b.bin`
- `fwdc218b_dec.bin`（与 pfwtool 兼容）
- `fwdc218b_full_dec.bin`
- `subcpu_arm.bin`

每个输出都会和参考哈希比对，保证你的分析与 `notes/` 里的地址逐字节对应。这个工具既不会自动下载，也不会上传任何东西。

把相机本身升级到 1.07，请按理光页面上的官方流程：把 `fwdc218b.bin` 复制到格式化过的卡上，按住 MENU 开机。绝不要刷入本仓库工具生成的任何文件。

## 目录结构

| 路径 | 内容 |
| --- | --- |
| [docs/](docs/debug-mode-guide.zh-CN.md) | 用户指南和实机测试记录表 |
| [notes/](notes/README.zh-CN.md) | 分析笔记：内存映射、SD 卡入口、脚本命令表、调试模式读取点、完整性校验、K-5 对比、模拟器评估 |
| `sdcard/` | 现成的 SD 卡脚本预置（`devmenu`、`enable`、`disable`、`camlog`、`sysparam-laptime`） |
| `tools/firmware_setup.py` | 校验、解压、解密你自己下载的官方固件 |
| `tools/make_debug_card.py` | 生成和检查 SD 卡脚本（默认拒绝危险命令） |
| `tools/pentax_fw.py` | 固件容器编解码、自检、完整性检查和修正（离线使用） |
| `tools/emulate_parse.py`、`tools/fremu/` | 在 Ghidra P-code 模拟器或 Nikon FrEmulator 中运行固件的脚本解析器 |
| `tools/gh.py`、`mkfunc.py`、`callers.py`、`containing.py`、`port_names.py`、`dump_decomp.py`、`ghidra_scripts/` | Ghidra / GhidraMCP 辅助工具 |
| `tools/names.tsv`、`notes/*.tsv` | 地址到函数名的对照表 |

所有文档都有英文版（`*.md`，默认）和简体中文版（`*.zh-CN.md`）。

## 分析环境（可选）

以下工具都需要另行克隆或安装，不属于本仓库：

- [Ghidra](https://github.com/NationalSecurityAgency/ghidra) 12.1.x
- [desrdev/ghidra-fr60](https://github.com/desrdev/ghidra-fr60)：FR60/FR81 处理器模块
- [bethington/ghidra-mcp](https://github.com/bethington/ghidra-mcp)：GhidraMCP
- [twang2218/pentax-firmware-tool](https://github.com/twang2218/pentax-firmware-tool)：pfwtool，参考解密器
- [simeonpilgrim/nikon-firmware-tools](https://github.com/simeonpilgrim/nikon-firmware-tools)：FrEmulator

安装细节见 [notes/README.zh-CN.md](notes/README.zh-CN.md)。

## 相关项目

- [radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)：GR IV / GR IIIx 上的同一套工厂脚本机制
- [i-am-shodan/PHDK](https://github.com/i-am-shodan/PHDK)、[i-am-shodan/PentaxFirmwareTool](https://github.com/i-am-shodan/PentaxFirmwareTool)：PENTAX K-30 固件研究
