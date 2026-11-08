# 用 GitHub Actions 编一颗「最新版 ReSukiSU」的 maple_dsds 内核

目标：绕开你现在这颗内核的限制——XDA 帖给的 `ReSukiSU-34781-maple_dsds.zip` 里内核侧 KSU 核心是 **34781**，
而 ReSukiSU 管理器最低要求 **35061**，所以管理器顶部永远一条红条「需要更新内核」。

自编一颗新内核后，内核侧 KSU 版本会跟到最新（≥ 35171），红条消失，管理器所有功能正常。

---

## 0. 为什么是这条路

| 事实 | 来源 |
|---|---|
| 内核仓库 `justinlin099/android_kernel_sony_msm8998` 有 maple_dsds 的 defconfig，`lineage-22.1` / `lineage-22.2` 分支都在 | 实测两个分支的 `lineage-msm8998-yoshino-maple_dsds_defconfig` 均 HTTP 200 |
| ReSukiSU 官方集成脚本 `kernel/setup.sh` 会自动 `git clone https://github.com/Baka-SU/BakaSU` 并给 `drivers/` 挂钩子 | 读了脚本原文 |
| 该 defconfig 已含 `CONFIG_KPROBES=y`、`CONFIG_MODULES=y`、`CONFIG_OVERLAY_FS=y`、`CONFIG_TMPFS_XATTR=y` | grep 过原始 defconfig |
| ReSukiSU 没有适配 4.4 的 LKM（只支持 GKI 5.10+），**只能编进内核** | resukisu 文档 |

---

## 1. Fork 内核仓库

1. 打开 https://github.com/justinlin099/android_kernel_sony_msm8998
2. 右上 `Fork` → `Create fork`（只 fork 默认分支即可，稍后切分支）
3. 在你的 fork 里把分支切到 **`lineage-22.1`**（和你手机上的 ROM 版本对齐）
   - 分支下拉框 → `View all branches` → 选 `lineage-22.1`

## 2. 上传两个东西

在 fork 首页点 `Add file` → `Upload files`，把这两样拖进去：

```
.github/workflows/build-kernel.yml     ← 编译流水线
anykernel3/                            ← AnyKernel3 刷机包骨架（tools/、META-INF/ 等）
```

> `anykernel3/` 里**不要**放 `Image`（产物由流水线自动填进去）。
> 网页上传支持整个文件夹拖拽；如果不行，就打包成 zip 上传后解压。

提交信息随便写，比如 `ci: build kernel with ReSukiSU`。

## 3. 启用 Actions

fork 出来的仓库第一次进 `Actions` 标签页会有一条提示：

> Workflows aren't being run on this forked repository.
> **I understand my workflows, go ahead and enable them**

点那个按钮启用。

## 4. 跑一次编译

1. `Actions` → 左侧 `Build Kernel (maple_dsds + ReSukiSU)`
2. 右侧 `Run workflow`：
   - **Use workflow from**: `lineage-22.1`（务必选对分支）
   - `ksu_ref`: 保持 `main`（想要特定版本可填 tag/commit）
   - `defconfig`: 保持默认
3. 点绿色 `Run workflow`

耗时大约 **30–60 分钟**（4.4 内核 + LTO 关闭，一般 25–40 分钟）。

## 5. 取产物

跑完后进那次运行 → 页面底部 `Artifacts` → 下载 `ReSukiSU-kernel-maple_dsds.zip`，里面有：

- `ReSukiSU-kernel-maple_dsds.zip` ← **这个丢进 TWRP 刷**
- `Image` ← 裸内核，备用（可以在 ReSukiSU 管理器的「刷写 AnyKernel3」里选）

## 6. 刷之前：先备份当前 boot（1 分钟，强烈建议）

手机进 TWRP（`adb reboot recovery`），然后在电脑上：

```powershell
adb shell "dd if=/dev/block/bootdevice/by-name/boot of=/sdcard1/ROM/backup/boot-blessed.img bs=1M"
```

出问题就把它刷回去（TWRP Install → 右下 `Install Image` → 选这个文件 → 分区选 `Boot`）。

## 7. 刷入

1. 把 `ReSukiSU-kernel-maple_dsds.zip` 拷到 SD 卡（`/sdcard1/ROM/`）
2. TWRP → `Install` → 选中它 → 滑一下
3. 屏幕会显示 `ReSukiSU (GitHub Actions build) for maple_dsds` + `Checking device... maple_dsds` + `Done!`
4. `Reboot System`，首次开机慢一点（3–10 分钟，可能自己软重启一次）

## 8. 验收

```powershell
adb shell "cat /proc/version"            # 内核时间戳应该是今天
adb shell "su -c id"                     # 应为 uid=0(root) context=u:r:ksu:s0
```

打开 ReSukiSU 管理器：
- 顶部红条**应该消失**
- 「工作中」卡片显示的版本号应 ≥ `35171`
- 如果管理器还是旧版，去 `设置 → 检查管理器更新` 或直接装最新 APK

---

## 编译失败怎么办

把 Actions 里失败的 step 日志（从 `Error` 往上 30 行）发我，我按报错改 workflow。常见三类：

| 报错 | 原因 | 改法 |
|---|---|---|
| `error: unknown target ...` / missing header | 工具链版本不对 | 换 clang 版本（把第 2 步的 `clang-r416183b` 换成别的 tag） |
| `-Werror=...` 大面积报错 | 内核代码对新编译器太旧 | 已加 `KCFLAGS="-Wno-error"`；仍有的话再加 `CONFIG_WERROR=n` |
| `drivers/kernelsu` 目录为空 / `No rule to make target` | setup.sh 没跑成 | 看第 3 步日志，确认 `KernelSU/` 有内容、`drivers/kernelsu` 是软链 |
| 刷完卡在开机动画 | 内核与 22.1 的 DTB/vendor 不匹配 | 回滚 boot 备份，改用 `lineage-22.2` 分支编一版试 |

---

## 附：这套东西的边界

- **只换内核，不换 ROM**：ramdisk、vendor、TWRP 都不会被动（AnyKernel3 只 patch boot 里的 kernel）。
- **不会碰你的数据**：不 format、不 wipe。
- **SIM 卡问题跟这个无关**：你现在 `gsm.sim.state=ABSENT,ABSENT` 是因为还没插卡，插上再看。
