[English](debug-script.md) | 简体中文

# 工厂调试脚本（K-5 IIs，固件 1.07）

## 1. 需要的文件（放在 SD 卡根目录）

| 文件 | 来源 | 内容要求 |
| --- | --- | --- |
| `00077681.541` | `sprintf("C:\\%08d.%03d", hdr[0x14]=77681, hdr[0x10]=541)` | 命令脚本（文本） |
| `DEVELOP.MOD` | 固件里用栈上字节逐个异或 0x29 还原出的字符串，避免明文 grep 被搜到 | K-5 IIs **只检查是否存在**；工具写入 GR 系列要求的 10 字节 `07 01 2C 1F 10 03 1E 16 05 2D` |

检查函数是 `ScriptMode_files_present` @ `0x1060F57A`：两个文件都要用 `fs_stat` 检查成功。

关于 `DEVELOP.MOD` 内容的复核（2026-10-21）：

- `ScriptMode_files_present` 用 15 条 `LDI:8` 把 `C:\DEVELOP.MOD` 的编码字节压栈，按 `c ^ 0xFF ^ 0xD6`（等价于异或 0x29）还原后只调用 `fs_stat`，没有打开或读取文件。
- 全映像扫描同一组 `LDI:8` 序列，只有 `0x1060F5FA` 一处（另一处 `0x10A8F1B4` 位于副处理器段，属于巧合）。
- `0x1079FF40` 有同一编码串的常量副本，紧跟在格式串 `C:\%08d.%03d` 后面，没有任何引用，是编译器留下的初始化数据。
- 明文和异或 0x29 形式的 `DEVELOP.MOD` 在别处都没有出现。
- 结论：K-5 IIs 1.07 不检查内容和长度。GR IV 和 GR IIIx 1.60 实测要求正好 10 字节的固定内容，这组字节用单字节异或、加法、链式异或都解不出可读文本，含义未知。为了兼容其他机身或固件版本，`make_debug_card.py` 统一写入这 10 字节。

## 2. 开机进入条件

开机分类函数 `Boot_classify` @ `0x105E815A` 判断这不是一次"正常开机"后，会走特殊开机分支 `Boot_special_poweron` @ `0x105E81D8`：

```
if (SW_DEBUG_MENU && 按住 OK(6) + DISP(10))        -> 开发菜单（Development Menu1..5）
else if (SCRIPT_EN_MODE || DEBUG_MODE || DOOR(0x1E) 处于触发状态):
    if (SCRIPT_EN_MODE && 卡上有 AUTORUN.541)       -> AUTORUN 自动测试
    else if (卡上同时有 00077681.541 和 DEVELOP.MOD) -> 工厂脚本模式（本文）
```

按键码来自 SWITCH TEST 画面的显示函数 `0x10614978`，它把按键码和名称一一对应：

| 按键码 | 名称 | 推测的物理部件 |
| --- | --- | --- |
| 0 | SWS | 半按快门 |
| 1 | SWR | 全按快门 |
| 3 | CARD | 卡是否插入 |
| 5 | AF | AF 按键 |
| 6 | 4WOK | 四向键中间的 OK |
| 7 | MENU | MENU 键 |
| 9 | INFO | INFO 键 |
| 10 | DISP | DISP（物理键待实机确认） |
| 0x11–0x14 | 4WU/4WD/4WR/4WL | 四向键 |
| 0x15 | AEL | AE-L |
| 0x16 | GREEN | 绿键 |
| 0x17 | XVAVSET | 未识别 |
| 0x18 | PRV | 预览 |
| 0x1D | FLPOP | 闪光灯弹起 |
| **0x1E** | **DOOR** | **卡仓门开关** |
| 0x20 | GP | 未识别 |
| 0x21 | ISO | ISO 键 |
| 0x22 | LIVE | 实时取景 |
| 0x23 | 36 | 未识别 |
| 0x25 | RAW | RAW 键 |
| 0x26 | ERASE | 删除键 |

**结论**：全新的相机（所有标志都关闭）要进入脚本模式，**需要在卡仓门打开时开机**（DOOR 开关处于触发状态）。

做法是插好卡、不关卡仓门，然后打开电源。如果门开着开机不生效，就在开机瞬间用手指按住门舌下的开关。

一旦 `DEBUG_MODE` 或 `SCRIPT_EN_MODE` 被打开，之后每次开机都会走这条分支：只要卡上有脚本文件，就会再次执行。所以完成设置后**必须删除或改名这个脚本文件**。

