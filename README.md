# MiniMaclator (Reverse-Rosetta Execution Framework)

A next-generation reverse binary translation & execution framework designed to run native **ARM64 macOS (Apple Silicon)** applications on x86_64 host environments.

---

## 🎯 相比同类项目的超越与突破 (Key Breakthroughs)

针对原作者及同类项目普遍存在的 5 个关键“不支持”痛点，本项目进行了针对性的攻坚设计：

| 功能模块 | 原作者/同类项目状态 | MiniMaclator 解决方案 |
| :--- | :--- | :--- |
| **Mach-O 二进制原生装载** | 仅依赖外部 sysroot 提取 | **内置原生 `MachOLoader`**，完整解析 LC_SEGMENT_64 / LC_UNIXTHREAD / LC_MAIN，实现段内存映射与 Entrypoint 解析 |
| **沙盒应用 (Sandbox)** | ❌ 不支持 (权限不匹配直接 SIGKILL) | **Syscall 拦截伪造层**: 劫持沙盒权限探测（如 `sandbox_check`），强制 Mock 返回 0（放行状态），杜绝闪退 |
| **音频输出 (Audio/CoreAudio)** | ❌ 不支持 | **AudioBridge 模块 (`audio_bridge.py`)**: 拦截 CoreAudio / AudioQueue 调度，实时捕获 guest 内存中 PCM 音频流并桥接输出为标准 WAV 音频文件 |
| **IOKit 硬件依赖** | ❌ 大部分硬件不支持 | **虚拟硬件句柄分发**: 提供 Mock Matching Service，避免应用因找不到硬件而 abort |
| **CAMetalLayer 渲染** | ❌ 不支持 | **IOSurfaceBridge 模块 (`gpu_surface_bridge.py`)**: 实现 CAMetalLayer 上屏提交拦截，跨架构共享 1.9MB+ 显存帧缓冲与纹理数据 |

---

## 🏗️ 核心架构

```
┌────────────────────────────────────────┐
│     ARM64 macOS Mach-O Executable      │
└───────────────────┬────────────────────┘
                    │
            [Mach-O Loader]
   解析 __TEXT / __DATA / EntryPoint
                    │
                    ▼
       ┌────────────────────────┐
       │   Unicorn ARM64 CPU    │  <--- 指令执行层 (JIT/AOT 挂载点)
       └────────────┬───────────┘
                    │ SVC #0x80 中断拦截
                    ▼
       ┌────────────────────────┐
       │ Syscall Dispatch / Mock│
       ├────────────────────────┤
       │ • BSD Syscall (write...)
       │ • Sandbox 强制放行     │
       │ • IOKit 虚拟句柄 Mock   │
       │ • Audio 数据重定向     │
       └────────────────────────┘
```

---

## 🚀 快速上手与验证

### 1. 运行 Mach-O 原生二进制测试
```bash
# 生成原生 ARM64 Mach-O 测试样本
python3 tests/gen_macho.py

# 使用 MiniMaclator 直接加载并运行 Mach-O 文件
PYTHONPATH=src python3 -c "from engine import MiniMaclator; m = MiniMaclator(); m.run_macho('tests/sample_arm64.macho')"
```

**运行输出示例：**
```text
[MachO Loader] 开始加载可执行文件: sample_arm64.macho
  -> 映射段 __TEXT     虚拟地址: 0x100000000 ~ 0x100001000 (大小: 4096 字节)
[MachO Loader] 入口点 EntryPoint: 0x100000200

[MiniMaclator] 启动执行 Mach-O 入口点: 0x100000200...
[Mach-O Native Execution] Hello from parsed ARM64 Mach-O Binary!
[MiniMaclator] 拦截到 Sandbox Check (Syscall 0x200), 伪造放行返回 0
[MiniMaclator] 进程正常退出, ExitCode=0
```
