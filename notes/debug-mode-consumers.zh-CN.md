[English](debug-mode-consumers.md) | 简体中文

# DEBUG_MODE 的读取点（K-5 IIs 1.07）

目的：找出 `DEBUG_MODE`（SysFlags +0x04，持久值 `0x5AA5A55A`/`0xFFFFFFFF`）打开以后，固件里到底有哪些行为会变化，并找出在机身上退出调试模式的方法。对照对象是 GR IV 的 Debug 行为（Version 页四段版本号、隐藏菜单等）。

方法：通过 GhidraMCP 枚举所有 `LDI:32 #getter` 装载点，再逐个反编译调用者。部分调用者原本不是 Ghidra 识别出的函数，用 `tools/containing.py --create` 补建（虚表项指向的位置比 Ghidra 自动建立的函数入口早 2 字节，已按虚表地址重建）。

## 1. 三个读取函数

| 函数 | 地址 | 说明 |
| --- | --- | --- |
| `SysFlags_is_debug_mode` | `0x10615F70` | 读 SysFlags 对象 +0x04。装载点：`104BB3A0`、`105DD3E8`、`1060D212`、`10610F6A`、`10611682`、`10611720`、`10618D1A/2A/36` |
| `flags_is_debug_mode` | `0x10483F1C` | 持久存储层的读取。调用者是 `FUN_105EC2A2`（开机分类里用的包装，见 `debug-script.zh-CN.md` 第 2 节）和 `FUN_104840AE`（一次性读出所有标志到数组） |
| `flags_is_debug_mode_2` | `0x10483EF0` | 通过 `FUN_104F7936` 使用，读持久存储第 3 区 |

同一组还有其他标志的读写函数：`FUN_10483F48/F74/FCC`、`FUN_10484012` 是读取，`FUN_10483F5C/FB4/ECA`、`FUN_10484018`、`FUN_1048400C` 是写入，`FUN_10484046` 用数组一次性写回全部标志。

## 2. 行为变化一览

| 位置 | 调试模式下的变化 | 对应 GR IV 行为 |
| --- | --- | --- |
| `FUN_1060D1FA`（工厂画面链的版本页） | 版本号从 `VER %d.%02d` 两段变成 `DSP VER %d.%02d.%02d.%02d` 和 `CPU VER %d.%02d.%02d.%02d` 四段，并多显示一行主 CPU 版本 | Version 页四段版本号，**完全对应** |
| `FUN_10618CBC` | 同样调用 `FUN_106182D2(obj, debug?2:0, debug)`，显示 5 秒 | 同上 |
| 设置菜单（`0x1000AD2C` 初始化表、导航函数 `FUN_10230824`） | 多出一页 TEST MODE（页号 0x0D），见第 3 节 | 隐藏的工厂菜单 |
| `FUN_104BA894` 第 731 行 | `FUN_1049E2F8(…,2)==2` 且调试模式时，把输出结构 +0x5A 强制为 1；否则取 0xDE 号设置项的值。含义未确认 | — |
| `FUN_105EC9D8` | 非调试模式时调用 `FUN_104A8B6C()` 和 `FUN_104A946C(1,0)`；调试模式跳过这两步。含义未确认 | — |
| `FUN_105DD34C` | 构造状态位图，调试模式是第 1 个字的 bit 0（推测供 USB/PC 通信查询） | — |
| `FUN_1061167A` | 把所有标志快照到结构 +0x5E..+0x68，供 Development Menu1 显示和修改 | — |
| `FUN_106116DE`（Development Menu1 画面） | 显示 `DEBUG MODE <EN>/<DIS>`、`CARDDOOR OPEN`、`WRITE CARD VNDR`、`SCRIPT EN MODE`、`AUTO TEST MODE`、`USR DAT CLEAR`、`REGION CODE`；确认后逐个写回标志 | GR IV 的工厂调试菜单 |
| `ScriptMode_execute` `0x10610F6A`、`0x10610F96` | 脚本命令执行时的调试分支，见 `debug-script.zh-CN.md` | — |

`FUN_106182D2(obj, mode, debug)` 的 mode：0 只显示 DSP 版本，1 只显示 CPU 版本，2 两者都显示，3 显示 DSP 芯片版本（Development Menu5 用）。第三个参数为真时使用四段格式。

工厂画面运行器 `FUN_1060C1BA(obj, n)` 按 n 选择起始画面：0 是版本页（单例 `FUN_1060D15A`，对象 `0xC006BCF0`），1 是 ScriptMode，2 是 SwitchTest，3 是 Development Menu1（`FUN_1061149E`）。`FUN_1060C402` 把各画面串成链表：版本页的下一页是 Menu1，Menu1 到 Menu5（`1061149E` → `10611C62` → `10612234` → `10612898` → `10612D0C`）首尾相连。

## 3. 设置菜单里的 TEST MODE 页

