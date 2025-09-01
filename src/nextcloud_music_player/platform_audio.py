"""
平台检测和平台特定的音频播放器实现
"""

import sys
import logging
import os
from typing import Optional, Protocol
from pathlib import Path

logger = logging.getLogger(__name__)

def is_ios() -> bool:
    """检测是否运行在iOS平台"""
    return sys.platform == 'ios' or 'iOS' in str(sys.platform)

def is_macos() -> bool:
    """检测是否运行在macOS平台"""
    return sys.platform == 'darwin'

def is_mobile() -> bool:
    """检测是否运行在移动平台"""
    return is_ios()

class AudioPlayerProtocol(Protocol):
    """音频播放器协议接口"""
    
    def load(self, file_path: str) -> bool:
        """加载音频文件"""
        ...
    
    def play(self) -> bool:
        """播放音频"""
        ...
    
    def pause(self) -> bool:
        """暂停播放"""
        ...
    
    def stop(self) -> bool:
        """停止播放"""
        ...
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        ...
    
    def set_volume(self, volume: float) -> bool:
        """设置音量 (0.0-1.0)"""
        ...
    
    def get_duration(self) -> float:
        """获取音频时长（秒）"""
        ...
    
    def get_position(self) -> float:
        """获取当前播放位置（秒）"""
        ...
    
    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）"""
        ...

class PygameAudioPlayer:
    """基于pygame的音频播放器（桌面平台）"""
    
    def __init__(self):
        self._pygame = None
        self._current_file = None
        self._is_paused = False
        self._volume = 0.7
        self._init_pygame()
    
    def _init_pygame(self):
        """初始化pygame"""
        try:
            import pygame
            self._pygame = pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            logger.info("pygame音频播放器初始化成功")
        except ImportError:
            logger.error("pygame未安装，无法使用pygame音频播放器")
        except Exception as e:
            logger.error(f"初始化pygame失败: {e}")
    
    def load(self, file_path: str) -> bool:
        """加载音频文件"""
        if not self._pygame:
            return False
        
        try:
            if not os.path.exists(file_path):
                logger.error(f"音频文件不存在: {file_path}")
                return False
            
            self._pygame.mixer.music.load(file_path)
            self._current_file = file_path
            logger.info(f"音频文件加载成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"加载音频文件失败: {e}")
            return False
    
    def play(self) -> bool:
        """播放音频"""
        if not self._pygame or not self._current_file:
            return False
        
        try:
            if self._is_paused:
                self._pygame.mixer.music.unpause()
                self._is_paused = False
            else:
                self._pygame.mixer.music.play()
            logger.info("开始播放音频")
            return True
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
            return False
    
    def pause(self) -> bool:
        """暂停播放"""
        if not self._pygame:
            return False
        
        try:
            self._pygame.mixer.music.pause()
            self._is_paused = True
            logger.info("暂停播放")
            return True
        except Exception as e:
            logger.error(f"暂停播放失败: {e}")
            return False
    
    def stop(self) -> bool:
        """停止播放"""
        if not self._pygame:
            return False
        
        try:
            self._pygame.mixer.music.stop()
            self._is_paused = False
            logger.info("停止播放")
            return True
        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return False
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        if not self._pygame:
            return False
        
        try:
            return self._pygame.mixer.music.get_busy() and not self._is_paused
        except:
            return False
    
    def set_volume(self, volume: float) -> bool:
        """设置音量 (0.0-1.0)"""
        if not self._pygame:
            return False
        
        try:
            self._volume = max(0.0, min(1.0, volume))
            self._pygame.mixer.music.set_volume(self._volume)
            return True
        except Exception as e:
            logger.error(f"设置音量失败: {e}")
            return False
    
    def get_duration(self) -> float:
        """获取音频时长（秒）- pygame不支持直接获取，返回-1"""
        return -1.0
    
    def get_position(self) -> float:
        """获取当前播放位置（秒）- pygame不支持直接获取，返回-1"""
        return -1.0
    
    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）- pygame不支持，返回False"""
        return False

