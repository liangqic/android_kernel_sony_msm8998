#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apply BakaSU / ReSukiSU "manual hook" patches to a Linux 4.4 kernel tree.

Only the four *mandatory* hook points are patched here:

    fs/stat.c        ksu_handle_stat / ksu_handle_newfstat_ret / ksu_handle_fstat64_ret
    fs/exec.c        ksu_handle_execveat / ksu_handle_post_execveat
    fs/open.c        ksu_handle_faccessat
    kernel/reboot.c  ksu_handle_sys_reboot

The setuid / init.rc / input hooks are supplied automatically through LSM
(CONFIG_KSU_MANUAL_HOOK_AUTO_SETUID_HOOK, ..._AUTO_INITRC_HOOK,
..._AUTO_INPUT_HOOK are all =y), so kernel/sys.c, fs/read_write.c and
drivers/input/input.c are intentionally left untouched.

Every replacement must match exactly once, otherwise the script aborts so the
CI job fails loudly instead of producing a half-patched kernel.

Usage:  python3 patch_manual_hook.py [kernel_source_root]
"""

import os
import sys

IF = "#ifdef CONFIG_KSU_MANUAL_HOOK"
END = "#endif"


def L(*lines):
    """Join lines with \\n, keeping the leading newline convention explicit."""
    return "\n".join(lines)


def patch(root, relpath, old, new, tag):
    path = os.path.join(root, relpath)
    if not os.path.isfile(path):
        sys.exit("[manual-hook] ERROR: %s not found" % path)
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()
    hits = src.count(old)
    if hits != 1:
        sys.exit(
            "[manual-hook] ERROR: anchor '%s' matched %d times in %s (expected 1)"
            % (tag, hits, relpath)
        )
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(src.replace(old, new, 1))
    print("[manual-hook]   ok  %-16s %s" % (tag, relpath))


def check_pp_balance(root, relpath):
    """Catch a missing #endif before the compiler does."""
    path = os.path.join(root, relpath)
    opens = closes = 0
    with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("#if"):
                opens += 1
            elif stripped.startswith("#endif"):
                closes += 1
    if opens != closes:
        sys.exit(
            "[manual-hook] ERROR: unbalanced preprocessor conditionals in %s "
            "(#if*=%d, #endif=%d)" % (relpath, opens, closes)
        )
    print("[manual-hook]   ok  pp-balance       %s (#if*=%d)" % (relpath, opens))


# ---------------------------------------------------------------- stat.c chunks
STAT_DECL = L(
    IF,
    "__attribute__((hot))",
    "extern int ksu_handle_stat(int *dfd, const char __user **filename_user,",
    "\t\t\t\tint *flags);",
    "",
    "extern void ksu_handle_newfstat_ret(unsigned int *fd, struct stat __user **statbuf_ptr);",
    "#if defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_COMPAT_STAT64)",
    "extern void ksu_handle_fstat64_ret(unsigned long *fd, struct stat64 __user **statbuf_ptr);",
    END,
    END,
    "",
    "",
)

STAT_ANCHOR = L(
    "#if !defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_SYS_NEWFSTATAT)",
    "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,",
)

STAT_FSTATAT_OLD = L(
    "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,",
    "\t\tstruct stat __user *, statbuf, int, flag)",
    "{",
    "\tstruct kstat stat;",
    "\tint error;",
    "",
)

STAT_FSTATAT_NEW = L(
    "SYSCALL_DEFINE4(newfstatat, int, dfd, const char __user *, filename,",
    "\t\tstruct stat __user *, statbuf, int, flag)",
    "{",
    "\tstruct kstat stat;",
    "\tint error;",
    "",
    IF,
    "\tksu_handle_stat(&dfd, &filename, &flag);",
    END,
    "",
)

STAT_FSTAT_OLD = L(
    "SYSCALL_DEFINE2(newfstat, unsigned int, fd, struct stat __user *, statbuf)",
    "{",
    "\tstruct kstat stat;",
    "\tint error = vfs_fstat(fd, &stat);",
    "",
    "\tif (!error)",
    "\t\terror = cp_new_stat(&stat, statbuf);",
    "",
    "\treturn error;",
)

STAT_FSTAT_NEW = L(
    "SYSCALL_DEFINE2(newfstat, unsigned int, fd, struct stat __user *, statbuf)",
    "{",
    "\tstruct kstat stat;",
    "\tint error = vfs_fstat(fd, &stat);",
    "",
    "\tif (!error)",
    "\t\terror = cp_new_stat(&stat, statbuf);",
    "",
    IF,
    "\tksu_handle_newfstat_ret(&fd, &statbuf);",
    END,
    "",
    "\treturn error;",
)

STAT_FSTAT64_OLD = L(
    "SYSCALL_DEFINE2(fstat64, unsigned long, fd, struct stat64 __user *, statbuf)",
    "{",
    "\tstruct kstat stat;",
    "\tint error = vfs_fstat(fd, &stat);",
    "",
    "\tif (!error)",
    "\t\terror = cp_new_stat64(&stat, statbuf);",
    "",
    "\treturn error;",
)

