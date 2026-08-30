"""线程安全的下载进度状态，供下载线程和 Flet 设置页共享。"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass


@dataclass
class DownloadSnapshot:
    status: str = "idle"
    filename: str = ""
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    queued: int = 0
    completed: int = 0
    failed: int = 0
    message: str = "暂无下载任务"


class DownloadProgressTracker:
    """保存当前下载与批次统计；回调可安全地从工作线程调用。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = DownloadSnapshot()
        self._started_at = 0.0
        self._generation = 0

    def enqueue(self, count: int = 1) -> None:
        if count <= 0:
            return
        with self._lock:
            if self._state.status in ("idle", "completed", "failed"):
                self._state.completed = 0
                self._state.failed = 0
            self._state.queued += count
            if self._state.status != "downloading":
                self._state.status = "queued"
                self._state.message = f"等待下载 {self._state.queued} 首"

    def start(self, filename: str) -> int:
        with self._lock:
            self._generation += 1
            if self._state.queued:
                self._state.queued -= 1
            self._state.status = "downloading"
            self._state.filename = filename
            self._state.downloaded_bytes = 0
            self._state.total_bytes = 0
            self._state.speed_bps = 0.0
            self._state.message = "正在下载"
            self._started_at = time.monotonic()
            return self._generation

    def update(
        self, downloaded_bytes: int, total_bytes: int = 0, token: int | None = None
    ) -> None:
        with self._lock:
            if token is not None and token != self._generation:
                return
            self._state.downloaded_bytes = max(0, int(downloaded_bytes))
            self._state.total_bytes = max(0, int(total_bytes))
            elapsed = max(time.monotonic() - self._started_at, 0.001)
            self._state.speed_bps = self._state.downloaded_bytes / elapsed

    def finish(
        self, success: bool, message: str = "", token: int | None = None
    ) -> None:
        with self._lock:
            if token is not None and token != self._generation:
                return
            if success:
                self._state.completed += 1
            else:
                self._state.failed += 1
            if self._state.queued:
                self._state.status = "queued"
                self._state.message = f"等待下载 {self._state.queued} 首"
            else:
                self._state.status = "completed" if success else "failed"
                self._state.message = message or ("下载完成" if success else "下载失败")
                self._state.speed_bps = 0.0

    def snapshot(self) -> dict:
        with self._lock:
            return asdict(self._state)
