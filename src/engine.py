import struct
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (
    UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3,
    UC_ARM64_REG_X8, UC_ARM64_REG_X16, UC_ARM64_REG_PC, UC_ARM64_REG_SP
)
import capstone

# 内存基址映射定义
BASE_ADDR = 0x100000000
STACK_ADDR = 0x200000000
STACK_SIZE = 0x100000

class MiniMaclator:
    def __init__(self):
        # 1. 初始化 ARM64 模拟引擎
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        
        # 2. 映射内存区域 (4KB/16KB 对齐)
        self.uc.mem_map(BASE_ADDR, 0x100000)      # 代码段 1MB
        self.uc.mem_map(STACK_ADDR, STACK_SIZE)   # 栈段 1MB
        
        # 设置栈指针 SP
        self.uc.reg_write(UC_ARM64_REG_SP, STACK_ADDR + STACK_SIZE - 0x1000)
        
        # 3. 注册中断 Hook（用于截获 ARM64 SVC 系统调用）
        self.uc.hook_add(unicorn.UC_HOOK_INTR, self.hook_syscall)

    def hook_syscall(self, uc, intno, user_data):
        """
        拦截 ARM64 的系统调用并进行桥接
        macOS ARM64 BSD Syscall 规范:
        - X16 / X8: Syscall 号 (macOS 惯用 X16, Linux 惯用 X8, 此处实现两者的兼容桥接)
        - X0 - X5: 入参
        - 返回值写回 X0
        """
        pc = uc.reg_read(UC_ARM64_REG_PC)
        # 检查触发的寄存器 (兼容标准与 macOS 习惯)
        sys_no = uc.reg_read(UC_ARM64_REG_X16)
        if sys_no == 0:
            sys_no = uc.reg_read(UC_ARM64_REG_X8)
            
        a0 = uc.reg_read(UC_ARM64_REG_X0)
        a1 = uc.reg_read(UC_ARM64_REG_X1)
        a2 = uc.reg_read(UC_ARM64_REG_X2)

        # 4: write(fd, buf, count)
        if sys_no in (4, 64):
            # 从虚拟机内存读取字符串
            buf = uc.mem_read(a1, a2)
            import os
            try:
                os.write(a0, buf)
                uc.reg_write(UC_ARM64_REG_X0, len(buf))
            except Exception as e:
                uc.reg_write(UC_ARM64_REG_X0, -1)
        # 1: exit(status)
        elif sys_no in (1, 93):
            print(f"\n[MiniMaclator] 进程正常退出, 状态码: {a0}")
            uc.emu_stop()
        # 针对图片中提到的痛点进行 Mock 增强:
        # Mock 1: 沙盒与权限检查 (Sandbox check) 始终返回允许 (0)
        elif sys_no == 0x200: # 假定 sandbox_check
            print(f"[MiniMaclator] 拦截到 Sandbox Check, 强行放行返回 0")
            uc.reg_write(UC_ARM64_REG_X0, 0)
        # Mock 2: IOKit 服务查询 (IOServiceGetMatchingService) 返回模拟句柄
        elif sys_no == 0x201:
            print(f"[MiniMaclator] 拦截到 IOKit 请求, 返回通用虚拟设备句柄")
            uc.reg_write(UC_ARM64_REG_X0, 0x1337)
        else:
            print(f"[MiniMaclator] 未知/未桥接 Syscall 号: {sys_no}, PC=0x{pc:x}")
            uc.reg_write(UC_ARM64_REG_X0, 0)

    def load_and_run(self, code_bytes, entry_offset=0):
        print(f"[MiniMaclator] 正在写入 ARM64 机器码 (长度: {len(code_bytes)} 字节)...")
        self.uc.mem_write(BASE_ADDR, code_bytes)
        self.uc.reg_write(UC_ARM64_REG_PC, BASE_ADDR + entry_offset)
        
        print("[MiniMaclator] 开始在 x86_64 宿主机上模拟执行 ARM64 二进制...")
        try:
            self.uc.emu_start(BASE_ADDR + entry_offset, BASE_ADDR + len(code_bytes))
        except Exception as e:
            pc = self.uc.reg_read(UC_ARM64_REG_PC)
            print(f"[MiniMaclator] 执行中断于 PC=0x{pc:x}: {e}")
            # 反汇编中断位置指令
            chunk = self.uc.mem_read(pc, 16)
            for i in self.cs.disasm(chunk, pc):
                print(f" -> 崩溃点指令: 0x{i.address:x}:\t{i.mnemonic}\t{i.op_str}")
                break

import unicorn
