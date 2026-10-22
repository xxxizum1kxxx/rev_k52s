[English](debug-mode-guide.md) | 简体中文

# Pentax K-5 IIs（固件 1.07）工厂调试模式使用指南

> 本指南完全基于静态逆向和 P-code 模拟得出，**尚未在实机上验证**。第 6 节是实机测试记录表，请按顺序执行并填写。
> 所有步骤**不修改固件**，只往 SD 卡放文件。改动的只是相机里持久保存的标志，可以用"关闭脚本"恢复。

## 0. 准备

- 机身固件必须是 **1.07**：按住 MENU 开机，液晶屏中央会显示版本号。
  - 其他版本的脚本编号可能不同，`make_debug_card.py` 会从对应固件头读取编号。
  - 如果不是 1.07，先按理光官方流程升级，见根目录 README 的"获取固件"一节。
- 电池充满。使用一张已经在本机格式化过的 SD 卡，**卡槽 1**。
- 在电脑上生成卡文件（也可以直接复制 `sdcard/` 下预生成的文件）：

```bash
python3 tools/make_debug_card.py presets
python3 tools/make_debug_card.py write /run/media/$USER/SDCARD --preset devmenu
python3 tools/make_debug_card.py check /run/media/$USER/SDCARD/00077681.541 --emulate
```

卡的根目录里应当出现：
- `00077681.541`：命令脚本，CRLF 换行
- `DEVELOP.MOD`：10 字节 `07 01 2C 1F 10 03 1E 16 05 2D`。K-5 IIs 只检查文件是否存在，这组内容是 GR IV / GR IIIx 实测要求的，写上它不影响 K-5 IIs

## 1. 进入脚本模式（第一次）

第一次先用 `devmenu` 卡，只含 `[OPEN_DEBUG_MENU]`。它不改写任何持久标志，能看到开发菜单就说明"文件名、`DEVELOP.MOD`、卡门开机条件"三者都对了，然后再用 `enable` 卡开启标志。

同一家公司的 GR IV 上，只放 `[OPEN_FACTORY_DEBUG_MENU]` 一条命令加 `DEVELOP.MOD` 就能进入工厂菜单，已经在实机上验证过（[radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)）。K-5 IIs 的 `OPEN_DEBUG_MENU` 与它名称和用途都对应。

1. 关机，插入 SD 卡，**保持卡仓门打开**。
2. 打开电源。
   - 固件在开机时检查卡门开关（按键码 0x1E，名称 DOOR）：门开着就走"特殊开机"分支，再查找脚本文件。
   - 如果没有反应，关机后再试一次：开机瞬间用手指压住卡门的检测开关。
3. 屏幕上会出现脚本执行界面。
   - 标志类命令（例如 `DEBUG_MODE EN`）会被写入并提交。
   - 如果脚本里有显示类或导出类命令，会显示 `WAIT...`、`COMPLETE...` 或 `ERROR...`，按任意键后继续。
   - `devmenu` 卡应当直接进入 Development Menu1。按 `[MENU]` 退出，不要在菜单里改动任何项目。
4. 关机，换成 `enable` 卡，同样门开着开机一次。
5. 关机，**在电脑上删除或改名 `00077681.541`**。
   - 原因：打开 `DEBUG_MODE` 之后，每次开机都会走特殊分支，不删除就会反复执行脚本。
6. 关上卡门，正常开机，确认机身已进入调试模式（第 3 节）。

## 2. 预置脚本

| 预置 | 内容 | 用途 | 风险 |
| --- | --- | --- | --- |
| `enable` | `[DEBUG_MODE EN]` `[SW_DEBUG_MENU EN]` | 开启调试模式和开发菜单的组合键 | 低，可逆 |
| `disable` | `[DEBUG_MODE DIS]` `[SW_DEBUG_MENU DIS]` `[SCRIPT_EN_MODE DIS]` | 全部关闭 | 无 |
| `devmenu` | `[OPEN_DEBUG_MENU]` | 直接打开开发菜单 | 低 |
| `camlog` | `[CAM_LOG_DISP]` | 显示快门总数、无线频道、焦点偏移 | 只读 |
| `backup-cpu-rom` | `[CPU_ROM_STORE]` | 导出 `KB541CPU.BIN` | 只读 |
| `backup-dsp-rom` | `[DSP_ROM_STORE]` | 导出 `KB541DSP.BIN` | 只读 |
| `backup-adj` | `[ALL_ADJ_DAT_READ]` | 导出全部校准数据 `KB541*.ADJ` | 只读 |
| `backup-camlog` | `[CAM_LOG_DAT_READ]` | 导出 `KB541CAM.LOG` | 只读 |