## 3. 脚本格式

读取函数是 `ScriptMode_load_script` @ `0x1060F700`，逐行读取用的是 `script_readline` @ `0x10616BDA`。

- 文件整体读进内存后逐行处理，每行最多 0x400 字节。
- 一行里可以有多个 `[...]` 命令，括号内的文本（最长 0x7F 字节）原样交给 `ScriptMode_parse_command`。
- 遇到 `!` 或 `;` 时，**该行剩余部分被忽略**，可用来写注释。
- 命令文本与表中字符串用 `strcmp` 精确比较：区分大小写，空格数量必须完全一致，例如 `[DEBUG_MODE EN]`。
- 无法识别的命令会被静默忽略。

## 4. 命令表（`ScriptMode_parse_command` @ `0x1060F950`）

解析结果写入数组 `cmd[index]`：EN 写 1，DIS 写 2，单独的动作命令写 1。`cmd[0x25]` 保存区域码，初始值是 0xFF。

| 索引 | 命令 | 执行函数或作用 | 风险 |
| --- | --- | --- | --- |
| 0x00 | `DEBUG_MODE EN` / `DEBUG_MODE DIS` | `SysFlags_set_debug_mode`，偏移 +0x04；从关闭切换为 EN 时还会额外调用 `0x106162C6` | 低，可逆 |
| 0x01 | `CFDOOR_OPEN EN/DIS` | 偏移 +0x08，允许卡门打开时继续操作 | 低 |
| 0x02 | `WRITE_CF_VNDR EN/DIS` | 偏移 +0x0C | 未知 |
| 0x03 | `SCRIPT_EN_MODE EN/DIS` | 偏移 +0x10，开启 AUTORUN | 低 |
| 0x04 | `USR_DAT_CLEAR` | **清除用户数据**（优先级最高，立即执行） | 中，相当于恢复出厂设置 |
| 0x05 | `SWITCH_TEST` | 按键测试画面 | 只读 |
| 0x06 | `DISPLAY_TEST` | 屏幕测试 | 只读 |
| 0x07 | `MEMORY_TEST` | 内存测试 | 只读 |
| 0x08 | `RELEASE_AGING` | 快门老化测试（**会大量消耗快门寿命**） | 高 |
| 0x09 | `LENS_COMUNICATION_CHECK` | 镜头通信检查 | 只读 |
| 0x0A | `CPU_ADJ_FLG_CLEAR` | 清除 CPU 校准标志 | **高** |
| 0x0B / 0x0C | `CPU_ADJ_CSV_WRITE` / `CPU_TST_CSV_WRITE` | 读取卡上的 `KB541ADJ/TST.CSV` | **高** |
| 0x0D / 0x0E | `CPU_ADJ_CSV_READ` / `CPU_TST_CSV_READ` | 把校准值导出到 CSV | 只读 |
| 0x0F | `CPU_ROM_STORE` | 把 CPU ROM 导出为 `KB541CPU.BIN` | 只读，**建议首先执行作为备份** |
| 0x10 | `DSP_ROM_STORE` | 把 DSP ROM 导出为 `KB541DSP.BIN` | 只读 |
| 0x11 | `AF_PINT_DISP` | 显示 AF 焦点偏移 | 只读 |
| 0x12 | `ICCD_PINT_OFF_CLEAR` | 清除焦点校准 | **高** |
| 0x13 | `COLOR_PINT_COR_CLEAR` | 清除焦点色差校正 | **高** |
| 0x14 | `SI_ALL_ON` | 点亮全部取景器叠加显示 | 只读 |
| 0x15 / 0x16 | `CPU_ADJ_DAT_READ` / `CPU_ADJ_DAT_WRITE` | `KB541CPU.ADJ` 的导出（READ）和写入（WRITE） | READ 只读，WRITE 高风险 |
| 0x17 / 0x18 | `DSP_ADJ_DAT_READ` / `DSP_ADJ_DAT_WRITE` | `KB541.ADJ` | 同上 |
| 0x19 | `ALL_ADJ_DAT_READ` | 导出全部校准数据 | 只读，建议备份 |
| 0x1A / 0x1B | `DSP_USR_DAT_READ` / `DSP_USR_DAT_WRITE` | `KB541.USR` | READ 只读 |
| 0x1C | `SR_BULB` | 防抖 B 门测试 | 中 |
| 0x1D | `DIS_AF_F28` | 禁用 F2.8 AF 传感器 | 中，测试用 |
| 0x1E | `ONLY_AF_F28` | 只用 F2.8 AF 传感器 | 中 |
| 0x1F | `VLENS_CTRL` | 虚拟镜头控制 | 中 |
| 0x20 | `LENS_CPU_FIRMUP` | 镜头固件升级（`LENSCPU.bin`） | **高** |
| 0x21 / 0x22 | `LENSROM_LOAD` / `LENSROM_STORE` | 镜头 EEPROM 的写入和导出 | STORE 只读，LOAD 高风险 |
| 0x23 | `OPEN_DEBUG_MENU` | 直接打开开发菜单 1–5 | 低 |
| 0x24 | `SW_DEBUG_MENU EN/DIS` | 偏移 +0x18，允许用 OK+DISP 开机进入开发菜单 | 低 |
| 0x25 | `REGION_CODE 0`…`REGION_CODE 5` | 改写区域码（影响语言和制式） | 中 |
| 0x26 | `DISP_REGION_CODE` | 显示区域码 | 只读 |
| 0x27 | `CAM_LOG_DAT_READ` | 把相机日志导出为 `KB541CAM.LOG` | 只读 |
| 0x28 | `CAM_LOG_DISP` | 显示快门计数、无线频道、焦点偏移 | 只读 |
| 0x29 | `USR_CLEAR_CAM_DISP` | 用户数据清除并显示 | 中 |
| 0x2A | `CRE_RECOVERY_FW` | 生成恢复固件 | 中，会写入闪存 |
| 0x2B | `G200_TEST` | 测试，依赖 `G200STEP.DAT` | 未知 |
| 0x2C | `LIVE_VIEW_TEST_MODE EN/DIS` | 实时取景测试模式 | 低 |