class iOSAudioPlayer:
    """基于iOS AVFoundation的音频播放器"""
    
    def __init__(self):
        self._player = None
        self._current_file = None
        self._volume = 0.7
        self._audio_manager = None
        self._init_avfoundation()
    
    def _init_avfoundation(self):
        """初始化AVFoundation"""
        try:
            # 尝试导入iOS的AVFoundation
            from rubicon.objc import ObjCClass, objc_method
            
            # 获取AVFoundation类
            self.AVAudioPlayer = ObjCClass("AVAudioPlayer")
            self.NSURL = ObjCClass("NSURL")
            self.NSString = ObjCClass("NSString")
            self.AVAudioSession = ObjCClass("AVAudioSession")
            
            # 初始化后台音频管理器
            try:
                from .ios_background_audio import get_ios_audio_manager
                self._audio_manager = get_ios_audio_manager()
                if self._audio_manager and self._audio_manager.is_configured:
                    logger.info("iOS后台音频管理器配置成功")
                else:
                    logger.warning("iOS后台音频管理器配置失败")
            except ImportError:
                logger.warning("无法导入iOS后台音频管理器")
            
            # 配置音频会话以支持后台播放
            session = self.AVAudioSession.sharedInstance()
            
            # 设置音频会话类别为播放，支持后台播放
            try:
                # 尝试使用更完整的API
                success = session.setCategory_withOptions_error_(
                    "AVAudioSessionCategoryPlayback",
                    0,  # AVAudioSessionCategoryOptions 默认
                    None
                )
                
                if not success:
                    # 回退到简单API
                    success = session.setCategory_error_("AVAudioSessionCategoryPlayback", None)
                
                if success:
                    session.setActive_error_(True, None)
                    logger.info("iOS音频会话配置成功，支持后台播放")
                else:
                    logger.warning("设置iOS音频会话类别失败")
                    
            except Exception as e:
                logger.warning(f"配置iOS音频会话失败: {e}")
                # 最后尝试简单方法
                try:
                    session.setCategory("AVAudioSessionCategoryPlayback", error=None)
                    session.setActive(True, error=None)
                    logger.info("iOS音频会话配置成功（简单方法）")
                except:
                    logger.error("所有iOS音频会话配置方法都失败")
            
            logger.info("iOS AVFoundation音频播放器初始化成功")
            
        except ImportError as e:
            logger.error(f"无法导入AVFoundation: {e}")
        except Exception as e:
            logger.error(f"初始化iOS音频播放器失败: {e}")
    
    def load(self, file_path: str) -> bool:
        """加载音频文件"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"音频文件不存在: {file_path}")
                return False
            
            # 创建NSURL
            file_url = self.NSURL.fileURLWithPath(self.NSString.stringWithString(file_path))
            
            # 创建AVAudioPlayer
            self._player = self.AVAudioPlayer.alloc().initWithContentsOfURL(file_url, error=None)
            
            if self._player:
                self._player.prepareToPlay()
                self._player.setVolume(self._volume)
                self._current_file = file_path
                logger.info(f"iOS音频文件加载成功: {file_path}")
                return True
            else:
                logger.error(f"无法创建AVAudioPlayer: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"iOS加载音频文件失败: {e}")
            return False
    
    def play(self) -> bool:
        """播放音频"""
        try:
            # 激活音频会话
            if self._audio_manager:
                self._audio_manager.activate_session()
            
            if self._player:
                result = self._player.play()
                if result:
                    logger.info("iOS开始播放音频")
                return result
            return False
        except Exception as e:
            logger.error(f"iOS播放音频失败: {e}")
            return False
    
    def pause(self) -> bool:
        """暂停播放"""
        try:
            if self._player:
                self._player.pause()
                logger.info("iOS暂停播放")
                return True
            return False
        except Exception as e:
            logger.error(f"iOS暂停播放失败: {e}")
            return False
    
    def stop(self) -> bool:
        """停止播放"""
        try:
            if self._player:
                self._player.stop()
                logger.info("iOS停止播放")
                
                # 可选：停止播放后停用音频会话（如果不需要保持后台能力）
                # if self._audio_manager:
                #     self._audio_manager.deactivate_session()
                
                return True
            return False
        except Exception as e:
            logger.error(f"iOS停止播放失败: {e}")
            return False
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        try:
            if self._player:
                return self._player.isPlaying()
            return False
        except:
            return False
    
    def set_volume(self, volume: float) -> bool:
        """设置音量 (0.0-1.0)"""
        try:
            self._volume = max(0.0, min(1.0, volume))
            if self._player:
                self._player.setVolume(self._volume)
            return True
        except Exception as e:
            logger.error(f"iOS设置音量失败: {e}")
            return False
    
    def get_duration(self) -> float:
        """获取音频时长（秒）"""
        try:
            if self._player:
                return float(self._player.duration())
            return -1.0
        except:
            return -1.0
    
    def get_position(self) -> float:
        """获取当前播放位置（秒）"""
        try:
            if self._player:
                return float(self._player.currentTime())
            return -1.0
        except:
            return -1.0
    
    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）"""
        try:
            if self._player:
                self._player.setCurrentTime(position)
                return True
            return False
        except Exception as e:
            logger.error(f"iOS跳转位置失败: {e}")
            return False

