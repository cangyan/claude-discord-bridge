#!/usr/bin/env python3
"""
Flask HTTP Bridge - Discord ↔ Claude Code 集成的核心

此模块负责以下职责：
1. 从Discord Bot接收HTTP API请求
2. 消息向Claude Code会话的转发
3. 系统状态的监视·报告
4. 会话管理的支援
5. 健康检查功能的提供

可扩展性要点：
- 新API端点的添加
- 消息转发方式的多样化
- 认证·权限管理的实现
- 日志·监视功能的强化
- 负载均衡·扩展对应
"""

import os
import sys
import json
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# 添加包根目录（相对导入支持）
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from flask import Flask, request, jsonify, Response
except ImportError:
    print("Error: Flask is not installed. Run: pip install flask")
    sys.exit(1)

from config.settings import SettingsManager

# 日志设置（生产环境中可从外部配置文件读取）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TmuxMessageForwarder:
    """
    tmux会话的消息转发处理

    未来的扩展：
    - tmux以外的转发方式（WebSocket、gRPC等）
    - 消息队列
    - 失败时的重试机制
    - 负载均衡对应
    """

    # 可配置常量（将来可配置文件化）
    TMUX_DELAY_SECONDS = 0.2
    SESSION_NAME_PREFIX = "claude-session"

    @classmethod
    def forward_message(cls, message: str, session_num: int) -> Tuple[bool, Optional[str]]:
        """
        向指定会话转发消息

        扩展点：
        - 转发方式的选择功能
        - 消息加密
        - 转发状况的详细记录
        - 批处理对应

        Args:
            message: 要转发的消息
            session_num: 转发目标会话编号

        Returns:
            Tuple[bool, Optional[str]]: (成功标志, 错误消息)
        """
        try:
            session_name = f"{cls.SESSION_NAME_PREFIX}-{session_num}"

            # 步骤1: 消息发送
            cls._send_tmux_keys(session_name, message)

            # 步骤2: Enter发送（命令执行）
            time.sleep(cls.TMUX_DELAY_SECONDS)
            cls._send_tmux_keys(session_name, 'C-m')

            logger.info(f"Message forwarded to session {session_num}")
            return True, None

        except subprocess.CalledProcessError as e:
            error_msg = f"tmux command failed: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg)
            return False, error_msg

    @classmethod
    def _send_tmux_keys(cls, session_name: str, keys: str):
        """
        向tmux会话发送按键输入

        扩展点：
        - 发送前验证
        - 会话存在确认
        - 替代转发方式
        """
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, keys],
            check=True,
            capture_output=True
        )