**每次开机只会执行一个"独占动作"**（导出、清除等），所以多项备份要分几次进行。

**强烈建议**开启调试模式后，先依次执行 4 个 `backup-*`，并把导出的文件保存到电脑。校准数据一旦被误清除，就只能靠这些备份恢复。

这些导出文件**不要公开或分享**：里面包含理光享有版权的固件，以及你这台相机独有的校准数据。

危险命令（`USR_DAT_CLEAR`、`*_WRITE`、`*_CLEAR`、`RELEASE_AGING`、`LENS_CPU_FIRMUP`、`REGION_CODE n` 等）默认被工具拒绝生成。确实要用时需要加 `--allow-dangerous`。完整风险分级见 `notes/debug-script.zh-CN.md`。

## 3. 开启后可以用的功能

### 3.1 开发菜单（需要 `SW_DEBUG_MENU EN`）

开机时按住 **OK 和 DISP**（按键码 6 和 10），进入 Development Menu。用四向键选择，`[OK]` 执行，`[MENU]` 取消或返回。

| 菜单 | 项目 | 建议 |
| --- | --- | --- |
| Menu1 | DEBUG MODE / CARDDOOR OPEN / WRITE CARD VNDR / SCRIPT EN MODE / AUTO TEST MODE 开关，USR DAT CLEAR，REGION CODE | 只动前两项；**不要**执行 USR DAT CLEAR 或改区域码 |
| Menu2 | SWITCH TEST、RELEASE AGING（MAN/AUTO）、LENS COM CHECK、AF PINT DISP、CAMERA LOG DISP | 除 RELEASE AGING 外都是只读；**RELEASE AGING 会连续释放快门** |
| Menu3 | CPU/DSP ADJ DAT 在相机和 SD 卡之间互传（CAMERA=>SD 或 SD=>CAMERA），CAMERA LOG CAMERA=>SD | 只用 `CAMERA=>SD` 方向 |
| Menu4 | LENS ROM DAT 互传，LENS ROM EDIT R/W，LENS CPU FWUP | 只用 `CAMERA=>SD`；**不要**编辑或升级镜头 |
| Menu5 | BOARD VER、DSP CHIP VER、DUST REDUCTION TEST、MEDIA TEST、DISPLAY TEST、MEMORY TEST、LIVEVIEW TEST | 基本只读；MEDIA TEST 可能会写卡 |

DISP 对应哪个物理键还没确认（K-5 IIs 的 INFO 键是另一个按键码 9）。如果 OK+DISP 不生效，改用 `devmenu` 预置脚本进入。

### 3.2 设置菜单里的 TEST MODE 页（需要 `DEBUG_MODE EN`）

调试模式下，普通 MENU 的设置部分在 Setup 第 0x0C 页之后会多出一页 TEST MODE（页号 0x0D），不需要按组合键：

| 项目 | 说明 | 建议 |
| --- | --- | --- |
| CAPTURE/SYSTEM TEST | 拍摄/系统测试 | 内容未逆向，先不进入 |
| AF TEST | AF 测试 | 同上 |
| STRINGS DISP TEST | 逐条显示界面字符串 | 只读，可以看 |
| Icon Test | 显示图标 | 只读，可以看 |
| **DEBUG MODE DISABLE** | 弹出 `DISABLE DEBUG MODE ?`，选 `DISABLE` 关闭调试模式 | 备用退出方式，见第 4 节 |

另外，工厂画面里的版本页会从 `VER x.yy` 变成 `DSP VER x.yy.zz.ww` 和 `CPU VER x.yy.zz.ww` 四段格式，这和 GR IV 调试模式下 Version 页的变化一致。固件里没有找到 GR IV 那种限时四键序列。详见 `notes/debug-mode-consumers.zh-CN.md`。

### 3.3 SWITCH TEST 中显示的按键名

`SWS`（半按）、`SWR`（全按）、`PRV`、`AF`、`LIVE`、`GREEN`、`FLPOP`、`DOOR`、`CARD`、`GP`、`36`、`RAW`、`MENU`、`ERASE`、`INFO`、`4WU/D/L/R/OK`、`DISP`、`XVAVSET`、`AEL`、`ISO`、`AEMD`、`AFMD`、`AFAREA`、`MODE`、`FDL/RDL`（前后拨轮计数）、`AC:ON/OFF`。

可以用这个画面确认 DISP 和 DOOR 各对应哪个物理按键。

### 3.4 SYSPARAM.TXT（需要 `DEBUG_MODE EN`）

调试模式下，拍摄管线初始化时会读取卡根目录的 `SYSPARAM.TXT`。

