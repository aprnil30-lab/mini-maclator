"""
IOSurface & CAMetalLayer 渲染桥接器
实现跨架构 Metal 纹理共享:
- 拦截 CAMetalLayer 的 nextDrawable 与 presentDrawable
- 模拟 IOSurface 跨进程共享内存对象
- 提取渲染帧并转换为宿主视口可读取的 RGBA 帧缓冲
"""
import struct

class IOSurfaceBridge:
    def __init__(self):
        self.surfaces = {}
        self.next_surface_id = 1

    def create_surface(self, width, height, pixel_format="BGRA8"):
        """
        模拟 IOSurfaceCreate: 分配共享纹理内存
        """
        surface_id = self.next_surface_id
        self.next_surface_id += 1
        bytes_per_row = width * 4
        total_bytes = bytes_per_row * height
        
        self.surfaces[surface_id] = {
            "id": surface_id,
            "width": width,
            "height": height,
            "bytes_per_row": bytes_per_row,
            "total_bytes": total_bytes,
            "buffer": bytearray(total_bytes)
        }
        print(f"[IOSurfaceBridge] 创建共享显存表面 SurfaceID={surface_id} ({width}x{height}, 格式: {pixel_format}, 大小: {total_bytes} 字节)")
        return surface_id

    def present_drawable(self, uc, surface_id, frame_buf_addr):
        """
        拦截 CAMetalLayer present: 将 guest 渲染出的 Metal 纹理数据同步到共享表面
        """
        if surface_id not in self.surfaces:
            print(f"[IOSurfaceBridge] 警告: 未知 SurfaceID={surface_id}")
            return -1

        surface = self.surfaces[surface_id]
        try:
            frame_data = uc.mem_read(frame_buf_addr, surface["total_bytes"])
            surface["buffer"][:] = frame_data
            print(f"[IOSurfaceBridge] 收到 CAMetalLayer 上屏提交: SurfaceID={surface_id}, 成功桥接 {len(frame_data)} 字节显存纹理")
            return 0
        except Exception as e:
            print(f"[IOSurfaceBridge] 读取显存帧失败: {e}")
            return -1
