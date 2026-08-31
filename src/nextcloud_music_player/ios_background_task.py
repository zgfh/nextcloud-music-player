"""
iOS 后台执行宽限（Background Task）

iOS 应用退到后台后几秒内即被挂起。begin_background_task() 通过
UIApplication.beginBackgroundTask 申请约 30 秒的宽限时间，让正在
进行的下载/IO 有机会完成；批次结束或宽限耗尽后调用 end_background_task。

非 iOS 平台全部为 no-op；rubicon 不可用或调用失败时静默降级，
绝不能影响业务流程。
"""

import logging

logger = logging.getLogger(__name__)

# name -> UIKit 后台任务标识（UIBackgroundTaskIdentifier）
_bg_tasks: dict = {}


def _ui_application():
    try:
        from rubicon.objc import ObjCClass

        UIApplication = ObjCClass("UIApplication")
        return UIApplication.sharedApplication()
    except Exception as e:
        logger.debug(f"获取 UIApplication 失败: {e}")
        return None


def begin_background_task(name: str = "background-task"):
    """申请 iOS 后台执行宽限；成功返回 name 作为 token，失败返回 None"""
    from .platform_audio import is_ios

    if not is_ios():
        return None

    app = _ui_application()
    if app is None:
        return None

    try:
        from rubicon.objc import Block
    except ImportError:
        return None

    # 过期回调必须结束对应任务，但任务标识在调用之后才产生，用持有器带出
    holder = {}

    def _on_expired():
        logger.warning(f"iOS 后台宽限时间已耗尽: {name}")
        task = holder.get("task")
        if task is not None:
            _end_task(app, task)

    try:
        handler = Block(_on_expired)
        token = app.beginBackgroundTaskWithExpirationHandler_(handler)
    except Exception as e:
        logger.debug(f"申请后台宽限失败: {e}")
        return None

    if token is None:
        return None

    holder["task"] = token
    _bg_tasks[name] = token
    logger.info(f"已申请 iOS 后台宽限时间: {name}")
    return name


def end_background_task(token):
    """结束后台宽限（幂等；token 为 None 或已结束时直接返回）"""
    if not token:
        return
    task = _bg_tasks.pop(token, None)
    if task is None:
        return
    app = _ui_application()
    if app is not None:
        _end_task(app, task)


def _end_task(app, task):
    try:
        app.endBackgroundTask_(task)
        logger.info("已结束 iOS 后台宽限任务")
    except Exception as e:
        logger.debug(f"结束后台宽限任务失败: {e}")