格式规则：
- 每个条目写成 `[KEY]值1,值2@`，`@` 结束一个条目。
- 空格和回车换行都会被忽略。
- `#` 表示文件结束。
- 数值按十进制解析，`atoi` 风格，允许负号。

最安全的第一个实验是 `sdcard/sysparam-laptime/SYSPARAM.TXT`：

```
[ENABLE_RELEASE_LAP_TIME_DISPLAY]1@
#
```

预期效果：拍摄后显示快门释放的耗时。

其余键名见 `notes/sd-file-entrypoints.zh-CN.md` 第三节。像 `DISABLENR` 和 `CAPTURE_ALL_PIXEL` 这类会改变出片的键，以及 `STORE*` 这类会把 RAW 中间数据写满卡的键，请在确认 lap-time 生效之后再逐个尝试。每次只改一个键。

### 3.5 AUTORUN 脚本（需要 `SCRIPT_EN_MODE EN`，进阶）

开机时如果卡上有 `AUTORUN.541`，相机会执行一种 BASIC 风格的测试脚本，最大 20000 字节，结果追加到 `CHKDAT.541`。

已知的控制流关键字有 `PRINT WAIT GOTO GOSUB IF WHILE FILEOUT FSEARCH TIMERON` 等。和相机操作有关的命令表还没逆向，暂时不建议使用。

## 4. 退出与恢复

1. 用 `disable` 预置脚本，按第 1 节的流程运行一次。
2. 删除卡上的 `00077681.541`、`DEVELOP.MOD`、`SYSPARAM.TXT`、`AUTORUN.541`。
3. 正常开机，确认调试相关的显示已经消失。

备用退出方式（不需要读卡）：MENU → 设置部分的 TEST MODE 页 → `DEBUG MODE DISABLE` → 在 `DISABLE DEBUG MODE ?` 中选 `DISABLE`。它会一次清除 `DEBUG_MODE`、`CARDDOOR_OPEN`、`WRITE_CF_VNDR`、`SCRIPT_EN_MODE`、`SW_DEBUG_MENU` 等标志并保存（`FUN_104F786A`）。

注意：Menu5 的 BOARD TEST 里有 `36 : FLASH INIT`，它会清除全部标志后**重新打开**调试模式和卡门标志，不是退出方式，不要执行。

## 5. 风险与原则

- 只用只读或可逆的命令。所有 `WRITE`、`CLEAR`、`LOAD`、`FIRMUP`、`REGION_CODE` 类操作都需要单独评估。
- 不要在电量低时执行导出或测试。
- 如果出现无法开机或反复进入脚本界面：取出 SD 卡，换上一张只放了 `disable` 脚本加 `DEVELOP.MOD` 的卡，再按第 1 节进入。
- 只有 SD 卡方案失败时才考虑修改固件。这需要单独确认，不在本指南范围内。

## 6. 实机测试记录

| # | 操作 | 预期 | 实际 | 备注 |
| --- | --- | --- | --- | --- |
| 0 | `devmenu` 卡、门开着开机 | 直接出现 Development Menu1 | | 不出现就先排查卡门条件，不要继续后面的步骤 |
| 1 | `enable` 卡、门开着开机 | 出现脚本界面，或无提示直接完成 | | 照片或描述 |
| 2 | 删掉脚本、关门正常开机 | MENU 设置部分在 Setup 页之后多出 TEST MODE 页 | | 这是判断调试模式已开启最可靠的标志 |
| 3 | 按住 OK+DISP 开机 | Development Menu1 | | 不行就试 OK+INFO，或用 `devmenu` 脚本 |
| 4 | Menu2 → SWITCH TEST | 按键名随按键高亮 | | 记下 DISP 和 DOOR 对应的物理键 |
| 5 | `camlog` 卡 | 显示 TOTAL COUNT（快门次数） | | |
| 6 | `backup-cpu-rom`、`backup-dsp-rom`、`backup-adj`、`backup-camlog` | 卡上出现相应文件 | | 文件大小（不要分享文件本身） |
| 7 | `sysparam-laptime`，在调试模式下拍一张 | 显示释放耗时 | | |
| 8 | TEST MODE 页 → STRINGS DISP TEST / Icon Test | 显示字符串或图标列表 | | 只读 |
| 9 | TEST MODE 页 → DEBUG MODE DISABLE → DISABLE | TEST MODE 页消失 | | 菜单退出方式；之后可用 `enable` 卡重新开启 |
| 10 | `disable` 卡 | 恢复正常 | | 卡片退出方式 |

请把这张表的结果反馈回来，导出文件只报告大小、不要发送文件本身，以便据此修正指南。
