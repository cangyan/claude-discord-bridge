#!/usr/bin/env python3
"""
Attachment Manager - Discord附件文件管理系统

此模块负责以下职责：
1. Discord附件文件的异步下载
2. 文件格式的验证与大小限制管理
3. 自动文件命名与重复避免
4. 存储管理与自动清理
5. Claude Code集成用路径生成

可扩展性要点：
- 新文件格式的支持添加
- 文件转换·处理功能的实现
- 外部存储集成（S3、GCS等）
- 病毒扫描·安全功能
- 元数据提取·分析功能
"""

import os
import sys
import secrets
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

# 添加包根目录（相对导入支持）
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp is not installed. Run: pip install aiohttp")
    sys.exit(1)

from config.settings import SettingsManager

# ログ設定
logger = logging.getLogger(__name__)

@dataclass
class FileMetadata:
    """
    文件元数据管理用数据类

    扩展点：
    - 附加元数据字段
    - 文件分析结果
    - 转换处理信息
    """
    original_name: str
    saved_name: str
    file_path: str
    size: int
    mime_type: Optional[str] = None
    download_url: str = ""
    timestamp: str = ""

class FileValidator:
    """
    文件验证处理

    未来的扩展：
    - MIME type详细验证
    - 文件内容扫描
    - 病毒检查集成
    - 自定义验证规则
    """

    # 支持的图像格式（可扩展）
    SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff'}

    # 文件大小限制（遵循Discord限制，将来可配置）
    MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB

    @classmethod
    def is_supported_format(cls, filename: str) -> bool:
        """
        检查是否支持的文件格式

        扩展点：
        - 动态支持格式管理
        - MIME type验证
        - 自定义格式定义
        """
        return Path(filename).suffix.lower() in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def is_valid_size(cls, size: int) -> bool:
        """
        检查文件大小是否在限制内

        扩展点：
        - 用户别大小限制
        - 动态限制设置
        - 通过压缩处理避免限制
        """
        return size <= cls.MAX_FILE_SIZE

    @classmethod
    def validate_attachment(cls, attachment) -> Tuple[bool, Optional[str]]:
        """
        附件文件的综合验证

        Args:
            attachment: Discord attachment object

        Returns:
            Tuple[bool, Optional[str]]: (有效标志, 错误消息)
        """
        # ファイル形式チェック
        if not cls.is_supported_format(attachment.filename):
            return False, f"Unsupported file format: {attachment.filename}"

        # ファイルサイズチェック
        if not cls.is_valid_size(attachment.size):
            return False, f"File too large ({attachment.size} bytes, max {cls.MAX_FILE_SIZE})"

        return True, None

class FileNamingStrategy:
    """
    文件命名策略

    未来的扩展：
    - 命名规则的自定义
    - 用户别命名空间
    - 基于内容的命名
    - 重复避免算法
    """

    @staticmethod
    def generate_unique_filename(original_name: str) -> str:
        """
        生成唯一的文件名

        扩展点：
        - 命名模式的设置化
        - 基于哈希的命名
        - 日期格式自定义

        Args:
            original_name: 原始文件名

        Returns:
            str: 生成的唯一文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = secrets.token_hex(3)  # 6字符的随机字符串
        extension = Path(original_name).suffix.lower()

        # 扩展名不存在时的默认处理
        if not extension:
            extension = '.bin'

        return f"IMG_{timestamp}_{random_suffix}{extension}"

class StorageManager:
    """
    存储管理系统

    未来的扩展：
    - 外部存储支持（S3、GCS等）
    - 存储分层化
    - 自动备份
    - 容量限制管理
    """

    def __init__(self, config_dir: Path):
        """
        存储管理器的初始化

        Args:
            config_dir: 设置目录路径
        """
        self.config_dir = config_dir
        self.attachments_dir = config_dir / 'attachments'
        self.ensure_storage_directory()

    def ensure_storage_directory(self):
        """
        存储目录的创建·确认

        扩展点：
        - 权限设置的优化
        - 多个目录管理
        - 容量监视功能
        """
        try:
            self.attachments_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Storage directory ensured: {self.attachments_dir}")
        except Exception as e:
            logger.error(f"Failed to create storage directory: {e}")
            raise

    def get_storage_path(self, filename: str) -> Path:
        """
        获取文件保存路径

        扩展点：
        - 目录分层化（按日期等）
        - 负载均衡目录选择
        - 重复文件处理
        """
        return self.attachments_dir / filename

    def cleanup_old_files(self, max_age_days: int = 1) -> int:
        """
        旧文件的清理

        扩展点：
        - 详细的删除策略
        - 归档功能
        - 删除前通知

        Args:
            max_age_days: 保留期间（天数）

        Returns:
            int: 删除的文件数
        """
        if not self.attachments_dir.exists():
            return 0

        try:
            cutoff_time = datetime.now() - timedelta(days=max_age_days)
            deleted_count = 0

            for file_path in self.attachments_dir.glob('IMG_*'):
                try:
                    # ファイルの更新時刻を取得
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if file_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old attachment: {file_path.name}")

                except OSError as e:
                    logger.warning(f"Failed to delete {file_path.name}: {e}")
                    continue

            if deleted_count > 0:
                logger.info(f"Cleanup completed: {deleted_count} files deleted")

            return deleted_count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def get_storage_info(self) -> Dict[str, Any]:
        """
        获取存储使用情况

        扩展点：
        - 详细统计信息
        - 文件种类分析
        - 使用量预测
        """
        try:
            if not self.attachments_dir.exists():
                return {
                    'total_files': 0,
                    'total_size': 0,
                    'total_size_mb': 0.0,
                    'directory': str(self.attachments_dir)
                }

            files = list(self.attachments_dir.glob('IMG_*'))
            total_size = sum(f.stat().st_size for f in files if f.is_file())

            return {
                'total_files': len(files),
                'total_size': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'directory': str(self.attachments_dir),
                'last_updated': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting storage info: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'total_size_mb': 0.0,
                'directory': str(self.attachments_dir),
                'error': str(e)
            }

class AttachmentDownloader:
    """
    异步文件下载处理

    未来的扩展：
    - 并行下载数控制
    - 进度显示功能
    - 重试机制
    - 带宽限制功能
    """

    # 可配置常量（将来可配置文件化）
    DOWNLOAD_TIMEOUT_SECONDS = 30
    MAX_CONCURRENT_DOWNLOADS = 5

    def __init__(self, storage_manager: StorageManager):
        """
        下载器的初始化

        Args:
            storage_manager: 存储管理器实例
        """
        self.storage_manager = storage_manager
        self.file_validator = FileValidator()
        self.naming_strategy = FileNamingStrategy()

    async def download_attachment(self, attachment) -> Optional[FileMetadata]:
        """
        Discord附件文件的异步下载

        扩展点：
        - 进度回调
        - 部分下载支持
        - 下载优先级控制

        Args:
            attachment: Discord attachment object

        Returns:
            Optional[FileMetadata]: 下载成功时的元数据
        """
        try:
            # ステップ1: ファイル検証
            is_valid, error_msg = self.file_validator.validate_attachment(attachment)
            if not is_valid:
                logger.warning(f"Invalid attachment {attachment.filename}: {error_msg}")
                return None

            # ステップ2: ファイル名生成
            saved_filename = self.naming_strategy.generate_unique_filename(attachment.filename)
            file_path = self.storage_manager.get_storage_path(saved_filename)

            # ステップ3: ダウンロード実行
            success = await self._perform_download(attachment.url, file_path)
            if not success:
                return None

            # ステップ4: メタデータ作成
            metadata = FileMetadata(
                original_name=attachment.filename,
                saved_name=saved_filename,
                file_path=str(file_path.absolute()),
                size=attachment.size,
                download_url=attachment.url,
                timestamp=datetime.now().isoformat()
            )

            logger.info(f"Downloaded attachment: {saved_filename} ({attachment.size} bytes)")
            return metadata

        except Exception as e:
            logger.error(f"Error downloading {attachment.filename}: {e}")
            return None

    async def _perform_download(self, url: str, file_path: Path) -> bool:
        """
        实际的下载处理

        扩展点：
        - 分块单位下载
        - 恢复功能
        - 进度通知
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.DOWNLOAD_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()

                        # ファイル保存
                        with open(file_path, 'wb') as f:
                            f.write(content)

                        # 権限設定（読み取り専用）
                        os.chmod(file_path, 0o644)

                        return True
                    else:
                        logger.error(f"HTTP {response.status} for URL: {url}")
                        return False

        except asyncio.TimeoutError:
            logger.error(f"Download timeout for URL: {url}")
            return False
        except Exception as e:
            logger.error(f"Download error for URL {url}: {e}")
            return False

