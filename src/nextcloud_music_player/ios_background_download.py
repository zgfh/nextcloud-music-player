"""
iOS 原生后台下载（Background NSURLSession）

应用内下载（requests + 线程池）在应用切后台约 30 秒后被系统挂起，
beginBackgroundTask 宽限耗尽后整批下载中断。本模块通过 rubicon-objc
直接创建原生 background NSURLSession：

- 真正的传输由系统进程 nsurlsessiond 执行，应用挂起、锁屏甚至被杀
  都不影响下载；任务完成后系统会唤醒/重启应用交付结果
- 每次启动用同一 identifier 重建 session，即可接管上一进程遗留的
  任务（App 被划掉后已提交的任务继续下载，完成后经孤儿回调落库）
- taskDescription 携带 JSON（key/dest），跨进程恢复"任务 -> 歌曲"映射
- didFinishDownloadingToURL 内同步移动文件（系统约定：返回后临时文件
  即被删除）
- 传输中断时优先用 resumeData 自动断点续传一次

非 iOS 平台、rubicon 不可用或会话创建失败一律静默降级
（is_available() == False），调用方回退到 requests 下载路径。
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote, unquote

logger = logging.getLogger(__name__)

# 必须跨版本保持不变：identifier 是系统重联遗留任务的唯一凭据。
# 注意：同一 identifier 同一时刻只能属于一个进程——第二个进程创建
# 同名会话，其任务会立刻失败（NSURLErrorDomain -996）。本模块通过
# _ensure_state() 保证每进程只创建一次会话，不会触发该约束。
SESSION_IDENTIFIER = "com.daozzg.nextcloud-music-player.download"

RESUME_DATA_KEY = "NSURLSessionDownloadTaskResumeData"

# 与 requests 回退路径（timeout=120）保持一致
REQUEST_TIMEOUT = 120.0


class _DownloadState:
    """任务登记与回调分发的纯 Python 状态机。

    与 rubicon 解耦以便单元测试；原生 delegate 在系统队列线程上把
    ObjC 回调翻译成对这里的方法调用，因此所有方法都必须线程安全。
    """

    def __init__(self):
        self.lock = threading.Lock()
        # key -> {"future": (loop, fut), "on_progress": Callable | None}
        self.entries: dict = {}
        # key -> 最终文件路径。didFinishDownloadingToURL 先于
        # didCompleteWithError 送达，用它衔接两段回调
        self.deliveries: dict = {}
        # key -> 非 2xx 的 HTTP 状态（URLSession 不把状态码当错误，
        # 404/401 的响应体会正常走 didFinish，必须应用层拦截）
        self.errors: dict = {}
        # 已用 resumeData 断点续传过的 key（每个任务只自动续传一次）
        self.retried: set = set()
        # fn(key, success, final_path, error)：应用重启后遗留任务完成时
        # 的落库回调（由 activate() 注入 MusicService）
        self.orphan_callback: Optional[Callable] = None
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None

        # 原生句柄（_create_native_state 注入；测试中保持 None）
        self.session = None
        self.ns_url_class = None
        self.ns_request_class = None

    # ---------- 原生 delegate 入口（系统队列线程调用） ----------

    def task_meta(self, task) -> tuple[Optional[str], dict]:
        """解析 taskDescription JSON -> (key, 完整 meta)"""
        try:
            desc = task.taskDescription
            if desc is not None:
                desc = str(desc)
        except Exception:
            return None, {}
        if not desc:
            return None, {}
        try:
            meta = json.loads(desc)
        except (TypeError, ValueError):
            return None, {}
        key = meta.get("key") if isinstance(meta, dict) else None
        return (key if isinstance(key, str) and key else None), (meta or {})

    def handle_progress(self, key: Optional[str], written: int, total: int) -> None:
        if not key:
            return
        with self.lock:
            entry = self.entries.get(key)
            on_progress = entry.get("on_progress") if entry else None
        if on_progress is None:
            return
        try:
            on_progress(written, total)
        except Exception as e:
            logger.debug(f"下载进度回调异常 {key}: {e}")

    def handle_downloaded(
        self, key: Optional[str], meta: dict, location_path: str, http_status=None
    ) -> Optional[str]:
        """didFinishDownloadingToURL：返回前把临时文件搬到目标位置。

        非 2xx 的响应（错误页正文）删除并记录失败原因。
        """
        if key and http_status is not None and not (200 <= http_status < 300):
            with self.lock:
                self.errors[key] = f"HTTP {http_status}"
            logger.warning(f"下载响应状态异常 {key}: HTTP {http_status}，已丢弃响应体")
            try:
                Path(location_path).unlink(missing_ok=True)
            except Exception:
                pass
            return None
        dest = meta.get("dest") if meta else None
        if not (key and dest and location_path):
            return None
        try:
            dest_path = Path(dest)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(location_path), str(dest_path))
        except Exception as e:
            logger.error(f"保存下载文件失败 {key}: {e}")
            return None
        with self.lock:
            self.deliveries[key] = str(dest_path)
        return str(dest_path)

    def handle_complete(
        self, key: Optional[str], meta: dict, error, session=None
    ) -> None:
        """didCompleteWithError：以"是否拿到交付文件"判定成功。

        不直接依赖 error 的 nil 表示（rubicon 对 nil 的包装形式
        因版本而异）：didFinish 已交付文件则一律视为成功。
        """
        if not key:
            return
        with self.lock:
            final_path = self.deliveries.pop(key, None)
        if final_path:
            self.dispatch_complete(key, True, final_path, None)
            return
        if error is None:
            with self.lock:
                message = self.errors.pop(key, None) or "下载完成但文件未交付"
            logger.warning(f"下载未交付文件，判定为失败 {key}: {message}")
            self.dispatch_complete(key, False, None, message)
            return

        resume_data = _extract_resume_data(error)
        if resume_data is not None and session is not None:
            with self.lock:
                already = key in self.retried
                if not already:
                    self.retried.add(key)
            if not already:
                logger.warning(f"下载中断，尝试断点续传: {key}")
                if _resubmit_with_resume(session, resume_data, meta):
                    return

        self.dispatch_complete(key, False, None, _describe_error(error))

    # ---------- Python 侧 ----------

    def register(self, key: str, on_progress: Optional[Callable]) -> asyncio.Future:
        """登记等待者；必须在提交原生任务之前调用，防止完成回调早到"""
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        with self.lock:
            self.entries[key] = {"future": (loop, fut), "on_progress": on_progress}
        return fut

    def unregister(self, key: str) -> None:
        with self.lock:
            self.entries.pop(key, None)

    def dispatch_complete(
        self, key: str, success: bool, final_path: Optional[str], error: Optional[str]
    ) -> None:
        with self.lock:
            entry = self.entries.pop(key, None)
            orphan = self.orphan_callback
            loop = self.main_loop

        if entry is not None:
            fut_loop, fut = entry["future"]

            def _resolve():
                if not fut.done():
                    fut.set_result((success, final_path, error))

            try:
                fut_loop.call_soon_threadsafe(_resolve)
                return
            except RuntimeError:
                logger.warning(f"等待方事件循环已关闭，按遗留任务处理: {key}")

        if orphan is None:
            logger.info(f"后台下载完成（无接收方）: {key} success={success}")
            return
        self._run_orphan(orphan, key, success, final_path, error, loop)

    def _run_orphan(self, orphan, key, success, final_path, error, loop) -> None:
        # 遗留任务多来自系统后台重启，优先转回主循环执行，
        # 避免在 delegate 线程里触碰 music_library 的非线程安全写路径
        if loop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(
                    lambda: _safe_call(orphan, key, success, final_path, error)
                )
                return
            except RuntimeError:
                pass
        _safe_call(orphan, key, success, final_path, error)


def _safe_call(fn, *args) -> None:
    try:
        fn(*args)
    except Exception:
        logger.exception("后台下载收尾回调异常")


def _describe_error(error) -> str:
    try:
        return f"{error.domain}({error.code}): {error.localizedDescription()}"
    except Exception:
        return str(error)


def _http_status(response) -> Optional[int]:
    """读取 NSHTTPURLResponse 状态码；非 HTTP 响应返回 None"""
    try:
        return int(response.statusCode)
    except Exception:
        return None


def _extract_resume_data(error):
    try:
        data = error.userInfo.get(RESUME_DATA_KEY)
        return data if data is not None else None
    except Exception:
        return None


def _resubmit_with_resume(session, resume_data, meta: dict) -> bool:
    try:
        task = session.downloadTaskWithResumeData_(resume_data)
        if meta:
            task.setTaskDescription_(json.dumps(meta, ensure_ascii=False))
        task.resume()
        return True
    except Exception as e:
        logger.error(f"断点续传提交失败: {e}")
        return False


# ---------------------------------------------------------------------------
# 原生会话引导
# ---------------------------------------------------------------------------

_state: Optional[_DownloadState] = None
_state_lock = threading.Lock()
_bootstrap_failed = False
# 运行期禁用原因（如 ATS 拦截明文 HTTP）；置位后本进程一律回退 requests
_disabled_reason: Optional[str] = None


def is_available() -> bool:
    """原生后台下载是否可用（未被运行期禁用 + iOS + 会话创建成功）"""
    if _disabled_reason is not None:
        return False
    return _ensure_state() is not None


def disable(reason: str) -> None:
    """运行期禁用原生后台下载，本进程后续下载回退 requests 路径。

    用于确定性、配置级的失败（如 ATS 拦截明文 HTTP），重试不会好转。
    """
    global _disabled_reason
    if _disabled_reason is None:
        _disabled_reason = reason
        logger.warning(f"原生后台下载已禁用，回退应用内下载: {reason}")


def _ensure_state() -> Optional[_DownloadState]:
    global _state, _bootstrap_failed
    if _state is not None:
        return _state
    if _bootstrap_failed:
        return None
    with _state_lock:
        if _state is not None or _bootstrap_failed:
            return _state
        from .platform_audio import is_ios

        if not is_ios():
            _bootstrap_failed = True
            return None
        state = _create_native_state()
        if state is None:
            _bootstrap_failed = True
            return None
        _state = state
        logger.info(f"原生后台下载会话已创建: {SESSION_IDENTIFIER}")
        return _state


def _create_native_state() -> Optional[_DownloadState]:
    """创建 background NSURLSession；任何失败返回 None（调用方回退）"""
    try:
        from rubicon.objc import NSObject, ObjCClass, ObjCProtocol, objc_method
    except ImportError as e:
        logger.info(f"rubicon 不可用，跳过原生后台下载: {e}")
        return None

    state = _DownloadState()

    # 协议并非在所有运行时都注册（macOS 上 objc_getProtocol 找不到它，
    # iOS 上通常可用）。URLSession 委托按选择器分发、不校验
    # conformsToProtocol:，拿不到协议时跳过声明即可
    try:
        download_delegate = ObjCProtocol("NSURLSessionDownloadDelegate")
        delegate_protocols = [download_delegate]
    except NameError:
        delegate_protocols = []

    class _URLSessionDelegate(NSObject, protocols=delegate_protocols):
        """把 NSURLSession 回调翻译给 _DownloadState（系统队列线程）。

        注意：ObjC 委托选择器以 "URLSession"（大写 U）开头，
        Swift 的 urlSession(...) 是它的 Swift 化写法；rubicon 按
        Python 方法名生成选择器，这里必须用大写 U 命名。
        """

        @objc_method
        def URLSession_downloadTask_didWriteData_totalBytesWritten_totalBytesExpectedToWrite_(
            self,
            session,
            downloadTask,
            bytesWritten: int,
            totalBytesWritten: int,
            totalBytesExpectedToWrite: int,
        ):
            key, _meta = state.task_meta(downloadTask)
            state.handle_progress(key, totalBytesWritten, totalBytesExpectedToWrite)

        @objc_method
        def URLSession_downloadTask_didFinishDownloadingToURL_(
            self, session, downloadTask, location
        ):
            key, meta = state.task_meta(downloadTask)
            if not key:
                return
            try:
                location_path = str(location.path)
            except Exception:
                location_path = ""
            state.handle_downloaded(
                key, meta, location_path, _http_status(downloadTask.response)
            )

        @objc_method
        def URLSession_task_didCompleteWithError_(self, session, task, error):
            key, meta = state.task_meta(task)
            if not key:
                return
            state.handle_complete(key, meta, error, session=session)

        @objc_method
        def URLSessionDidFinishEventsForBackgroundURLSession_(self, session):
            logger.info("后台下载事件已全部交付")

    try:
        NSURL = ObjCClass("NSURL")
        NSMutableURLRequest = ObjCClass("NSMutableURLRequest")
        URLSession = ObjCClass("NSURLSession")
        URLSessionConfiguration = ObjCClass("NSURLSessionConfiguration")

        config = URLSessionConfiguration.backgroundSessionConfigurationWithIdentifier_(
            SESSION_IDENTIFIER
        )
        # Swift 里叫 isDiscretionary，ObjC 属性名是 discretionary
        config.discretionary = False  # 用户主动下载，立即执行，不交系统择机
        config.sessionSendsLaunchEvents = True  # 应用被杀也因任务完成被重启交付
        config.timeoutIntervalForRequest = REQUEST_TIMEOUT

        delegate = _URLSessionDelegate.alloc().init()
        session = URLSession.sessionWithConfiguration_delegate_delegateQueue_(
            config, delegate, None
        )

        state.session = session
        state.ns_url_class = NSURL
        state.ns_request_class = NSMutableURLRequest
        return state
    except Exception as e:
        logger.warning(f"创建后台 NSURLSession 失败，回退应用内下载: {e}")
        return None


async def download(
    url: str,
    headers: Optional[dict],
    dest,
    key: str,
    on_progress: Optional[Callable] = None,
) -> tuple[bool, Optional[str], Optional[str]]:
    """经后台 NSURLSession 下载一个文件，返回 (success, final_path, error)。

    提交失败（URL 非法、会话不可用等）抛异常，调用方回退 requests；
    传输失败通过返回值表达。
    """
    state = _ensure_state()
    if state is None:
        raise RuntimeError("原生后台下载不可用")

    fut = state.register(key, on_progress)
    try:
        nsurl = state.ns_url_class.URLWithString_(url)
        if not nsurl:
            raise ValueError(f"非法下载 URL: {url}")
        request = state.ns_request_class.requestWithURL_(nsurl)
        request.timeoutInterval = REQUEST_TIMEOUT
        for name, value in (headers or {}).items():
            request.setValue_forHTTPHeaderField_(str(value), str(name))
        task = state.session.downloadTaskWithRequest_(request)
        task.setTaskDescription_(
            json.dumps({"key": key, "dest": str(dest)}, ensure_ascii=False)
        )
        task.resume()
    except Exception:
        state.unregister(key)
        raise

    return await fut


def activate(music_service=None) -> bool:
    """应用启动时重建后台会话并接管遗留任务。

    iOS 会因后台下载完成而唤醒/重启应用，必须每次启动用同一
    identifier 重建 session，遗留任务的 didFinish/didComplete
    才会送达本进程（经 orphan 回调落库）。非 iOS 平台为 no-op。
    """
    state = _ensure_state()
    if state is None:
        return False
    handler = getattr(music_service, "handle_orphan_native_download", None)
    if handler is not None:
        state.orphan_callback = handler
    try:
        state.main_loop = asyncio.get_running_loop()
    except RuntimeError:
        state.main_loop = None
    logger.info(f"原生后台下载会话已就绪: {SESSION_IDENTIFIER}")
    return True


def build_webdav_url(server_url: str, file_path: str) -> Optional[str]:
    """拼装可直接交给 NSURL 的下载 URL（路径统一百分号编码）。

    file_path 是 PROPFIND href（服务端绝对路径，可能已编码）。
    server_url 非 http(s)（如 SMB 来源）返回 None，由调用方回退。
    """
    server = (server_url or "").strip().rstrip("/")
    if not server.startswith(("http://", "https://")):
        return None
    path = unquote(file_path or "")
    if not path.startswith("/"):
        path = "/" + path
    return f"{server}{quote(path, safe='/')}"