设置菜单的页序列来自 ROM 初始化表 `0x1000AD2C`：

- 正常：`1 2 3 4 5 8 9 A B C E F 10 11`，共 14 页。
- 调试模式：在 `C` 之后插入 `D`，共 15 页。短序列 `6..C` 同样变成 `6..D`。
- 导航函数 `FUN_10230824`；另一个附加条件 `FUN_104FB7EA` 在本固件里恒返回 0。

页 0x0D：

- 布局表 `0x10707F58`，绘制函数 `FUN_10227D32`（虚表 `0x1070DDF4`，槽位在 `0x1070DF20`），按键处理 `FUN_102282BC`。OK 是按键码 7，按键 0xE 经 `FUN_102301CE(…,0x18)` 返回。
- 字符串在本地化表 `0x1002B75C` 起，每字节加 9 编码。

| 行 | 进入画面 |
| --- | --- |
| CAPTURE/SYSTEM TEST | 0x67 |
| AF TEST | 0x65 |
| STRINGS DISP TEST | 0x66 |
| Icon Test | 0x68 |
| **DEBUG MODE DISABLE** | 0x69 |

## 4. 退出调试模式的路径

### 4.1 菜单：DISABLE DEBUG MODE ?

TEST MODE 页的 `DEBUG MODE DISABLE` 打开确认对话框：

- 构造函数 `FUN_104309D2`，虚表 `0x1076194C`。绘制槽 37 = `0x10430AD4`，布局 `0x10761370`（`DISABLE DEBUG MODE ?` / `DISABLE` / `CANCEL`）；按键槽 45 = `0x10430DA4`。
- 实例由 `FUN_102A6CE6` 存到画面管理器 +0x244。
- 选中 `DISABLE`（ID `0x1FF0002`）调用 `FUN_10430E9E` → `FUN_104F786A(obj, 0)`：若当前是调试模式，依次清除 `DEBUG_MODE`、`CFDOOR_OPEN`、`WRITE_CF_VNDR`、`SCRIPT_EN_MODE`、`0x10483FB4` 对应的标志、`SW_DEBUG_MENU`、`0x10483ECA` 对应的标志，最后用 `FUN_1048BD74` 提交到持久存储。

这是**不需要读卡、不需要脚本**的退出方式，可以作为 `disable` 卡之外的备用方案。

### 4.2 SYSPARAM：DAC_DEBUG_MODE_BREAK

DA 校准循环 `FUN_102AFB2E` 开始时检查 `FUN_104A5ACE(0x22)` = `DO_DA_CALIB`（对象 +0xF4），某条退出路径上检查 `FUN_104A5ACE(0x2A)` = `DAC_DEBUG_MODE_BREAK`（+0x114），为真就调用同一个 `FUN_104F786A`。也就是 `SYSPARAM.TXT` 写 `[DAC_DEBUG_MODE_BREAK]1@` 并进入 DA 校准流程时会清除调试模式。怎样进入 DA 校准流程尚未确认，不建议使用。

### 4.3 BOARD TEST 36：FLASH INIT（反方向，注意）

BOARD TEST 列表（字符串 `0x10798790` 起，`COMMAND: %02X HEX`，测试 10–38，入口引用在 `0x105D23FA`）中的 `36 : FLASH INIT`（`FUN_105D3AD8`，由 `FUN_105D2C46` 在 `0x105D2D7E` 调用）：

1. `FUN_1061619E` 清除全部标志并提交；
2. 然后 `SysFlags_set_debug_mode(1)`、`set_cfdoor_open(1)`；
3. 最后 `FUN_10616168`。

所以 FLASH INIT 之后机身处在**调试模式打开**的出厂状态，不要误当成退出手段。

## 5. 更正：`0xC000468C` 不是 DEBUG_MODE

之前的笔记把 `_DAT_C000468C` 当成 DEBUG 标签开关，这是错的：

- 它是 0/1/2 的模式值，只由 `FUN_1023019C` 写入，调用者 `FUN_102B29C2` 复制 obj+0x70。
- `ui_show_debug_mode_label`（`0x10245F40`）在值为 0 时显示 `DEBUG MODE`，否则显示 `PC VENDOR`。即它只选择标签文字，不决定是否处于调试模式。
- `FUN_102301CE` 在值为 1 且参数为 1 时跳过动作。

真正的调试模式状态只在 SysFlags +0x04（及其持久存储）。

## 6. 隐藏按键序列

GR IV 在 Debug 下可以用限时四键序列进入 `DevelopmentMenuController`。K-5 IIs 1.07 没有找到同类序列：所有调试模式读取点都已列在第 2 节，没有一处出现在按键事件计数或计时逻辑里。进入 Development Menu 的按键组合仍只有开机时按住 OK+DISP（需 `SW_DEBUG_MENU`），见 `debug-script.zh-CN.md` 第 2 节。
