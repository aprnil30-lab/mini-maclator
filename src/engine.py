import os
import struct
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_INTR
from unicorn.arm64_const import (
    UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3,
    UC_ARM64_REG_X8, UC_ARM64_REG_X16, UC_ARM64_REG_PC, UC_ARM64_REG_SP
)
import capstone
from macho_loader import MachOLoader
from audio_bridge import AudioBridge
from gpu_surface_bridge import IOSurfaceBridge

STACK_ADDR = 0x700000000000
STACK_SIZE = 0x200000  # 2MB 栈空间

class MiniMaclator:
    def __init__(self):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.cs = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        self.audio_bridge = AudioBridge()
        self.gpu_bridge = IOSurfaceBridge()
        
        # 映射栈空间
        self.uc.mem_map(STACK_ADDR, STACK_SIZE)
        self.uc.reg_write(UC_ARM64_REG_SP, STACK_ADDR + STACK_SIZE - 0x1000)
        
        # 挂载中断拦截钩子
        self.uc.hook_add(UC_HOOK_INTR, self.hook_syscall)

    def hook_syscall(self, uc, intno, user_data):
        pc = uc.reg_read(UC_ARM64_REG_PC)
        sys_no = uc.reg_read(UC_ARM64_REG_X16)
        if sys_no == 0:
            sys_no = uc.reg_read(UC_ARM64_REG_X8)

        a0 = uc.reg_read(UC_ARM64_REG_X0)
        a1 = uc.reg_read(UC_ARM64_REG_X1)
        a2 = uc.reg_read(UC_ARM64_REG_X2)

        # 4: write(fd, buf, count)
        if sys_no in (4, 64):
            buf = uc.mem_read(a1, a2)
            try:
                os.write(a0, buf)
                uc.reg_write(UC_ARM64_REG_X0, len(buf))
            except Exception:
                uc.reg_write(UC_ARM64_REG_X0, -1)
        # 1: exit(status)
        elif sys_no in (1, 93):
            print(f"\n[MiniMaclator] 进程正常退出, ExitCode={a0}")
            uc.emu_stop()
        # 核心超越特性 1: 沙盒绕过 (Sandbox Check 强行放行)
        elif sys_no == 0x200:
            print(f"[MiniMaclator] 拦截到 Sandbox Check (Syscall 0x200), 伪造放行返回 0")
            uc.reg_write(UC_ARM64_REG_X0, 0)
        # 核心超越特性 2: IOKit 服务句柄 Mock (避免无硬件闪退)
        elif sys_no == 0x201:
            print(f"[MiniMaclator] 拦截到 IOKit Matching 服务查询, 返回虚拟硬件句柄 0x1337")
            uc.reg_write(UC_ARM64_REG_X0, 0x1337)
        # 核心超越特性 3: 音频 AudioQueue/HAL 调度拦截 (捕获 PCM 数据流)
        elif sys_no == 0x202:
            buf_addr = a0
            buf_size = a1
            res = self.audio_bridge.handle_audio_stream(uc, buf_addr, buf_size)
            uc.reg_write(UC_ARM64_REG_X0, res)
        # 核心超越特性 4: CAMetalLayer / IOSurface 纹理呈现拦截
        elif sys_no == 0x203:
            surface_id = a0
            frame_buf_addr = a1
            res = self.gpu_bridge.present_drawable(uc, surface_id, frame_buf_addr)
            uc.reg_write(UC_ARM64_REG_X0, res)
        else:
            print(f"[MiniMaclator] 未知 Syscall: {sys_no} at PC=0x{pc:x}")
            uc.reg_write(UC_ARM64_REG_X0, 0)

    def run_macho(self, macho_path):
        """
        直接加载并执行一个真实的 ARM64 Mach-O 二进制文件
        """
        loader = MachOLoader(macho_path)
        entry_point = loader.map_into_emulator(self.uc)
        self.uc.reg_write(UC_ARM64_REG_PC, entry_point)

        print(f"[MiniMaclator] 启动执行 Mach-O 入口点: 0x{entry_point:09x}...")
        try:
            self.uc.emu_start(entry_point, entry_point + 0x1000000)
        except Exception as e:
            pc = self.uc.reg_read(UC_ARM64_REG_PC)
            print(f"[MiniMaclator] 执行中断/结束于 PC=0x{pc:x}")
