"""
NextCloud client for accessing and downloading music files.
"""

import requests
from requests.auth import HTTPBasicAuth
import asyncio
import concurrent.futures
import logging
from pathlib import Path
import tempfile
import os
import shutil
from urllib.parse import urljoin, quote
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import hashlib
import traceback

logger = logging.getLogger(__name__)


class NextCloudClient:
    """Client for interacting with NextCloud WebDAV API."""
    
    def __init__(self, server_url: str, username: str, password: str):
        """Initialize the NextCloud client."""
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.webdav_url = f"{self.server_url}/remote.php/dav/files/{username}/"
        
        # 使用配置管理器获取合适的目录
        from .config_manager import ConfigManager
        config_manager = ConfigManager()
        
        # 临时目录用于下载中的文件
        self.temp_dir = config_manager.get_temp_directory()
        self.temp_dir.mkdir(exist_ok=True)
        
        # 缓存目录用于已下载的音乐文件
        self.cache_dir = config_manager.get_cache_directory()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 元数据缓存
        self.metadata_cache = {}
    
    async def test_connection(self) -> bool:
        """Test the connection to NextCloud using requests library."""
        logger.info(f"🔍 Testing connection to: {self.server_url}")
        
        def _sync_test_connection():
            """同步连接测试函数"""
            try:
                # 1. 测试基本网络连接
                logger.info("📡 Step 1: Testing basic network connectivity...")
                try:
                    response = requests.head(self.server_url, timeout=10)
                    logger.info(f"✅ Server reachable: HTTP {response.status_code}")
                except requests.exceptions.ConnectTimeout:
                    logger.error("❌ Connection timeout")
                    return False
                except requests.exceptions.ConnectionError as e:
                    logger.error(f"❌ Network connection failed: {e}")
                    return False
                except Exception as e:
                    logger.error(f"❌ Network error: {e}")
                    return False
                
                # 2. 测试WebDAV认证
                logger.info("🔐 Step 2: Testing WebDAV authentication...")
                try:
                    auth = HTTPBasicAuth(self.username, self.password)
                    response = requests.request(
                        "PROPFIND",
                        self.webdav_url,
                        auth=auth,
                        headers={"Depth": "0"},
                        timeout=10
                    )
                    
                    if response.status_code in [200, 207]:
                        logger.info(f"✅ WebDAV authentication successful: HTTP {response.status_code}")
                        return True
                    elif response.status_code == 401:
                        logger.error("❌ Authentication failed: Invalid credentials")
                        return False
                    elif response.status_code == 404:
                        logger.error("❌ WebDAV endpoint not found")
                        return False
                    else:
                        logger.error(f"❌ WebDAV failed: HTTP {response.status_code}")
                        return False
                        
                except requests.exceptions.ConnectTimeout:
                    logger.error("❌ WebDAV connection timeout")
                    return False
                except requests.exceptions.ConnectionError as e:
                    logger.error(f"❌ WebDAV connection error: {e}")
                    return False
                except Exception as e:
                    logger.error(f"❌ WebDAV error: {e}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Connection test failed: {e}")
                return False
        
        # 在线程池中运行同步函数
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_test_connection)
            return result
    
    async def list_music_files(self, folder_path: str = "") -> List[Dict]:
        """List all music files in the specified folder with enhanced compatibility and logging."""
        music_extensions = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma'}
        
        logger.info(f"🔍 [LIST] 开始列出音乐文件，文件夹: '{folder_path}'")
        logger.info(f"🎵 [LIST] 支持的音乐格式: {list(music_extensions)}")
        
        # 首先尝试使用增强的sync_files方法
        try:
            logger.info(f"📥 [LIST] 尝试使用sync_files方法...")
            result = await self.sync_files(folder_path, music_extensions)
            if result.get('error'):
                logger.error(f"❌ [LIST] sync_files出错: {result['error']}")
                if result.get('debug'):
                    debug = result['debug']
                    logger.debug(f"🔍 [LIST] 调试信息:")
                    logger.debug(f"    - 请求URL: {debug.get('request_url')}")
                    logger.debug(f"    - 响应状态: {debug.get('response_status')}")
                    logger.debug(f"    - 发现项目总数: {debug.get('total_items_found', 0)}")
                    logger.debug(f"    - 发现文件数: {debug.get('files_found', 0)}")
                    logger.debug(f"    - 发现音乐文件数: {debug.get('music_files_found', 0)}")
            else:
                files = result.get('files', [])
                logger.info(f"✅ [LIST] sync_files成功，找到 {len(files)} 个音乐文件")
                return files
        except Exception as e:
            logger.error(f"❌ [LIST] sync_files异常: {e}")
        
        # 如果sync_files失败，尝试备用方法
        logger.info(f"🔄 [LIST] 尝试备用文件列表方法...")
        methods = [
            self._list_files_webdav,
            self._list_files_ocs_api,
            self._list_files_simple_webdav
        ]
        
        for i, method in enumerate(methods, 1):
            try:
                logger.info(f"🔧 [LIST] 尝试方法 {i}/{len(methods)}: {method.__name__}")
                files = await method(folder_path, music_extensions)
                if files:
                    logger.info(f"✅ [LIST] 方法 {method.__name__} 成功，找到 {len(files)} 个文件")
                    return files
                else:
                    logger.info(f"ℹ️ [LIST] 方法 {method.__name__} 返回空列表")
            except Exception as e:
                logger.error(f"❌ [LIST] 方法 {method.__name__} 失败: {e}")
                continue
        
        logger.warning(f"⚠️ [LIST] 所有方法都失败，返回空列表")
        return []
    
    async def _list_files_webdav(self, folder_path: str, music_extensions: set) -> List[Dict]:
        """Standard WebDAV file listing using requests."""
        
        def _sync_list_files():
            music_files = []
            
            url = urljoin(self.webdav_url, quote(folder_path)) if folder_path else self.webdav_url
            
            propfind_body = '''<?xml version="1.0"?>
            <d:propfind xmlns:d="DAV:">
                <d:prop>
                    <d:displayname/>
                    <d:getcontentlength/>
                    <d:getcontenttype/>
                    <d:resourcetype/>
                    <d:getlastmodified/>
                    <d:getetag/>
                </d:prop>
            </d:propfind>'''
            
            try:
                auth = HTTPBasicAuth(self.username, self.password)
                response = requests.request(
                    method="PROPFIND",
                    url=url,
                    auth=auth,
                    headers={
                        "Depth": "infinity",
                        "Content-Type": "application/xml"
                    },
                    data=propfind_body,
                    timeout=60
                )
                
                if response.status_code not in [200, 207]:
                    raise Exception(f"WebDAV PROPFIND failed with status {response.status_code}")
                
                # Parse XML response
                root = ET.fromstring(response.text)
                
                for response_elem in root.findall('.//{DAV:}response'):
                    href_elem = response_elem.find('.//{DAV:}href')
                    displayname_elem = response_elem.find('.//{DAV:}displayname')
                    resourcetype_elem = response_elem.find('.//{DAV:}resourcetype')
                    size_elem = response_elem.find('.//{DAV:}getcontentlength')
                    modified_elem = response_elem.find('.//{DAV:}getlastmodified')
                    
                    if href_elem is not None and displayname_elem is not None:
                        file_path = href_elem.text
                        file_name = displayname_elem.text
                        
                        # Check if it's a file (not directory)
                        if resourcetype_elem is None or len(resourcetype_elem) == 0:
                            # Check if it's a music file
                            file_ext = Path(file_name.lower()).suffix
                            if file_ext in music_extensions:
                                music_files.append({
                                    'name': file_name,
                                    'path': file_path,
                                    'size': size_elem.text if size_elem is not None else '0',
                                    'modified': modified_elem.text if modified_elem is not None else '',
                                    'type': 'file'
                                })
                
                return music_files
                
            except Exception as e:
                logger.error(f"WebDAV file listing failed: {e}")
                return []
        
        # 在线程池中运行同步函数
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_list_files)
    async def _list_files_ocs_api(self, folder_path: str, music_extensions: set) -> List[Dict]:
        """OCS API file listing (fallback method)."""
        # OCS API方法比较复杂，作为备用方案，这里返回空列表
        logger.debug("OCS API method not fully implemented, using WebDAV instead")
        return []

    async def _list_files_simple_webdav(self, folder_path: str, music_extensions: set) -> List[Dict]:
        """Simplified WebDAV listing using requests."""
        
        def _sync_simple_list():
            music_files = []
            
            try:
                url = urljoin(self.webdav_url, quote(folder_path)) if folder_path else self.webdav_url
                
                # 使用简化的PROPFIND - 只获取基本信息
                propfind_body = '''<?xml version="1.0"?>
                <d:propfind xmlns:d="DAV:">
                    <d:prop>
                        <d:displayname/>
                        <d:getcontentlength/>
                        <d:resourcetype/>
                    </d:prop>
                </d:propfind>'''
                
                auth = HTTPBasicAuth(self.username, self.password)
                response = requests.request(
                    method="PROPFIND",
                    url=url,
                    auth=auth,
                    headers={
                        "Depth": "1",  # 只列出当前目录，不递归
                        "Content-Type": "application/xml"
                    },
                    data=propfind_body,
                    timeout=30
                )
                
                if response.status_code not in [200, 207]:
                    logger.error(f"Simple WebDAV PROPFIND failed with status {response.status_code}")
                    return []
                
                # 解析XML响应
                root = ET.fromstring(response.text)
                
                for response_elem in root.findall('.//{DAV:}response'):
                    href_elem = response_elem.find('.//{DAV:}href')
                    displayname_elem = response_elem.find('.//{DAV:}displayname')
                    resourcetype_elem = response_elem.find('.//{DAV:}resourcetype')
                    size_elem = response_elem.find('.//{DAV:}getcontentlength')
                    
                    if href_elem is not None and displayname_elem is not None:
                        file_name = displayname_elem.text
                        file_path = href_elem.text
                        
                        # 跳过目录
                        if resourcetype_elem is not None and len(resourcetype_elem) > 0:
                            continue
                        
                        # 检查是否是音乐文件
                        if file_name:
                            file_ext = Path(file_name.lower()).suffix
                            if file_ext in music_extensions:
                                music_files.append({
                                    'name': file_name,
                                    'path': file_path,
                                    'size': size_elem.text if size_elem is not None else '0',
                                    'type': 'file'
                                })
                
                return music_files
                
            except Exception as e:
                logger.error(f"Simple WebDAV file listing failed: {e}")
                return []
        
        # 在线程池中运行同步函数
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_simple_list)
            return result

    async def sync_files(self, folder_path: str = "", target_extensions: set = None) -> Dict:
        """同步NextCloud中的音乐文件，带详细日志."""
        if target_extensions is None:
            target_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.ogg'}
        
        def _sync_files():
            debug_info = {
                'request_url': '',
                'response_status': 0,
                'total_items_found': 0,
                'directories_found': 0,
                'files_found': 0,
                'music_files_found': 0,
                'all_files': [],
                'target_extensions': list(target_extensions),
                'folder_path': folder_path
            }
            
            try:
                url = f"{self.server_url}/remote.php/dav/files/{self.username}/{folder_path}".rstrip('/')
                debug_info['request_url'] = url
                auth = HTTPBasicAuth(self.username, self.password)
                
                logger.info(f"🔍 [SYNC] 开始同步文件夹: {folder_path}")
                logger.debug(f"🔗 [SYNC] 请求URL: {url}")
                logger.debug(f"🎵 [SYNC] 目标音乐格式: {list(target_extensions)}")
                
                propfind_body = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:">
    <d:prop>
        <d:displayname/>
        <d:getcontentlength/>
        <d:getlastmodified/>
        <d:getetag/>
        <d:resourcetype/>
    </d:prop>
