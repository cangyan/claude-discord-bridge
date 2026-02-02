#!/usr/bin/env python3
"""
Discord Bot实现 - Claude-Discord Bridge的核心功能

此模块负责以下职责：
1. Discord消息的接收与处理
2. 图片附件文件的管理
3. 向Claude Code转发消息
4. 用户反馈的管理
5. 定期维护处理

可扩展性要点：
- 消息格式策略的添加
- 新附件文件格式的支持
- 自定义命令的添加
- 通知方法的扩展
- 会话管理的增强
"""

import os
import sys
import json
import asyncio
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any

# 添加包根目录（相对导入支持）
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import discord
    from discord.ext import commands, tasks
except ImportError:
    print("Error: discord.py is not installed. Run: pip install discord.py")
    sys.exit(1)

from config.settings import SettingsManager
from attachment_manager import AttachmentManager

# 日志设置（生产环境中可从外部配置文件读取）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageProcessor:
    """
    消息处理的策略模式实现

    未来的扩展：
    - 支持不同的消息格式
    - 内容过滤
    - 消息转换处理
    """

    @staticmethod
    def format_message_with_attachments(content: str, attachment_paths: List[str], session_num: int) -> str:
        """
        消息和附件路径的适当格式化

        扩展点：
        - 附件格式多样化（视频、音频、文档等）
        - 消息模板的自定义
        - 多语言支持

        Args:
            content: 原始消息内容
            attachment_paths: 附件文件的路径列表
            session_num: 会话编号

        Returns:
            str: 格式化后的消息
        """
        # 附件路径字符串的生成
        attachment_str = ""
        if attachment_paths:
            attachment_parts = [f"[附件图片的文件路径: {path}]" for path in attachment_paths]
            attachment_str = " " + " ".join(attachment_parts)

        # 消息类型的分支处理
        if content.startswith('/'):
            # 斜杠命令形式（直接执行Claude Code命令）
            return f"{content}{attachment_str} session={session_num}"
        else:
            # 普通消息形式（向Claude Code的通知）
            return f"来自Discord的通知: {content}{attachment_str} session={session_num}"

