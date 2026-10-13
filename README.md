# MiniMaclator (逆向 Rosetta 转译器原型)

一个在 x86_64 宿主机上模拟执行 ARM64 macOS 原生指令的轻量转译执行框架。针对原始项目中不支持的几大短板进行了架构原型设计。

## 目录结构
- `src/engine.py`: 核心执行引擎（Unicorn CPU 模拟、Syscall 陷阱分发、Sandbox/IOKit Mock 层）
- `src/test_run.py`: ARM64 原生机器码执行与验证用例

## 核心实现
1. **指令转译层**: 将 ARM64 原生机器码映射至虚拟内存段，模拟 PC/SP 寄存器与堆栈调用。
2. **BSD/Mach Syscall 桥接**: 拦截 `SVC` 中断，把 ARM64 的 `write` (4/64)、`exit` 等调用转发到宿主内核。
3. **沙盒与硬件兼容 Mock**:
   - 拦截 `sandbox_check` 等私有调用，强制放行，避免应用因未签名或缺乏 entitlements 闪退。
   - 针对 IOKit 提供虚拟服务句柄（Mock Handle），绕过硬件检测限制。

## 运行验证
```bash
python3 src/test_run.py
```
