import os
import struct

class MachOLoader:
    """
    轻量原生 Mach-O (64-bit ARM64) 解析与装载器
    支持解析:
    - Mach Header (CPU Type, Subtype, Filetype, ncmds)
    - Load Commands:
        - LC_SEGMENT_64 (映射 __TEXT, __DATA 等内存段)
        - LC_MAIN / LC_UNIXTHREAD (确定程序实际入口 Entrypoint)
    """
    MH_MAGIC_64 = 0xfeedfacf
    MH_CIGAM_64 = 0xcffaedfe
    CPU_TYPE_ARM64 = 0x0100000c
    
    LC_SEGMENT_64 = 0x19
    LC_UNIXTHREAD = 0x5
    LC_MAIN = 0x80000028

    def __init__(self, filepath):
        self.filepath = filepath
        self.segments = []
        self.entry_point = 0
        self.base_vm_addr = 0
        self.parse()

    def parse(self):
        with open(self.filepath, "rb") as f:
            data = f.read()

        magic, cputype, cpusubtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from(
            "<IIIIIIII", data, 0
        )

        if magic != self.MH_MAGIC_64:
            raise ValueError(f"不支持的文件格式: Magic=0x{magic:08x}, 仅支持 64-bit Mach-O (0x{self.MH_MAGIC_64:08x})")

        if cputype != self.CPU_TYPE_ARM64:
            raise ValueError(f"不支持的 CPU 架构: CPU_TYPE=0x{cputype:08x}, 仅支持 ARM64 (0x{self.CPU_TYPE_ARM64:08x})")

        offset = 32  # 64-bit mach_header 大小
        for _ in range(ncmds):
            cmd, cmdsize = struct.unpack_from("<II", data, offset)
            
            # 1. 段加载命令: LC_SEGMENT_64
            if cmd == self.LC_SEGMENT_64:
                segname = data[offset+8:offset+24].split(b"\x00")[0].decode("ascii", errors="ignore")
                vmaddr, vmsize, fileoff, filesize, maxprot, initprot, nsects, flags = struct.unpack_from(
                    "<QQQQIIII", data, offset + 24
                )
                
                seg_bytes = data[fileoff:fileoff+filesize] if filesize > 0 else b""
                self.segments.append({
                    "name": segname,
                    "vmaddr": vmaddr,
                    "vmsize": vmsize,
                    "fileoff": fileoff,
                    "filesize": filesize,
                    "initprot": initprot,
                    "data": seg_bytes
                })
                if segname == "__TEXT" and self.base_vm_addr == 0:
                    self.base_vm_addr = vmaddr

            # 2. 现代程序入口: LC_MAIN
            elif cmd == self.LC_MAIN:
                entryoff, stacksize = struct.unpack_from("<QQ", data, offset + 8)
                self.entry_point = self.base_vm_addr + entryoff

            # 3. 经典/无 libc 程序入口: LC_UNIXTHREAD
            elif cmd == self.LC_UNIXTHREAD:
                # ARM64 thread state 结构体包含 32 个通用寄存器 + PC 等
                # 偏移 16 字节为 state 头部, PC 位于第 32 个 64-bit 槽位 (offset + 16 + 8 * 32)
                pc_offset = offset + 16 + (8 * 32)
                if pc_offset + 8 <= offset + cmdsize:
                    pc = struct.unpack_from("<Q", data, pc_offset)[0]
                    if self.entry_point == 0:
                        self.entry_point = pc

            offset += cmdsize

    def map_into_emulator(self, uc):
        """
        将所有解析出的段映射到 Unicorn 虚拟机内存中
        """
        PAGE_SIZE = 0x1000  # 4KB 对齐 (Unicorn 规范)

        print(f"\n[MachO Loader] 开始加载可执行文件: {os.path.basename(self.filepath)}")
        for seg in self.segments:
            if seg["vmsize"] == 0:
                continue
            
            # 对齐内存地址
            aligned_addr = seg["vmaddr"] & ~(PAGE_SIZE - 1)
            aligned_size = ((seg["vmaddr"] + seg["vmsize"] - aligned_addr + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
            
            print(f"  -> 映射段 {seg['name']:<10} 虚拟地址: 0x{seg['vmaddr']:09x} ~ 0x{seg['vmaddr']+seg['vmsize']:09x} (大小: {seg['vmsize']} 字节)")
            try:
                uc.mem_map(aligned_addr, aligned_size)
            except Exception:
                # 如果相邻段已由前一段映射，忽略重复映射
                pass
            
            if len(seg["data"]) > 0:
                uc.mem_write(seg["vmaddr"], seg["data"])

        print(f"[MachO Loader] 入口点 EntryPoint: 0x{self.entry_point:09x}\n")
        return self.entry_point
