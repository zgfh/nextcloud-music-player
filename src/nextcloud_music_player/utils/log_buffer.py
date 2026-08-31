"""
内存日志环形缓冲与全局异常钩子

设置页"查看应用日志"从内存缓冲读取当前会话日志（iOS 真机排障用）；
未捕获异常（主线程/子线程）也统一写入日志，便于事后查看。
"""

import logging
import sys
import threading
from collections import deque

LOG_FILE_NAME = "nextcloud_music_player.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

_RING_BUFFER: deque[str] = deque(maxlen=2000)

_original_sys_hook = sys.excepthook


class RingBufferHandler(logging.Handler):
    """把格式化后的日志行写入内存环形缓冲"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _RING_BUFFER.append(self.format(record))
        except Exception:
            # 日志系统自身绝不能影响业务
            pass


def get_recent_logs(n: int = 300) -> list[str]:
    """返回内存缓冲中最近 n 条日志行"""
    if n <= 0:
        return []
    return list(_RING_BUFFER)[-n:]


def get_buffered_log_count() -> int:
    return len(_RING_BUFFER)


def clear_buffer() -> None:
    _RING_BUFFER.clear()


def set_log_level(level_name: str, config_manager=None):
    """切换全局日志级别；传入 config_manager 时同时持久化到 app.log_level"""
    level_name = level_name.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.getLogger().setLevel(level)
    if config_manager is not None:
        try:
            config_manager.set("app.log_level", level_name)
            config_manager.save_config()
        except Exception:
            pass
    logging.getLogger(__name__).info(f"日志级别已切换为 {level_name}")


def _handle_sys_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        _original_sys_hook(exc_type, exc_value, exc_tb)
        return
    logging.critical("未捕获的异常（主线程）", exc_info=(exc_type, exc_value, exc_tb))
    _original_sys_hook(exc_type, exc_value, exc_tb)


def _handle_thread_exception(args: threading.ExceptHookArgs):
    thread_name = args.thread.name if args.thread else "?"
    logging.critical(
        f"未捕获的异常（线程 {thread_name}）",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def install_exception_hooks() -> None:
    """把未捕获异常写入日志（正常输出到 stderr 的行为保持不变）"""
    sys.excepthook = _handle_sys_exception
    threading.excepthook = _handle_thread_exception
