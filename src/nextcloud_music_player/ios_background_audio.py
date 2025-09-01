"""
iOS后台音频播放支持
处理iOS应用的后台播放权限和音频会话配置
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class iOSBackgroundAudioManager:
    """iOS后台音频管理器"""
    
    def __init__(self):
        self.audio_session = None
        self.is_configured = False
        self._init_audio_session()
    
    def _init_audio_session(self):
        """初始化iOS音频会话"""
        try:
            from rubicon.objc import ObjCClass
            
            # 获取AVAudioSession
            AVAudioSession = ObjCClass("AVAudioSession")
            self.audio_session = AVAudioSession.sharedInstance()
            
            # 配置音频会话
            self._configure_background_audio()
            
            logger.info("iOS音频会话初始化成功")
            
        except ImportError:
            logger.warning("rubicon.objc不可用，无法配置iOS音频会话")
        except Exception as e:
            logger.error(f"初始化iOS音频会话失败: {e}")
    
    def _configure_background_audio(self):
        """配置后台音频播放"""
        if not self.audio_session:
            return False
        
        try:
            # 设置音频会话类别为播放模式，支持后台播放
            # AVAudioSessionCategoryPlayback 是专门用于后台音频播放的类别
            category_success = self.audio_session.setCategory_withOptions_error_(
                "AVAudioSessionCategoryPlayback",  # 播放类别
                0,  # 选项（0 = 默认）
                None  # 错误指针
            )
            
            if not category_success:
                # 尝试旧的API
                category_success = self.audio_session.setCategory_error_(
                    "AVAudioSessionCategoryPlayback",
                    None
                )
            
            if category_success:
                # 激活音频会话
                active_success = self.audio_session.setActive_error_(True, None)
                if active_success:
                    self.is_configured = True
                    logger.info("iOS后台音频播放配置成功")
                    return True
                else:
                    logger.error("激活iOS音频会话失败")
                    return False
            else:
                logger.error("设置iOS音频会话类别失败")
                return False
                
        except Exception as e:
            logger.error(f"配置iOS后台音频失败: {e}")
            # 尝试备用方法
            try:
                self.audio_session.setCategory("AVAudioSessionCategoryPlayback", error=None)
                self.audio_session.setActive(True, error=None)
                self.is_configured = True
                logger.info("iOS后台音频播放配置成功（备用方法）")
                return True
            except Exception as backup_e:
                logger.error(f"备用配置方法也失败: {backup_e}")
                return False
    
    def activate_session(self):
        """激活音频会话（在开始播放前调用）"""
        if not self.audio_session:
            return False
        
        try:
            self.audio_session.setActive(True, error=None)
            logger.info("iOS音频会话已激活")
            return True
        except Exception as e:
            logger.error(f"激活iOS音频会话失败: {e}")
            return False
    
    def deactivate_session(self):
        """停用音频会话（在停止播放后调用）"""
        if not self.audio_session:
            return False
        
        try:
            self.audio_session.setActive(False, error=None)
            logger.info("iOS音频会话已停用")
            return True
        except Exception as e:
            logger.error(f"停用iOS音频会话失败: {e}")
            return False
    
    def handle_interruption(self, notification):
        """处理音频中断（如来电、其他应用播放等）"""
        try:
            # 这里可以添加处理音频中断的逻辑
            # 例如暂停播放、记录中断状态等
            logger.info("处理iOS音频中断")
        except Exception as e:
            logger.error(f"处理iOS音频中断失败: {e}")

# 全局实例
_ios_audio_manager: Optional[iOSBackgroundAudioManager] = None

def get_ios_audio_manager() -> Optional[iOSBackgroundAudioManager]:
    """获取iOS音频管理器实例"""
    global _ios_audio_manager
    
    if _ios_audio_manager is None:
        try:
            from .platform_audio import is_ios
            if is_ios():
                _ios_audio_manager = iOSBackgroundAudioManager()
            else:
                logger.info("非iOS平台，跳过iOS音频管理器初始化")
        except Exception as e:
            logger.error(f"创建iOS音频管理器失败: {e}")
    
    return _ios_audio_manager

def configure_ios_background_audio():
    """配置iOS后台音频播放"""
    manager = get_ios_audio_manager()
    if manager:
        return manager.is_configured
    return False

def activate_ios_audio_session():
    """激活iOS音频会话"""
    manager = get_ios_audio_manager()
    if manager:
        return manager.activate_session()
    return False

def deactivate_ios_audio_session():
    """停用iOS音频会话"""
    manager = get_ios_audio_manager()
    if manager:
        return manager.deactivate_session()
    return False
