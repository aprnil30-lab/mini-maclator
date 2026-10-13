"""
生成一个真实格式的 ARM64 Mach-O 可执行二进制文件 (支持 LC_SEGMENT_64 + LC_UNIXTHREAD)
"""
import struct
import os

def create_sample_arm64_macho(output_path):
    # 1. 构造 ARM64 机器指令
    msg = b"[Mach-O Native Execution] Hello from parsed ARM64 Mach-O Binary!\n\0"
    msg_len = len(msg) - 1
    
    # 汇编代码逻辑:
    # 0x00: adr x1, #36 (跳转到数据偏移)
    # 0x04: mov x0, #1 (stdout)
    # 0x08: mov x2, len
    # 0x0C: mov x16, #4 (sys_write)
    # 0x10: svc #0x80
    # 0x14: mov x16, #0x200 (sandbox check)
    # 0x18: svc #0x80
    # 0x1C: mov x0, #0 (exit 0)
    # 0x20: mov x16, #1
    # 0x24: svc #0x80
    imm = 40
    immlo = imm & 3
    immhi = (imm >> 2) & 0x7FFFF
    adr_x1 = 0x10000000 | (immlo << 29) | (immhi << 5) | 1

    code = bytearray()
    code += struct.pack("<I", adr_x1)
    code += struct.pack("<I", 0xd2800020)
    code += struct.pack("<I", 0xd2800002 | (msg_len << 5))
    code += struct.pack("<I", 0xd2800090)
    code += struct.pack("<I", 0xd4001001)
    code += struct.pack("<I", 0xd2804010)
    code += struct.pack("<I", 0xd4001001)
    code += struct.pack("<I", 0xd2800000)
    code += struct.pack("<I", 0xd2800030)
    code += struct.pack("<I", 0xd4001001)
    code += msg

    # 2. 组装 Mach-O Header 与 Load Commands
    VM_ADDR = 0x100000000
    PAGE_SIZE = 0x1000

    # LC_SEGMENT_64
    cmd_seg = 0x19
    cmdsize_seg = 72  # 无 section 时 72 字节
    segname = b"__TEXT".ljust(16, b"\x00")
    vmaddr = VM_ADDR
    vmsize = PAGE_SIZE
    fileoff = 0
    filesize = PAGE_SIZE
    maxprot = 7 # rwx
    initprot = 5 # r-x
    nsects = 0
    flags = 0

    seg_bytes = struct.pack(
        "<II16sQQQQIIII",
        cmd_seg, cmdsize_seg, segname,
        vmaddr, vmsize, fileoff, filesize,
        maxprot, initprot, nsects, flags
    )

    # LC_UNIXTHREAD (ARM64)
    cmd_thread = 0x5
    flavor = 6  # ARM_THREAD_STATE64
    count = 68 # 68 words = 34 个 64-bit 值 (x0~x30, fp, lr, sp, pc)
    cmdsize_thread = 16 + (count * 4)  # 16 + 272 = 288
    
    thread_header = struct.pack("<IIII", cmd_thread, cmdsize_thread, flavor, count)
    # 填充 31 个寄存器 (x0~x30) + sp(31) + pc(32) + cpsr(33)
    regs = [0] * 34
    entry_offset = 0x200 # 代码段放在文件偏移 0x200 处
    regs[32] = VM_ADDR + entry_offset # PC
    thread_data = thread_header + b"".join(struct.pack("<Q", r) for r in regs)

    ncmds = 2
    sizeofcmds = len(seg_bytes) + len(thread_data)
    
    # Mach-O 64-bit Header
    magic = 0xfeedfacf
    cputype = 0x0100000c # ARM64
    cpusubtype = 0x0
    filetype = 0x2 # MH_EXECUTE
    hdr_flags = 0x00200085
    reserved = 0
    header = struct.pack("<IIIIIIII", magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, hdr_flags, reserved)

    # 合成完整的 Mach-O 文件
    macho_data = bytearray(PAGE_SIZE)
    header_all = header + seg_bytes + thread_data
    macho_data[0:len(header_all)] = header_all
    macho_data[entry_offset:entry_offset + len(code)] = code

    with open(output_path, "wb") as f:
        f.write(macho_data)
    print(f"已生成 ARM64 Mach-O 测试样本: {output_path} ({len(macho_data)} 字节)")

if __name__ == "__main__":
    create_sample_arm64_macho("/root/maclator_mini/tests/sample_arm64.macho")