class MessageValidator:
    """
    接收消息的验证处理

    未来的扩展：
    - 垃圾邮件检测
    - 非法内容过滤
    - 速率限制
    - 权限检查
    """

    @staticmethod
    def validate_discord_message(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Discord 消息数据的验证

        扩展点：
        - 详细验证规则
        - 自定义验证逻辑
        - 用户权限检查

        Args:
            data: 接收到的消息数据

        Returns:
            Tuple[bool, Optional[str]]: (有效标志, 错误消息)
        """
        if not data:
            return False, "No data provided"

        # 必须字段的确认
        required_fields = ['message', 'session', 'channel_id']
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"

        # 消息长度限制检查
        message = data.get('message', '')
        if len(message) > 4000:  # 遵循Discord限制的上限
            return False, "Message too long"

        return True, None

class FlaskBridgeApp:
    """
    Flask HTTP Bridge应用程序

    架构特点：
    - RESTful API设计
    - 健壮的错误处理
    - 结构化日志输出
    - 可扩展的路由

    可扩展元素：
    - 认证·授权系统
    - API版本管理
    - 速率限制功能
    - 指标收集
    - WebSocket对应
    """

    def __init__(self, settings_manager: SettingsManager):
        """
        Flask应用程序的初始化

        Args:
            settings_manager: 设置管理实例
        """
        self.settings = settings_manager
        self.app = Flask(__name__)
        self.message_forwarder = TmuxMessageForwarder()
        self.message_validator = MessageValidator()
        self.active_processes = {}  # 扩展：活跃进程管理

        # 路由设置
        self._configure_routes()

        # 应用程序设置
        self._configure_app()

    def _configure_app(self):
        """
        Flask应用程序的设置

        扩展点：
        - CORS设置
        - 安全头部
        - 中间件添加
        """
        # 本番環境設定
        self.app.config['DEBUG'] = False
        self.app.config['TESTING'] = False

    def _configure_routes(self):
        """
        API路由的设置

        扩展点：
        - 新端点添加
        - API版本管理
        - 基于权限的路由
        """
        # 健康检查端点
        self.app.route('/health', methods=['GET'])(self.health_check)

        # 消息处理端点
        self.app.route('/discord-message', methods=['POST'])(self.handle_discord_message)

        # 会话管理端点
        self.app.route('/sessions', methods=['GET'])(self.get_sessions)

        # 状态确认端点
        self.app.route('/status', methods=['GET'])(self.get_status)

    def health_check(self) -> Response:
        """
        健康检查端点

        扩展点：
        - 依赖服务状态确认
        - 详细健康信息
        - 警报功能
        """
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',  # 拡張：バージョン管理
            'active_sessions': len(self.active_processes),
            'configured_sessions': len(self.settings.list_sessions())
        }

        return jsonify(health_data)

    def handle_discord_message(self) -> Response:
        """
        Discord 消息处理的主要端点

        处理流程：
        1. 请求数据的验证
        2. 消息详细信息的提取
        3. 向Claude Code会话的转发
        4. 处理结果的返回

        扩展点：
        - 异步处理对应
        - 消息队列
        - 优先级控制
        - 统计信息收集
        """
        try:
            # 步骤1: 数据验证
            data = request.json
            is_valid, error_msg = self.message_validator.validate_discord_message(data)
            if not is_valid:
                logger.warning(f"Invalid message data: {error_msg}")
                return jsonify({'error': error_msg}), 400

            # 步骤2: 消息详细信息提取
            message_info = self._extract_message_info(data)

            # 步骤3: 日志记录
            self._log_message_info(message_info)

            # 步骤4: 向Claude Code的转发
            success, error_msg = self._forward_to_claude(message_info)
            if not success:
                return jsonify({'error': error_msg}), 500

            # 步骤5: 成功响应
            return jsonify({
                'status': 'received',
                'session': message_info['session_num'],
                'message_length': len(message_info['message']),
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Unexpected error in message handling: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error'}), 500

    def _extract_message_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从请求数据中提取消息信息

        扩展点：
        - 附加元数据的提取
        - 数据规范化处理
        - 自定义字段对应
        """
        return {
            'message': data.get('message', ''),
            'channel_id': data.get('channel_id', ''),
            'session_num': data.get('session', 1),
            'user_id': data.get('user_id', ''),
            'username': data.get('username', 'Unknown'),
            'timestamp': datetime.now().isoformat()
        }

    def _log_message_info(self, message_info: Dict[str, Any]):
        """
        消息信息的日志记录

        扩展点：
        - 结构化日志输出
        - 外部日志系统集成
        - 指标收集
        """
        session_num = message_info['session_num']
        username = message_info['username']
        message_preview = message_info['message'][:100] + "..." if len(message_info['message']) > 100 else message_info['message']

        print(f"[Session {session_num}] {username}: {message_preview}")
        logger.info(f"Message processed: session={session_num}, user={username}, length={len(message_info['message'])}")

    def _forward_to_claude(self, message_info: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        向Claude Code会话的消息转发

        扩展点：
        - 转发方式的选择
        - 失败时的重试
        - 负载均衡
        """
        session_num = message_info['session_num']
        message = message_info['message']

        success, error_msg = self.message_forwarder.forward_message(message, session_num)

        if success:
            print(f"✅ Forwarded to Claude session {session_num}")
        else:
            print(f"❌ Failed to forward to Claude session {session_num}: {error_msg}")

        return success, error_msg

    def get_sessions(self) -> Response:
        """
        获取已设置会话一览

        扩展点：
        - 会话详细信息
        - 会话状态确认
        - 过滤功能
        """
        sessions = self.settings.list_sessions()
        response_data = {
            'sessions': [
                {
                    'number': num,
                    'channel_id': ch_id,
                    'status': 'active'  # 拡張：セッション状態確認
                }
                for num, ch_id in sessions
            ],
            'default': self.settings.get_default_session(),
            'total_count': len(sessions)
        }

        return jsonify(response_data)

    def get_status(self) -> Response:
        """
        获取应用程序状态

        扩展点：
        - 详细系统信息
        - 性能指标
        - 依赖服务状态
        """
        status_data = {
            'status': 'running',
            'configured': self.settings.is_configured(),
            'sessions_count': len(self.settings.list_sessions()),
            'active_processes': len(self.active_processes),
            'uptime': datetime.now().isoformat(),  # 拡張：稼働時間計算
            'version': '1.0.0'
        }

        return jsonify(status_data)

    def run(self, host: str = '127.0.0.1', port: Optional[int] = None):
        """
        Flask应用程序的执行

        扩展点：
        - WSGI 服务器对应
        - SSL/TLS设置
        - 负载均衡设置
        """
        if port is None:
            port = self.settings.get_port('flask')

        print(f"🌐 Starting Flask HTTP Bridge on {host}:{port}")
        logger.info(f"Flask app starting on {host}:{port}")

        try:
            # 本番モードで実行
            self.app.run(
                host=host,
                port=port,
                debug=False,
                threaded=True,  # マルチスレッド対応
                use_reloader=False
            )
        except Exception as e:
            error_msg = f"Failed to start Flask app: {e}"
            print(f"❌ {error_msg}")
            logger.error(error_msg, exc_info=True)
            sys.exit(1)

def run_flask_app(port: Optional[int] = None):
    """
    Flask 应用程序的启动函数

    扩展点：
    - 从配置文件读取启动参数
    - 环境别设置的切换
    - 多个实例管理
    """
    settings = SettingsManager()

    # 設定確認
    if not settings.is_configured():
        print("❌ Claude-Discord Bridge is not configured.")
        print("Run './install.sh' first.")
        sys.exit(1)

    # アプリケーション作成・実行
    app = FlaskBridgeApp(settings)
    app.run(port=port)

if __name__ == "__main__":
    run_flask_app()