STAT_FSTAT64_NEW = L(
    "SYSCALL_DEFINE2(fstat64, unsigned long, fd, struct stat64 __user *, statbuf)",
    "{",
    "\tstruct kstat stat;",
    "\tint error = vfs_fstat(fd, &stat);",
    "",
    "\tif (!error)",
    "\t\terror = cp_new_stat64(&stat, statbuf);",
    "",
    IF,
    "\tksu_handle_fstat64_ret(&fd, &statbuf);",
    END,
    "",
    "\treturn error;",
)

# ---------------------------------------------------------------- exec.c chunks
EXEC_DECL = L(
    IF,
    "__attribute__((hot))",
    "extern int ksu_handle_execveat(int *fd, struct filename **filename_ptr,",
    "\t\t\t\tvoid *argv, void *envp, int *flags);",
    "__attribute__((hot))",
    "extern int ksu_handle_post_execveat(int *fd, struct filename **filename_ptr,",
    "\t\t\t\tvoid *argv, void *envp, int *flags, int *retval);",
    END,
    "",
    "",
)

EXEC_ANCHOR = "static int do_execveat_common(int fd, struct filename *filename,"

EXEC_ENTER_OLD = L(
    "\tstruct files_struct *displaced;",
    "\tint retval;",
    "",
    "\tif (IS_ERR(filename))",
)

EXEC_ENTER_NEW = L(
    "\tstruct files_struct *displaced;",
    "\tint retval;",
    "",
    IF,
    "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);",
    END,
    "",
    "\tif (IS_ERR(filename))",
)

EXEC_OUT_OLD = L(
    "out_ret:",
    "\tputname(filename);",
    "\treturn retval;",
    "}",
)

EXEC_OUT_NEW = L(
    "out_ret:",
    "",
    IF,
    "\tksu_handle_post_execveat(&fd, &filename, &argv, &envp, &flags, &retval);",
    END,
    "",
    "\tputname(filename);",
    "\treturn retval;",
    "}",
)

# ---------------------------------------------------------------- open.c chunks
OPEN_DECL = L(
    IF,
    "__attribute__((hot))",
    "extern int ksu_handle_faccessat(int *dfd, const char __user **filename_user,",
    "\t\t\t\tint *mode, int *flags);",
    END,
    "",
    "",
)

OPEN_ANCHOR = L(
    "SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)",
    "{",
)

OPEN_CALL_OLD = L(
    "\tint res;",
    "\tunsigned int lookup_flags = LOOKUP_FOLLOW;",
    "",
    "\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */",
)

OPEN_CALL_NEW = L(
    "\tint res;",
    "\tunsigned int lookup_flags = LOOKUP_FOLLOW;",
    "",
    IF,
    "\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);",
    END,
    "",
    "\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */",
)

# -------------------------------------------------------------- reboot.c chunks
REBOOT_DECL = L(
    IF,
    "extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg);",
    END,
    "",
    "",
)

REBOOT_ANCHOR = L(
    "SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,",
    "\t\tvoid __user *, arg)",
    "{",
)

REBOOT_CALL_OLD = L(
    "\tchar buffer[256];",
    "\tint ret = 0;",
    "",
    "\t/* We only trust the superuser with rebooting the system. */",
)

REBOOT_CALL_NEW = L(
    "\tchar buffer[256];",
    "\tint ret = 0;",
    "",
    IF,
    "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);",
    END,
    "",
    "\t/* We only trust the superuser with rebooting the system. */",
)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    print("[manual-hook] kernel source root: %s" % root)

    patch(root, "fs/stat.c", STAT_ANCHOR, STAT_DECL + STAT_ANCHOR, "stat-decl")
    patch(root, "fs/stat.c", STAT_FSTATAT_OLD, STAT_FSTATAT_NEW, "stat-fstatat")
    patch(root, "fs/stat.c", STAT_FSTAT_OLD, STAT_FSTAT_NEW, "stat-fstat")
    patch(root, "fs/stat.c", STAT_FSTAT64_OLD, STAT_FSTAT64_NEW, "stat-fstat64")

    patch(root, "fs/exec.c", EXEC_ANCHOR, EXEC_DECL + EXEC_ANCHOR, "exec-decl")
    patch(root, "fs/exec.c", EXEC_ENTER_OLD, EXEC_ENTER_NEW, "exec-enter")
    patch(root, "fs/exec.c", EXEC_OUT_OLD, EXEC_OUT_NEW, "exec-outret")

    patch(root, "fs/open.c", OPEN_ANCHOR, OPEN_DECL + OPEN_ANCHOR, "open-decl")
    patch(root, "fs/open.c", OPEN_CALL_OLD, OPEN_CALL_NEW, "open-faccessat")

    patch(root, "kernel/reboot.c", REBOOT_ANCHOR, REBOOT_DECL + REBOOT_ANCHOR, "reboot-decl")
    patch(root, "kernel/reboot.c", REBOOT_CALL_OLD, REBOOT_CALL_NEW, "reboot-call")

    for rel in ("fs/stat.c", "fs/exec.c", "fs/open.c", "kernel/reboot.c"):
        check_pp_balance(root, rel)

    print("[manual-hook] all hooks patched successfully")


if __name__ == "__main__":
    main()
