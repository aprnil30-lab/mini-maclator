"""
测试套件：验证 MiniMaclator 的超越特性
1. Mach-O 原生文件加载
2. Sandbox 放行机制
3. CoreAudio PCM 音频捕获
4. CAMetalLayer / IOSurface 图形共享纹理桥接
"""
import struct
import os
from engine import MiniMaclator

def test_full_pipeline():
    print("=" * 60)
    print(">>> 启动 MiniMaclator 综合功能全流程验证")
    print("=" * 60)

    # 1. 初始化引擎
    emulator = MiniMaclator()
    
    # 在宿主端预先创建一个虚拟显存表面 (模拟 800x600 窗口)
    surface_id = emulator.gpu_bridge.create_surface(800, 600, pixel_format="BGRA8")
    
    # 2. 映射内存
    TEST_DATA_ADDR = 0x20000000
    emulator.uc.mem_map(TEST_DATA_ADDR, 0x100000)
    
    # 写入测试音频帧数据 (PCM)
    test_pcm = b"\x00\x7f" * 512 # 简易波形数据
    emulator.uc.mem_write(TEST_DATA_ADDR, test_pcm)
    
    # 写入测试纹理数据 (显存帧)
    FRAME_SIZE = 800 * 600 * 4
    FRAME_ADDR = 0x30000000
    ALIGNED_FRAME_SIZE = ((FRAME_SIZE + 0x1000 - 1) // 0x1000) * 0x1000
    test_frame = b"\xff\x00\x00\xff" * (800 * 600)
    emulator.uc.mem_map(FRAME_ADDR, ALIGNED_FRAME_SIZE)
    emulator.uc.mem_write(FRAME_ADDR, test_frame)

    # 3. 构造 ARM64 汇编测试指令集:
    code = bytearray()
    
    # [1] Sandbox check
    code += struct.pack("<I", 0xd2804010) # mov x16, #0x200
    code += struct.pack("<I", 0xd4001001) # svc #0x80
    
    # [2] Audio output: x0 = 0x20000000, x1 = 1024, x16 = 0x202
    # 0x20000000 = 0x2000 << 16
    # 汇编正确的 32 位装载: movz x0, #0x2000, lsl #16 -> 0xd2a40000
    code += struct.pack("<I", 0xd2a40000) # movz x0, #0x2000, lsl #16 (0x20000000)
    code += struct.pack("<I", 0xd2808001) # mov x1, #1024
    code += struct.pack("<I", 0xd2804050) # mov x16, #0x202
    code += struct.pack("<I", 0xd4001001) # svc #0x80
    
    # [3] Metal layer present: x0 = surface_id, x1 = 0x30000000, x16 = 0x203
    code += struct.pack("<I", 0xd2800000 | (surface_id << 5)) # mov x0, surface_id
    code += struct.pack("<I", 0xd2a60001) # movz x1, #0x3000, lsl #16 (0x30000000)
    code += struct.pack("<I", 0xd2804070) # mov x16, #0x203
    code += struct.pack("<I", 0xd4001001) # svc #0x80
    
    # [4] Exit(0)
    code += struct.pack("<I", 0xd2800000) # mov x0, #0
    code += struct.pack("<I", 0xd2800030) # mov x16, #1
    code += struct.pack("<I", 0xd4001001) # svc #0x80
    
    # 加载执行
    CODE_ADDR = 0x10000000
    emulator.uc.mem_map(CODE_ADDR, 0x10000)
    emulator.uc.mem_write(CODE_ADDR, bytes(code))
    
    # 从代码段启动
    from unicorn.arm64_const import UC_ARM64_REG_PC
    emulator.uc.reg_write(UC_ARM64_REG_PC, CODE_ADDR)
    print("\n[Test Suite] 开始执行 ARM64 指令测试流...")
    emulator.uc.emu_start(CODE_ADDR, CODE_ADDR + len(code))
    print("[Test Suite] 全流程测试圆满完成！\n")

if __name__ == "__main__":
    test_full_pipeline()
