"""
音频格式标准化

32kHz 等低采样率（MPEG-2 LSF）MP3 在部分播放链路（如 macOS 的
audioplayers/flet_audio）解码劣化，表现为声音发糊。此模块在下载
完成后用 ffmpeg 将低采样率 MP3 转码为 44.1kHz/320kbps，文件名
保持不变，播放列表/歌词逻辑不受影响。

ffmpeg 不可用（如 iOS）时静默跳过，保留原始文件。
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 低于该采样率的 MP3 视为需要转码
MIN_SAMPLE_RATE = 44100


def _probe(filepath: Path) -> Optional[dict]:
    """用 ffprobe 读取首个音频流信息"""
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate",
                "-of",
                "json",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        streams = json.loads(result.stdout).get("streams", [])
        return streams[0] if streams else None
    except Exception as e:
        logger.debug(f"ffprobe 失败: {e}")
        return None


def normalize_audio_if_needed(filepath) -> bool:
    """低采样率 MP3 转码为 44.1kHz。返回是否执行了转码。

    阻塞操作（调用 ffmpeg），异步上下文请用 asyncio.to_thread 包装。
    """
    filepath = Path(filepath)
    if not filepath.exists():
        return False

    if not (shutil.which("ffprobe") and shutil.which("ffmpeg")):
        logger.debug("ffmpeg/ffprobe 不可用，跳过音频标准化")
        return False

    stream = _probe(filepath)
    if not stream:
        return False

    codec = stream.get("codec_name", "")
    try:
        sample_rate = int(stream.get("sample_rate", 0))
    except (TypeError, ValueError):
        return False

    if codec != "mp3" or sample_rate >= MIN_SAMPLE_RATE:
        return False

    import subprocess

    tmp_path = filepath.with_name(filepath.stem + ".norm.tmp.mp3")
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(filepath),
                "-ar",
                str(MIN_SAMPLE_RATE),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "320k",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0 or not tmp_path.exists():
            logger.error(f"音频转码失败: {result.stderr[-300:]}")
            tmp_path.unlink(missing_ok=True)
            return False

        os.replace(tmp_path, filepath)
        logger.info(
            f"音频已标准化 {sample_rate}Hz -> {MIN_SAMPLE_RATE}Hz: {filepath.name}"
        )
        return True
    except Exception as e:
        logger.error(f"音频转码异常: {e}")
        tmp_path.unlink(missing_ok=True)
        return False


async def normalize_audio_async(filepath) -> bool:
    """normalize_audio_if_needed 的异步包装（线程池执行，不阻塞事件循环）"""
    return await asyncio.to_thread(normalize_audio_if_needed, filepath)