## 5. 执行语义（`ScriptMode_execute` @ `0x1061000E`）

1. **独占动作**按优先级只执行一个，之后等待按键：
   - `USR_DAT_CLEAR` → `USR_CLEAR_CAM_DISP` → 各种 CSV、ROM、ADJ 命令 → `LENS_CPU_FIRMUP` → `CRE_RECOVERY_FW` → `LENSROM_*` → `G200_TEST`
   - 屏幕上依次显示 `WAIT...`、`COMPLETE...` 或 `ERROR...`。
2. 没有独占动作时，处理**标志类命令**：
   - 可以组合，包括 `DEBUG_MODE`、`CFDOOR_OPEN`、`WRITE_CF_VNDR`、`SCRIPT_EN_MODE`、`SW_DEBUG_MENU`、`REGION_CODE`、`LIVE_VIEW_TEST_MODE`、两个 `*_CLEAR`。
   - 只要有任意一个改动，就调用一次 `SysFlags_commit` 写回持久存储。
3. 然后执行**一个界面类**命令：
   - `OPEN_DEBUG_MENU` → `SWITCH_TEST` → `DISPLAY_TEST` → `MEMORY_TEST` → `RELEASE_AGING` → `LENS_COM…` → `AF_PINT_DISP` → `CAM_LOG_DISP` → `SI_ALL_ON` → `SR_BULB` / `AF F2.8` → `VLENS` → `DISP_REGION_CODE`。

## 5.1 换行与模拟验证

- `script_readline` @ `0x10616BDA` **只把 `\r` 当作行结束**，并且会跳过它后面的一个字节，所以**必须使用 CRLF**：
  - 如果只用 LF，整个文件会被当成一行（缓冲区 0x400 字节，不检查边界），第一个 `;` 之后的命令也会全部丢失。
  - 如果只用 CR，下一行的第一个字符会被吃掉。
- `tools/emulate_parse.py --all` 用 Ghidra 的 P-code 模拟器**直接运行固件里的** `ScriptMode_parse_command`：
  - 全部 56 个命令字符串都落到预期的槽位，结果保存在 `notes/emulate_parse_all.txt`。
  - 4 个反例全部被拒绝：小写、双空格、末尾空格、空字符串。
- `tools/make_debug_card.py` 生成的文件会先用 Python 移植的固件分词逻辑自检，`check --emulate` 再把分出的命令交给模拟器验证。
- 预生成的卡文件放在 `sdcard/devmenu/`、`sdcard/enable/`、`sdcard/disable/`、`sdcard/camlog/`。

