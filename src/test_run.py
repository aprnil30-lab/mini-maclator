"""
精确计算 ADR 偏移的测试运行器
"""
import struct
from engine import MiniMaclator
import unicorn

def assemble_and_run():
    # 字符串数据
    msg = b"Hello from ARM64 on x86_64 host! (MiniMaclator)\n"
    msg_len = len(msg)

    # 我们构建 9 条指令 (36 字节)
    # 指令 0: ADR X1, msg (偏移 +36 字节)
    # ARM64 ADR 指令格式:
    # imm = 36 = 0b100100 -> immlo=0b00, immhi=0b0000000000000001001
    # 指令 0..9 共 10 条指令 = 40 字节
    # 指令 0: 0x00
    # 指令 1: 0x04
    # 指令 2: 0x08
    # 指令 3: 0x0C
    # 指令 4: 0x10 (SVC)
    # 指令 5: 0x14
    # 指令 6: 0x18 (SVC)
    # 指令 7: 0x1C
    # 指令 8: 0x20
    # 指令 9: 0x24 (SVC exit)
    # 数据起始于 0x28 (40 字节)
    imm = 40
    immlo = imm & 3
    immhi = (imm >> 2) & 0x7FFFF
    adr_x1 = 0x10000000 | (immlo << 29) | (immhi << 5) | 1

    code = bytearray()
    code += struct.pack("<I", adr_x1)                      # 0x00: ADR X1, #36
    code += struct.pack("<I", 0xd2800020)                  # 0x04: MOV X0, #1
    code += struct.pack("<I", 0xd2800002 | (msg_len << 5)) # 0x08: MOV X2, len
    code += struct.pack("<I", 0xd2800090)                  # 0x0C: MOV X16, #4 (sys_write)
    code += struct.pack("<I", 0xd4001001)                  # 0x10: SVC #0x80

    # 模拟图片中提到的重点：沙盒拦截与透传
    code += struct.pack("<I", 0xd2804010)                  # 0x14: MOV X16, #0x200 (mock sandbox_check)
    code += struct.pack("<I", 0xd4001001)                  # 0x18: SVC #0x80

    # 退出进程
    code += struct.pack("<I", 0xd2800000)                  # 0x1C: MOV X0, #0
    code += struct.pack("<I", 0xd2800030)                  # 0x20: MOV X16, #1 (sys_exit)
    code += struct.pack("<I", 0xd4001001)                  # 0x24: SVC #0x80

    # 0x24 之后 (即 +36 处) 放入字符串数据
    code += msg

    emulator = MiniMaclator()
    emulator.load_and_run(bytes(code))

if __name__ == "__main__":
    assemble_and_run()