</d:propfind>"""
                
                response = requests.request(
                    method="PROPFIND",
                    url=url,
                    auth=auth,
                    headers={
                        "Depth": "1",
                        "Content-Type": "application/xml"
                    },
                    data=propfind_body,
                    timeout=30
                )
                
                debug_info['response_status'] = response.status_code
                logger.debug(f"📡 [SYNC] 服务器响应状态: {response.status_code}")
                
                if response.status_code not in [200, 207]:
                    error_msg = f"PROPFIND failed with status {response.status_code}"
                    logger.error(f"❌ [SYNC] {error_msg}")
                    logger.debug(f"📄 [SYNC] 响应内容: {response.text[:500]}")
                    return {'files': [], 'error': error_msg, 'debug': debug_info}
                
                # 解析XML响应
                logger.debug(f"📄 [SYNC] 解析XML响应...")
                root = ET.fromstring(response.text)
                music_files = []
                
                for response_elem in root.findall('.//{DAV:}response'):
                    debug_info['total_items_found'] += 1
                    
                    href_elem = response_elem.find('.//{DAV:}href')
                    displayname_elem = response_elem.find('.//{DAV:}displayname')
                    resourcetype_elem = response_elem.find('.//{DAV:}resourcetype')
                    size_elem = response_elem.find('.//{DAV:}getcontentlength')
                    modified_elem = response_elem.find('.//{DAV:}getlastmodified')
                    etag_elem = response_elem.find('.//{DAV:}getetag')
                    
                    if href_elem is not None and displayname_elem is not None:
                        file_path = href_elem.text
                        file_name = displayname_elem.text
                        
                        # 记录所有发现的项目
                        item_info = {
                            'name': file_name,
                            'path': file_path,
                            'is_directory': False,
                            'is_music': False
                        }
                        
                        # 检查是否是目录
                        if resourcetype_elem is not None and resourcetype_elem.find('.//{DAV:}collection') is not None:
                            debug_info['directories_found'] += 1
                            item_info['is_directory'] = True
                            logger.debug(f"📁 [SYNC] 发现目录: {file_name}")
                            debug_info['all_files'].append(item_info)
                            continue
                        
                        # 这是文件
                        debug_info['files_found'] += 1
                        logger.debug(f"📄 [SYNC] 发现文件: {file_name}")
                        
                        # 检查文件扩展名
                        file_ext = ""
                        if file_name and '.' in file_name:
                            file_ext = '.' + file_name.split('.')[-1].lower()
                        
                        logger.debug(f"🔍 [SYNC] 文件扩展名: '{file_ext}'")
                        logger.debug(f"🎯 [SYNC] 是否匹配音乐格式: {file_ext in target_extensions}")
                        
                        # 检查是否是音乐文件
                        if file_name and any(file_name.lower().endswith(ext) for ext in target_extensions):
                            debug_info['music_files_found'] += 1
                            item_info['is_music'] = True
                            
                            music_file = {
                                'name': file_name,
                                'path': file_path,
                                'size': int(size_elem.text) if size_elem is not None and size_elem.text else 0,
                                'modified': modified_elem.text if modified_elem is not None else '',
                                'etag': etag_elem.text if etag_elem is not None else ''
                            }
                            music_files.append(music_file)
                            logger.debug(f"🎵 [SYNC] 添加音乐文件: {file_name} (大小: {music_file['size']} bytes)")
                        
                        debug_info['all_files'].append(item_info)
                
                # 打印总结信息
                logger.info(f"📊 [SYNC] 同步完成总结:")
                logger.info(f"   - 总项目数: {debug_info['total_items_found']}")
                logger.info(f"   - 目录数: {debug_info['directories_found']}")
                logger.info(f"   - 文件数: {debug_info['files_found']}")
                logger.info(f"   - 音乐文件数: {debug_info['music_files_found']}")
                
                if debug_info['music_files_found'] == 0:
                    logger.warning(f"⚠️ [SYNC] 未找到音乐文件！")
                    logger.warning(f"   检查要点:")
                    logger.warning(f"   1. 文件夹路径是否正确: '{folder_path}'")
                    logger.warning(f"   2. 支持的音乐格式: {list(target_extensions)}")
                    logger.debug(f"   3. 发现的所有文件:")
                    for item in debug_info['all_files']:
                        if not item['is_directory']:
                            logger.debug(f"      - {item['name']}")
                
                return {'files': music_files, 'error': None, 'debug': debug_info}
                
            except Exception as e:
                error_msg = f"同步异常: {str(e)}"
                logger.error(f"❌ [SYNC] {error_msg}")
                return {'files': [], 'error': error_msg, 'debug': debug_info}
        
        # 在线程池中运行同步函数
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_files)
            return result
    
    async def download_file(self, file_path: str, file_name: str,local_path: str=None) -> str:
        """Download a file from NextCloud with smart caching and multiple methods."""
        logger.info(f"📥 [NC_DOWNLOAD] download_file被调用: {file_path} -> {file_name}")
        
        try:
            # 生成缓存文件名（基于文件路径的hash）
            #file_hash = hashlib.md5(file_path.encode()).hexdigest()
            file_ext = Path(file_name).suffix
            #cached_filename = f"{file_hash}{file_ext}"
            #cached_filename=file_name
            cached_path = self.cache_dir / file_name
            if local_path:
                cached_path = Path(local_path)
            
            logger.debug(f"💾 [NC_DOWNLOAD] 缓存路径: {cached_path}")
            
            # 如果缓存文件存在且较新，直接返回
            if cached_path.exists():
                logger.info(f"✅ [NC_DOWNLOAD] 使用缓存文件: {cached_path}")
                return str(cached_path)
            
            # 尝试不同的下载方法
            download_methods = [
                self._download_webdav,
                self._download_direct_url,
                self._download_shared_link
            ]
            
            logger.info(f"🔄 [NC_DOWNLOAD] 尝试 {len(download_methods)} 种下载方法")
            
            for i, method in enumerate(download_methods):
                try:
                    logger.debug(f"🌐 [NC_DOWNLOAD] 方法 {i+1}: {method.__name__}")
                    content = await method(file_path, file_name)
                    if content:
                        logger.info(f"✅ [NC_DOWNLOAD] 方法 {method.__name__} 成功，内容大小: {len(content)} bytes")
                        
                        # 保存到缓存目录
                        cached_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(cached_path, 'wb') as f:
                            f.write(content)
                        
                        logger.debug(f"💾 [NC_DOWNLOAD] 文件已保存到缓存: {cached_path}")
                      
                        logger.info(f"✅ [NC_DOWNLOAD] 使用 {method.__name__} 成功下载 {file_name}")
                        return str(cached_path)
                except Exception as e:
                    logger.error(f"❌ [NC_DOWNLOAD] 方法 {method.__name__} 失败: {e}")
                    continue
            
            raise Exception("All download methods failed")
                    
        except Exception as e:
            logger.error(f"❌ [NC_DOWNLOAD] 下载文件失败 {file_name}: {e}")
            logger.debug(f"🔍 [NC_DOWNLOAD] 异常堆栈:\n{traceback.format_exc()}")
            raise
    
    async def _download_webdav(self, file_path: str, file_name: str) -> bytes:
        """Standard WebDAV download using requests."""
        logger.debug(f"🌐 [WEBDAV] _download_webdav开始: {file_path}")
        
        def _sync_download():
            try:
                download_url = f"{self.server_url}{file_path}"
                logger.debug(f"🔗 [WEBDAV] 下载URL: {download_url}")
                
                auth = HTTPBasicAuth(self.username, self.password)
                logger.debug(f"🔐 [WEBDAV] 使用认证: {self.username}")
                
                logger.debug(f"📡 [WEBDAV] 发送GET请求...")
                response = requests.get(
                    download_url,
                    auth=auth,
                    timeout=120
                )
                
                logger.debug(f"📊 [WEBDAV] 响应状态: {response.status_code}")
                logger.debug(f"📏 [WEBDAV] 内容长度: {len(response.content) if response.content else 0} bytes")
                
                if response.status_code == 200:
                    logger.debug(f"✅ [WEBDAV] 下载成功")
                    return response.content
                else:
                    error_msg = f"WebDAV download failed with status {response.status_code}"
                    logger.error(f"❌ [WEBDAV] {error_msg}")
                    logger.debug(f"🔍 [WEBDAV] 响应内容: {response.text[:500]}")
                    raise Exception(error_msg)
                    
            except Exception as e:
                logger.error(f"❌ [WEBDAV] 下载异常: {type(e).__name__}: {e}")
                raise
        
        # 在线程池中运行同步函数
        logger.debug(f"🧵 [WEBDAV] 在线程池中执行下载")
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_download)
            logger.debug(f"✅ [WEBDAV] 线程池执行完成，数据大小: {len(result)} bytes")
            return result

    async def _download_direct_url(self, file_path: str, file_name: str) -> bytes:
        """Direct URL download (fallback method)."""
        # 简化为使用WebDAV方法
        return await self._download_webdav(file_path, file_name)

    async def _download_shared_link(self, file_path: str, file_name: str) -> bytes:
        """Download via shared link (fallback method)."""
        # 简化为使用WebDAV方法
        return await self._download_webdav(file_path, file_name)

    async def get_file_info(self, file_path: str) -> Optional[Dict]:
        """获取文件详细信息使用requests."""
        
        def _sync_get_info():
            try:
                url = f"{self.server_url}{file_path}"
                auth = HTTPBasicAuth(self.username, self.password)
                
                propfind_body = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:">
    <d:prop>
        <d:displayname/>
        <d:getcontentlength/>
        <d:getcontenttype/>
        <d:getlastmodified/>
        <d:getetag/>
    </d:prop>
</d:propfind>"""
                
                response = requests.request(
                    method="PROPFIND",
                    url=url,
                    auth=auth,
                    headers={
                        "Depth": "0",
                        "Content-Type": "application/xml"
                    },
                    data=propfind_body,
                    timeout=30
                )
                
                if response.status_code in [200, 207]:
                    root = ET.fromstring(response.text)
                    response_elem = root.find('.//{DAV:}response')
                    
                    if response_elem is not None:
                        return {
                            'size': response_elem.findtext('.//{DAV:}getcontentlength'),
                            'modified': response_elem.findtext('.//{DAV:}getlastmodified'),
                            'etag': response_elem.findtext('.//{DAV:}getetag'),
                            'content_type': response_elem.findtext('.//{DAV:}getcontenttype')
                        }
                
                return None
                
            except Exception as e:
                logger.error(f"Error getting file info for {file_path}: {e}")
                return None
        
        # 在线程池中运行同步函数
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_get_info)
            return result
    
    async def diagnose_connection(self) -> Dict[str, any]:
        """Simplified connection diagnosis using requests library."""
        diagnosis = {
            'server_reachable': False,
            'webdav_supported': False,
            'auth_valid': False,
            'ssl_valid': False,
            'server_info': {},
            'errors': []
        }
        
        def _sync_diagnose():
            """同步诊断函数"""
            logger.info(f"🔍 Starting connection diagnosis for: {self.server_url}")
            
            try:
                # 1. 基本服务器可达性测试
                logger.info("📡 Testing server reachability...")
                try:
                    response = requests.head(self.server_url, timeout=10)
                    diagnosis['server_reachable'] = True
                    logger.info(f"✅ Server reachable: HTTP {response.status_code}")
                except requests.exceptions.ConnectTimeout:
                    error_msg = "Server unreachable: Connection timeout"
                    diagnosis['errors'].append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    return diagnosis
                except requests.exceptions.ConnectionError as e:
                    error_msg = f"Server unreachable: Connection failed - {str(e)}"
                    diagnosis['errors'].append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    return diagnosis
                except Exception as e:
                    error_msg = f"Server unreachable: {str(e)}"
                    diagnosis['errors'].append(error_msg)
                    logger.error(f"❌ {error_msg}")
                    return diagnosis
                
                # 2. SSL证书检查（仅针对HTTPS）
                if self.server_url.startswith('https'):
                    logger.info("🔒 Testing SSL certificate...")
                    try:
                        response = requests.head(self.server_url, timeout=10, verify=True)
                        diagnosis['ssl_valid'] = True
                        logger.info("✅ SSL certificate valid")
                    except requests.exceptions.SSLError as e:
                        diagnosis['errors'].append(f"SSL verification failed: {str(e)}")
                        logger.warning(f"⚠️ SSL certificate issue (will use unverified connection): {e}")
                    except Exception as e:
                        diagnosis['errors'].append(f"SSL check failed: {str(e)}")
                        logger.warning(f"⚠️ SSL check failed: {e}")
                else:
                    diagnosis['ssl_valid'] = True  # HTTP不需要SSL
                    logger.info("ℹ️ Using HTTP (no SSL check needed)")
                
                # 3. WebDAV端点测试
                logger.info("📁 Testing WebDAV endpoint...")
                try:
                    response = requests.request("OPTIONS", self.webdav_url, timeout=10)
                    if response.status_code in [200, 204, 401]:  # 401也表示端点存在
                        diagnosis['webdav_supported'] = True
                        logger.info(f"✅ WebDAV endpoint available: HTTP {response.status_code}")
                    else:
                        diagnosis['errors'].append(f"WebDAV endpoint failed: HTTP {response.status_code}")
                        logger.error(f"❌ WebDAV endpoint failed: HTTP {response.status_code}")
                except Exception as e:
                    diagnosis['errors'].append(f"WebDAV check failed: {str(e)}")
                    logger.error(f"❌ WebDAV check failed: {e}")
                
                # 4. 认证测试
                if diagnosis['webdav_supported']:
                    logger.info("🔐 Testing authentication...")
                    try:
                        auth = HTTPBasicAuth(self.username, self.password)
                        response = requests.request(
                            "PROPFIND",
                            self.webdav_url,
                            auth=auth,
                            headers={"Depth": "0"},
                            timeout=10
                        )
                        if response.status_code in [200, 207]:
                            diagnosis['auth_valid'] = True
                            diagnosis['root_accessible'] = True
                            logger.info(f"✅ Authentication successful: HTTP {response.status_code}")
                        elif response.status_code == 401:
                            diagnosis['errors'].append("Authentication failed: Invalid username or password")
                            logger.error("❌ Authentication failed: Invalid credentials")
                        else:
                            diagnosis['errors'].append(f"Auth check failed: HTTP {response.status_code}")
                            logger.error(f"❌ Authentication failed: HTTP {response.status_code}")
                    except Exception as e:
                        diagnosis['errors'].append(f"Auth check failed: {str(e)}")
                        logger.error(f"❌ Authentication test failed: {e}")
            
            except Exception as e:
                diagnosis['errors'].append(f"Diagnosis failed: {str(e)}")
                logger.error(f"❌ Diagnosis failed: {e}")
            
            return diagnosis
        
        # 在线程池中运行同步函数
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, _sync_diagnose)
            return result
    
    def get_connection_suggestions(self, diagnosis: Dict) -> List[str]:
        """Get connection troubleshooting suggestions based on diagnosis."""
        suggestions = []
        
        if not diagnosis['server_reachable']:
            suggestions.extend([
                "检查服务器地址是否正确 (例如: https://cloud.example.com)",
                "确认服务器正在运行且可以从网络访问",
                "检查防火墙设置",
                "尝试在浏览器中访问服务器地址"
            ])
        
        if not diagnosis['ssl_valid']:
            suggestions.extend([
                "服务器使用自签名证书或证书无效",
                "如果是自签名证书，这是正常的，应用会跳过SSL验证",
                "考虑为生产环境配置有效的SSL证书"
            ])
        
        if not diagnosis['webdav_supported']:
            suggestions.extend([
                "服务器可能不支持WebDAV",
                "检查NextCloud是否正确安装和配置",
                "确认WebDAV应用已启用",
                "尝试访问 https://yourserver.com/remote.php/dav"
            ])
        
        if not diagnosis['auth_valid']:
            suggestions.extend([
                "检查用户名和密码是否正确",
                "确认账户未被锁定或禁用",
                "如果启用了双因素认证，请使用应用专用密码",
                "检查NextCloud用户权限设置"
            ])
        
        if not diagnosis.get('root_accessible', False):
            suggestions.extend([
                "用户可能没有访问文件的权限",
                "检查NextCloud用户组和权限设置",
                "尝试在NextCloud网页界面中访问文件"
            ])
        
        if not suggestions:
            suggestions.append("连接诊断未发现明显问题，连接应该能够正常工作")
        
        return suggestions
        """清除本地缓存"""
        try:
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.temp_dir.mkdir(exist_ok=True)
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_size(self) -> int:
        """获取缓存大小（字节）"""
        total_size = 0
        try:
            for file_path in self.cache_dir.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"Error calculating cache size: {e}")
        return total_size
    
    def format_cache_size(self) -> str:
        """格式化缓存大小显示"""
        size = self.get_cache_size()
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
