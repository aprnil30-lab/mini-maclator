"""
CoreAudio Bridge & PCM Audio Hook
实现对 macOS ARM64 CoreAudio / HAL 调用的用户态拦截与桥接:
- 拦截 AudioOutputUnitStart / AudioUnitRender / AudioQueue 相关调用
- 解析 guest 内存中的 PCM 音频缓冲区 (AudioBufferList)
- 转发至宿主机虚拟声卡或本地音频流保存/播放
"""
import struct
import wave
import os

class AudioBridge:
    def __init__(self, output_wav="/tmp/maclator_output.wav"):
        self.output_wav = output_wav
        self.audio_frames = bytearray()
        self.sample_rate = 44100
        self.channels = 2
        self.sample_width = 2 # 16-bit PCM

    def handle_audio_stream(self, uc, buf_addr, buf_size, sample_rate=44100, channels=2):
        """
        从模拟器内存中提取 PCM 音频流
        """
        try:
            pcm_data = uc.mem_read(buf_addr, buf_size)
            self.audio_frames.extend(pcm_data)
            print(f"[AudioBridge] 捕获 CoreAudio PCM 数据帧: 地址 0x{buf_addr:x}, 大小 {buf_size} 字节, 采样率 {sample_rate}Hz")
            self.flush_to_file()
            return 0 # kAudioHardwareNoError
        except Exception as e:
            print(f"[AudioBridge] 提取音频数据失败: {e}")
            return -1

    def flush_to_file(self):
        """
        实时将捕获到的音频帧写入 WAV 文件
        """
        try:
            with wave.open(self.output_wav, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.sample_width)
                wf.setframerate(self.sample_rate)
                wf.writeframes(bytes(self.audio_frames))
        except Exception:
            pass