## 5.2 同系机型对照

理光 GR IV 和 GR IIIx 的公开研究（[radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)）表明，K-5 IIs 的工厂脚本机制被沿用到了 2020 年代的机型上。下表的 GR 一列来自该仓库的文档和 `tools/create_factory_entry.py`。

| 项目 | K-5 IIs 1.07（本项目） | GR IV 1.11 / GR IIIx 1.60 |
| --- | --- | --- |
| 脚本文件名 | `00077681.541`，`%08d.%03d`（脚本编号、机型码） | `00078560.636` / `00078490.609`，同一格式 |
| `DEVELOP.MOD` | 只检查存在 | 必须为 10 字节 `07 01 2C 1F 10 03 1E 16 05 2D` |
| 打开菜单的命令 | `[OPEN_DEBUG_MENU]` | `[OPEN_FACTORY_DEBUG_MENU]`，单独一条即可进入工厂菜单（实机验证） |
| 进入条件 | 卡门打开时开机，或标志已开 | 按住 MENU 开机 |
| Debug 标志 | 设置对象 `+0x04`，开 `0x5AA5A55A` / 关 `0xFFFFFFFF` | CameraModeData `+4`，取值完全相同 |
| 自动运行脚本 | `AUTORUN.541`，类 BASIC，结果写 `CHKDAT.541` | `script/startup.ttl`，Tera Term 语言，带 `filecopy`，`C:` 为 SD 卡、`A:` 为机内资源 |
| Debug 的界面消费者 | 版本页四段版本号、设置菜单多出 TEST MODE 页（含 `DEBUG MODE DISABLE`）；未找到隐藏按键序列。见 `debug-mode-consumers.zh-CN.md` | `Camera Mode` 文字、Version 页四段版本号、限时四键序列进入 `DevelopmentMenuController` |

同一家公司更早的 K-30 研究（[i-am-shodan/PHDK](https://github.com/i-am-shodan/PHDK)、[i-am-shodan/PentaxFirmwareTool](https://github.com/i-am-shodan/PentaxFirmwareTool)）在固件校验上也与 K-5 IIs 一致，见 `firmware-checksum.zh-CN.md`。

## 6. 推荐的第一次脚本

先用 `devmenu`（`[OPEN_DEBUG_MENU]`）确认能进入脚本模式，它不改写标志。之后再用：

```
; K-5 IIs: enable debug mode + dev menu (safe flags only)
[DEBUG_MODE EN]
[SW_DEBUG_MENU EN]
```

关闭用的脚本：

```
[DEBUG_MODE DIS]
[SW_DEBUG_MENU DIS]
[SCRIPT_EN_MODE DIS]
```

## 7. 开启后的效果（已确认的部分）

- `DEBUG_MODE` 打开后：
  - 拍摄管线初始化时会读取 `SYSPARAM.TXT`，键名见 `sd-file-entrypoints.zh-CN.md`。
  - 设置菜单在 Setup 页（0x0C）之后多出 TEST MODE 页（0x0D）：CAPTURE/SYSTEM TEST、AF TEST、STRINGS DISP TEST、Icon Test、DEBUG MODE DISABLE。
  - 工厂画面的版本页从两段版本号变成 DSP/CPU 四段版本号。
  - 详见 `debug-mode-consumers.zh-CN.md`。之前把 `0xC000468C` 当成 DEBUG 标签开关是错的，它只选择 `DEBUG MODE`/`PC VENDOR` 标签文字。
- `SW_DEBUG_MENU` 打开后：开机时按住 OK+DISP 进入 **Development Menu1–5**：
  - Menu1：标志开关、`USR DAT CLEAR`、`REGION CODE`
  - Menu2：`SWITCH TEST`、`RELEASE AGING`、`LENS COM CHECK`、`AF PINT DISP`、`CAMERA LOG DISP`
  - Menu3：校准数据在相机和 SD 卡之间互传
  - Menu4：镜头 ROM 的读写、编辑，以及镜头固件升级
  - Menu5：板卡版本、DSP 芯片版本、除尘测试、介质测试、显示测试、内存测试、实时取景测试
- `SCRIPT_EN_MODE` 打开后：开机时如果有 `AUTORUN.541`，就执行 BASIC 风格的测试脚本，结果写入 `CHKDAT.541`。