class ClaudeCLIBot(commands.Bot):
    """
    Claude CLI集成Discord Bot

    架构特点：
    - 异步处理带来的高响应性
    - 模块化设计带来的可扩展性
    - 健壮的错误处理
    - 自动资源管理

    可扩展元素：
    - 自定义命令的添加
    - 权限管理系统
    - 用户会话管理
    - 统计·分析功能
    - Webhook集成
    """

    # 可配置常量（将来可配置文件化）
    CLEANUP_INTERVAL_HOURS = 6
    REQUEST_TIMEOUT_SECONDS = 5
    LOADING_MESSAGE = "`...`"
    SUCCESS_MESSAGE = "> 消息发送完成"

    def __init__(self, settings_manager: SettingsManager):
        """
        Bot实例的初始化

        Args:
            settings_manager: 设置管理实例
        """
        self.settings = settings_manager
        self.attachment_manager = AttachmentManager()
        self.message_processor = MessageProcessor()

        # Discord Bot设置
        intents = discord.Intents.default()
        intents.message_content = True  # 消息内容的访问权限

        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        """
        Bot准备完成时的初始化处理

        扩展点：
        - 数据库连接初始化
        - 外部API连接确认
        - 统计信息的初始化
        - 定期处理任务的开始
        """
        logger.info(f'{self.user} has connected to Discord!')
        print(f'✅ Discord bot is ready as {self.user}')

        # 首次系统清理
        await self._perform_initial_cleanup()

        # 定期维护处理的开始
        await self._start_maintenance_tasks()

    async def _perform_initial_cleanup(self):
        """
        Bot启动时的首次清理处理

        扩展点：
        - 旧会话数据的删除
        - 日志文件的轮转
        - 缓存的初始化
        """
        cleanup_count = self.attachment_manager.cleanup_old_files()
        if cleanup_count > 0:
            print(f'🧹 Cleaned up {cleanup_count} old attachment files')

    async def _start_maintenance_tasks(self):
        """
        定期维护任务的开始

        扩展点：
        - 数据库维护
        - 统计信息的汇总
        - 外部API状态确认
        """
        if not self.cleanup_task.is_running():
            self.cleanup_task.start()
            print(f'⏰ Attachment cleanup task started (runs every {self.CLEANUP_INTERVAL_HOURS} hours)')

    async def on_message(self, message):
        """
        消息接收时的主要处理处理器

        处理流程：
        1. 消息的预先验证
        2. 会话确认
        3. 即时用户反馈
        4. 附件文件处理
        5. 消息格式化
        6. 向Claude Code转发
        7. 结果反馈

        扩展点：
        - 消息预处理过滤器
        - 权限检查
        - 速率限制
        - 日志记录
        - 统计收集
        """
        # 基本的验证
        if not await self._validate_message(message):
            return

        # 会话确认
        session_num = self.settings.channel_to_session(str(message.channel.id))
        if session_num is None:
            return

        # 用户反馈（即时加载显示）
        loading_msg = await self._send_loading_feedback(message.channel)
        if not loading_msg:
            return

        try:
            # 消息处理管道
            result_text = await self._process_message_pipeline(message, session_num)

        except Exception as e:
            result_text = f"❌ 处理错误: {str(e)[:100]}"
            logger.error(f"Message processing error: {e}", exc_info=True)

        # 最终结果的显示
        await self._update_feedback(loading_msg, result_text)

    async def _validate_message(self, message) -> bool:
        """
        消息的基本验证

        扩展点：
        - 垃圾邮件检测
        - 权限确认
        - 黑名单检查
        """
        # Bot自身的消息忽略
        if message.author == self.user:
            return False

        # Discord标准命令的处理
        await self.process_commands(message)

        return True

    async def _send_loading_feedback(self, channel) -> Optional[discord.Message]:
        """
        加载反馈的发送

        扩展点：
        - 自定义加载消息
        - 动画显示
        - 进度条
        """
        try:
            return await channel.send(self.LOADING_MESSAGE)
        except Exception as e:
            logger.error(f'反馈发送错误: {e}')
            return None

    async def _process_message_pipeline(self, message, session_num: int) -> str:
        """
        消息处理管道

        扩展点：
        - 处理步骤的添加
        - 异步处理的并行化
        - 缓存功能
        """
        # 步骤1: 附件文件处理
        attachment_paths = await self._process_attachments(message, session_num)

        # 步骤2: 消息格式化
        formatted_message = self.message_processor.format_message_with_attachments(
            message.content, attachment_paths, session_num
        )

        # 步骤3: 向Claude Code转发
        return await self._forward_to_claude(formatted_message, message, session_num)

    async def _process_attachments(self, message, session_num: int) -> List[str]:
        """
        附件文件的处理

        扩展点：
        - 新文件格式的支持
        - 文件转换处理
        - 病毒扫描
        """
        attachment_paths = []
        if message.attachments:
            try:
                attachment_paths = await self.attachment_manager.process_attachments(message.attachments)
                if attachment_paths:
                    print(f'📎 Processed {len(attachment_paths)} attachment(s) for session {session_num}')
            except Exception as e:
                logger.error(f'Attachment processing error: {e}')

        return attachment_paths

    async def _forward_to_claude(self, formatted_message: str, original_message, session_num: int) -> str:
        """
        向Claude Code的消息转发

        扩展点：
        - 多个转发目的地的支持
        - 转发失败时的重试
        - 负载均衡
        """
        try:
            payload = {
                'message': formatted_message,
                'channel_id': str(original_message.channel.id),
                'session': session_num,
                'user_id': str(original_message.author.id),
                'username': str(original_message.author)
            }

            flask_port = self.settings.get_port('flask')
            response = requests.post(
                f'http://localhost:{flask_port}/discord-message',
                json=payload,
                timeout=self.REQUEST_TIMEOUT_SECONDS
            )

            return self._format_response_status(response.status_code)

        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to Flask app. Is it running?")
            return "❌ 错误: 无法连接到Flask app"
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")
            return f"❌ 错误: {str(e)[:100]}"

    def _format_response_status(self, status_code: int) -> str:
        """
        响应状态的格式化

        扩展点：
        - 详细状态消息
        - 多语言支持
        - 自定义消息
        """
        if status_code == 200:
            return self.SUCCESS_MESSAGE
        else:
            return f"⚠️ 状态: {status_code}"

    async def _update_feedback(self, loading_msg: discord.Message, result_text: str):
        """
        反馈消息的更新

        扩展点：
        - 富消息显示
        - 进度状况的显示
        - 交互元素
        """
        try:
            await loading_msg.edit(content=result_text)
        except Exception as e:
            logger.error(f'消息更新失败: {e}')

    @tasks.loop(hours=CLEANUP_INTERVAL_HOURS)
    async def cleanup_task(self):
        """
        定期清理任务

        扩展点：
        - 数据库清理
        - 日志文件管理
        - 统计信息的汇总
        - 系统健康检查
        """
        try:
            cleanup_count = self.attachment_manager.cleanup_old_files()
            if cleanup_count > 0:
                logger.info(f'Automatic cleanup: {cleanup_count} files deleted')
        except Exception as e:
            logger.error(f'Error in cleanup task: {e}')

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """清理任务开始前的准备处理"""
        await self.wait_until_ready()

def create_bot_commands(bot: ClaudeCLIBot, settings: SettingsManager):
    """
    Bot命令的注册

    扩展点：
    - 新命令的添加
    - 基于权限的命令
    - 动态命令注册
    """

    @bot.command(name='status')
    async def status_command(ctx):
        """Bot状态确认命令"""
        sessions = settings.list_sessions()
        embed = discord.Embed(
            title="Claude CLI Bot Status",
            description="✅ Bot is running",
            color=discord.Color.green()
        )

        session_list = "\n".join([f"Session {num}: <#{ch_id}>" for num, ch_id in sessions])
        embed.add_field(name="Active Sessions", value=session_list or "No sessions configured", inline=False)

        await ctx.send(embed=embed)

    @bot.command(name='sessions')
    async def sessions_command(ctx):
        """已设置会话一览显示命令"""
        sessions = settings.list_sessions()
        if not sessions:
            await ctx.send("No sessions configured.")
            return

        lines = ["**Configured Sessions:**"]
        for num, channel_id in sessions:
            lines.append(f"Session {num}: <#{channel_id}>")

        await ctx.send("\n".join(lines))

def run_bot():
    """
    Discord Bot的主要执行函数

    扩展点：
    - 多个Bot管理
    - 分片支持
    - 高可用性设置
    """
    settings = SettingsManager()

    # 令牌确认
    token = settings.get_token()
    if not token or token == 'your_token_here':
        print("❌ Discord bot token not configured!")
        print("Run './install.sh' to set up the token.")
        sys.exit(1)

    # Bot实例创建
    bot = ClaudeCLIBot(settings)

    # 命令注册
    create_bot_commands(bot, settings)

    # Bot执行
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Failed to login. Check your Discord bot token.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running bot: {e}")
        logger.error(f"Bot execution error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_bot()