class FallbackAudioPlayer:
    """备用音频播放器（使用系统命令）"""
    
    def __init__(self):
        self._current_file = None
        self._process = None
        self._volume = 0.7
    
    def load(self, file_path: str) -> bool:
        """加载音频文件"""
        if not os.path.exists(file_path):
            logger.error(f"音频文件不存在: {file_path}")
            return False
        
        self._current_file = file_path
        logger.info(f"备用播放器加载文件: {file_path}")
        return True
    
    def play(self) -> bool:
        """播放音频"""
        if not self._current_file:
            return False
        
        try:
            import subprocess
            import shlex
            
            # 尝试使用系统音频播放命令
            if is_macos():
                # macOS使用afplay
                cmd = f"afplay {shlex.quote(self._current_file)}"
            else:
                # 其他平台尝试常见播放器
                cmd = f"mpg123 {shlex.quote(self._current_file)}"
            
            # 在后台执行
            self._process = subprocess.Popen(cmd, shell=True)
            logger.info(f"备用播放器开始播放: {self._current_file}")
            return True
            
        except Exception as e:
            logger.error(f"备用播放器播放失败: {e}")
            return False
    
    def pause(self) -> bool:
        """暂停播放"""
        # 备用播放器暂不支持暂停
        return False
    
    def stop(self) -> bool:
        """停止播放"""
        try:
            if self._process:
                self._process.terminate()
                self._process = None
                logger.info("备用播放器停止播放")
                return True
            return False
        except Exception as e:
            logger.error(f"备用播放器停止失败: {e}")
            return False
    
    def is_playing(self) -> bool:
        """检查是否正在播放"""
        if self._process:
            return self._process.poll() is None
        return False
    
    def set_volume(self, volume: float) -> bool:
        """设置音量 (0.0-1.0)"""
        self._volume = max(0.0, min(1.0, volume))
        # 备用播放器暂不支持音量控制
        return True
    
    def get_duration(self) -> float:
        """获取音频时长（秒）"""
        return -1.0
    
    def get_position(self) -> float:
        """获取当前播放位置（秒）"""
        return -1.0
    
    def seek(self, position: float) -> bool:
        """跳转到指定位置（秒）"""
        return False

def create_audio_player() -> AudioPlayerProtocol:
    """创建适合当前平台的音频播放器"""
    
    if is_ios():
        logger.info("检测到iOS平台，创建iOS音频播放器")
        player = iOSAudioPlayer()
        
        # 验证iOS播放器是否正常工作
        if hasattr(player, 'AVAudioPlayer'):
            return player
        else:
            logger.warning("iOS音频播放器初始化失败，使用备用播放器")
            return FallbackAudioPlayer()
    
    else:
        # 桌面平台尝试使用pygame
        logger.info("检测到桌面平台，创建pygame音频播放器")
        player = PygameAudioPlayer()
        
        # 验证pygame是否可用
        if player._pygame:
            return player
        else:
            logger.warning("pygame不可用，使用备用播放器")
            return FallbackAudioPlayer()