class AttachmentManager:
    """
    附件文件管理的集成类

    架构特点：
    - 异步处理带来的高并行性
    - 模块化设计带来的可扩展性
    - 健壮的错误处理
    - 自动资源管理

    可扩展元素：
    - 文件转换处理
    - 元数据提取
    - 外部API集成
    - 统计·分析功能
    - 备份·同步功能
    """

    def __init__(self):
        """
        附件文件管理器的初始化
        """
        self.settings = SettingsManager()
        self.storage_manager = StorageManager(self.settings.config_dir)
        self.downloader = AttachmentDownloader(self.storage_manager)

    async def process_attachments(self, attachments) -> List[str]:
        """
        多个附件文件的并行处理

        扩展点：
        - 处理优先级控制
        - 实时进度显示
        - 处理结果的详细分析

        Args:
            attachments: Discord attachment objects 的列表

        Returns:
            List[str]: 成功的文件路径列表
        """
        if not attachments:
            return []

        logger.info(f"Processing {len(attachments)} attachment(s)")

        # 並列ダウンロード実行
        tasks = [self.downloader.download_attachment(attachment) for attachment in attachments]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 結果の処理
        successful_paths = []
        failed_count = 0

        for result in results:
            if isinstance(result, FileMetadata):
                successful_paths.append(result.file_path)
            elif isinstance(result, Exception):
                logger.error(f"Attachment processing failed: {result}")
                failed_count += 1
            else:
                # None の場合（検証失敗等）
                failed_count += 1

        # 処理結果ログ
        logger.info(f"Attachment processing completed: {len(successful_paths)} success, {failed_count} failed")

        return successful_paths

    def cleanup_old_files(self, max_age_days: int = 1) -> int:
        """
        旧文件的清理（同步包装器）

        Args:
            max_age_days: 保留期间（天数）

        Returns:
            int: 删除的文件数
        """
        return self.storage_manager.cleanup_old_files(max_age_days)

    def get_storage_info(self) -> Dict[str, Any]:
        """
        存储信息的获取（同步包装器）

        Returns:
            Dict[str, Any]: 存储使用情况
        """
        return self.storage_manager.get_storage_info()

# 测试·调试用函数
async def test_attachment_manager():
    """
    AttachmentManager的动作测试

    扩展点：
    - 单元测试实现
    - 性能测试
    - 压力测试
    """
    manager = AttachmentManager()

    print(f"Storage directory: {manager.storage_manager.attachments_dir}")
    print(f"Storage info: {manager.get_storage_info()}")

    # クリーンアップテスト
    deleted = manager.cleanup_old_files()
    print(f"Cleanup: {deleted} files deleted")

if __name__ == "__main__":
    asyncio.run(test_attachment_manager())

