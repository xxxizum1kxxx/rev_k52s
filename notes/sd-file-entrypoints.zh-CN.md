[English](sd-file-entrypoints.md) | 简体中文

# SD 卡文件入口

完整的路径字符串及其使用位置见 `notes/sd_paths_raw.txt`（由 `LDI:32` 立即数扫描得到）。文件名中的 `541` 是机型码，来自固件头偏移 0x10。

## 一、会改变相机行为的入口（重点）

| 文件 | 触发时机 | 前置条件 | 处理函数 | 作用 |
| --- | --- | --- | --- | --- |
| `C:\00077681.541` **加上** `C:\DEVELOP.MOD` | 开机时 | 两个文件都必须存在，并满足开机分支条件（见 `debug-script.zh-CN.md`） | `ScriptMode_files_present` → `ScriptMode_load_script` → `ScriptMode_parse_command` → `ScriptMode_execute` | 工厂命令脚本：`[DEBUG_MODE EN]` 等 46 条命令 |
| `C:\AUTORUN.541` | 开机时 | `SCRIPT_EN_MODE` 标志已开，且文件存在（`FUN_105e4a42` → `FUN_1060925a`） | `FUN_1060940e`：读取（最大 20000 字节）后交给解释器（`this+0x60`） | 类 BASIC 的测试脚本语言（下面第二节） |
| `C:\CHKDAT.541` | AUTORUN 执行期间 | 同上 | `FUN_10609da4`（打开并追加写入） | AUTORUN 的结果日志 |
| `C:\SYSPARAM.TXT` | 拍摄管线初始化时（`FUN_104a5a78`） | **DEBUG_MODE 标志已开**（`FUN_10483ef0`） | `FUN_104a5ed2` | 图像管线调试参数，共 90 个左右的键（下面第三节） |
| `C:\FWDC218B.BIN` / `C\D\S.BIN` | 按住 MENU 开机（官方升级流程） | 文件大小必须精确匹配 | `fwup_load_image` | 固件升级 |
| `C:\KB541[B/C/S].BIN`、`C:\KB541.BIN` | 升级流程 | - | `0x104b3bae` 等 | 疑似维修用的整机或分区镜像 |
| `C:\KBCHG.BIN` | 升级流程 | - | `FUN_104b3ac8` | 读取一个参数后传给升级器（`sscanf`） |
| `C:\NOWAIT` | 升级流程 | 文件**不存在**时会等待按键 | `FUN_104b6f3e` | 存在时跳过升级过程中的等待和确认 |

## 二、AUTORUN 脚本语言（控制流关键字）

关键字表位于 0x1079F067：

```
END EXIT PAUSE WAIT GOTO IFGOTO ALLCLR CLS PRINT LANGUAGE COLOR
GOSUB IFGOSUB RETURN IF ELSE WHILE INTERVAL CYCLE FILEOUT FSEARCH TIMERON TIMEROFF
```

错误信息：`Command Error / Command Not Support / Command is Rejected / Illegal Parameter / Syntax Error / Data Over Flow / Script is Finished`。

这和 GR IV 研究中的"工厂脚本"属于同一类机制。相机自身功能对应的命令（不在上表中）由解释器转发给相机命令层，具体的命令表还没提取，留作后续研究方向。

## 三、SYSPARAM.TXT

格式规则：
- 每个条目写成 `[KEY]值1,值2@`，`@` 结束一个条目。
- `#` 或 `0x1A` 表示文件结束。
- 空格、CR、LF 会被忽略。
- 最多读取 0x400 字节。

键名分类：

| 类别 | 键名 |
| --- | --- |
| 数据导出 | `STOREPREBAYER STOREBAYER STOREPREDARK STOREGEN STORE_CIS_INFO STORECPU STOREAE STOREAF STOREIQWD STOREDP STOREDEFECTPIXELDATA STOREVFPNDATA STORE_CAF STORE_LVAE` |
| 降噪与坏点 | `DISABLENR FORCENR DISABLE_ALL_NR DISABLEDPC DISABLE_HW_DPC DISABLE_EX_DPC FORCE_EX_DPC FORCE_LEXP_DPC FORCE_HW_DPC DISABLE_BLACK_DPC DISABLEVFPNCOR ENABLE_SUPER_HIGH_ISO_NR` |
| 拜耳滤波 | `DISABLEBAYFLT DISABLEBAYPREFLT FORCEBAYFLT FORCEBAYPREFLT DISABLE_BAYER_ALL_FILTER FORCE_FINE_SHARPNESS` |
| 传感器（CIS） | `CAPTURE_ALL_PIXEL CAPTURE_ALL_PIXEL_V CIS_DIRECT_GAIN CIS_CLAMP_OFF CIS_SELECT_OFF CIS_READOUT_UPSIDEDOWN CIS_STILL_BLACK_DUMMY CIS_SVR_SHR_SETTING CHANGE_CIS_AD_TIMING SET_CIS_STILL_HD_CYCLE SET_STILL_CLAMP_AREA SET_STILL_CLAMP_LEVEL` |
| 暗场与 OB 校正 | `DISABLE_SUBSTRACT_OB DISABLE_ACT_OB_CORRECT ENABLE_FORCE_ACT_OB_CORRECT ENABLE_DARK_FRAME_TV_RATIO ENABLE_STORE_DFS_FRAME ENABLE_SET_ADD_DFS_OFFSET ENABLE_SET_ADDTIONAL_OB` |
| 阴影校正 | `DISABLE_H_SHADING_CORR DISABLE_V_SHADING_CORR ENABLE_V_SHADING_COEF_FIXED` |
| 增益 | `DIS_ISO_ADJ_GAIN DIS_RGB_ADJ_GAIN DISABLE_CIS_GAIN_DOWN ENABLE_SET_CIS_GAIN_DOWN DIRECT_GAIN` |
| 快门与 B 门 | `BULB_DEBUG DISABLE_BULB_ALG WAIT_CLOSING_CURTAIN ENABLE_DUMMY_RELEASE ENABLE_RELEASE_LAP_TIME_DISPLAY ENABLE_ROLLING_CAPTURE ENABLE_ROLLING_STILL ENABLE_STILL_WINDOW_MODE ENABLE_SVD_1EV_UP` |
| 实时取景 | `LV_MODE LV_DEBUG_SW KILL_LV_AE LV_INVALID_OFFSET_V LIVEVIEW_TEMPERATURE_FREE ENABLE_PHASE_CTL_GUI` |
| DAC 和 DA | `DAC_* DA_* DO_DA_CALIB PM_PARAM` |
| 防抖（SR） | `ENABLE_SR_TRIGGER_26KHZ` |

**风险提示**：其中很多键会改变出片结果，或把大体积 RAW 导出到卡上。建议先试纯显示类的键，例如 `ENABLE_RELEASE_LAP_TIME_DISPLAY`。

## 四、开发与校准数据文件（由工厂命令读写）

| 文件 | 对应命令 | 性质 |
| --- | --- | --- |
| `KB541ADJ.CSV` / `KB541TST.CSV` | `CPU_ADJ/TST_CSV_WRITE/READ` | CPU 校准值的导出和导入 |
| `KB541CPU.BIN` / `KB541DSP.BIN` | `CPU_ROM_STORE` / `DSP_ROM_STORE` | **ROM 导出**（只读，可用来备份；不要再分发） |
| `KB541.ADJ` / `KB541CPU.ADJ` | `*_ADJ_DAT_READ/WRITE`、`ALL_ADJ_DAT_READ` | 校准数据，READ 指从相机读到卡上 |
| `KB541.USR` | `DSP_USR_DAT_READ/WRITE` | 用户数据 |
| `KB541CAM.LOG` | `CAM_LOG_DAT_READ` | 相机日志（快门次数等） |
| `LENSEEP.LNS` / `BACKUP.LNS` | `LENSROM_LOAD/STORE` | 镜头 EEPROM |
| `G200STEP.DAT` | `G200_TEST` | 测试数据 |
| `LENSCPU.bin` | `LENS_CPU_FIRMUP` | 镜头固件升级 |

## 五、其他仅用于导出的路径

还有 RAW、JPEG、CSV 等调试导出路径（`Resu%04d.raw`、`Dfct_*.raw`、`AF%04d.srm`、`DacLog.csv`、`%08d.bin/.jpg`、`MOV%04d.RAW` 等），都是在相应调试开关打开后才会写出，不影响相机的启动行为。
