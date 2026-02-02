#!/usr/bin/env python3
"""
环境检测·诊断模块
自动检测Claude-Discord Bridge的环境，并诊断问题
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class EnvironmentDetector:
    """进行环境自动检测与诊断的类"""

    def __init__(self):
        self.toolkit_root = Path(__file__).parent.parent
        # Support both old and new config directory names for backward compatibility
        old_config_dir = Path.home() / '.claude-cli-toolkit'
        new_config_dir = Path.home() / '.claude-discord-bridge'

        self.config_dir = new_config_dir if new_config_dir.exists() else old_config_dir
        self.env_file = self.config_dir / '.env'

    def detect_all(self) -> Dict[str, any]:
        """检测全环境信息"""
        return {
            'os': self.detect_os(),
            'python': self.detect_python(),
            'dependencies': self.check_dependencies(),
            'shell': self.detect_shell(),
            'config': self.check_config(),
            'ports': self.check_ports()
        }

    def detect_os(self) -> Dict[str, str]:
        """检测OS信息"""
        return {
            'system': sys.platform,
            'version': os.uname().release if hasattr(os, 'uname') else 'unknown'
        }

    def detect_python(self) -> Dict[str, any]:
        """检测Python环境"""
        return {
            'version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'executable': sys.executable,
            'venv': hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        }

    def check_dependencies(self) -> Dict[str, bool]:
        """检查必要的依赖关系"""
        deps = {
            'tmux': shutil.which('tmux') is not None,
            'curl': shutil.which('curl') is not None,
            'git': shutil.which('git') is not None
        }

        # Python packages
        try:
            import requests
            deps['requests'] = True
        except ImportError:
            deps['requests'] = False

        try:
            import discord
            deps['discord.py'] = True
        except ImportError:
            deps['discord.py'] = False

        try:
            import flask
            deps['flask'] = True
        except ImportError:
            deps['flask'] = False

        return deps

    def detect_shell(self) -> str:
        """检测使用中的shell"""
        shell = os.environ.get('SHELL', '').split('/')[-1]
        return shell or 'unknown'

    def check_config(self) -> Dict[str, bool]:
        """检查配置文件的存在"""
        return {
            'config_dir': self.config_dir.exists(),
            'env_file': self.env_file.exists(),
            'token_set': self._check_token_set() if self.env_file.exists() else False
        }

    def _check_token_set(self) -> bool:
        """检查Discord token是否已设置"""
        try:
            with open(self.env_file, 'r') as f:
                content = f.read()
                return 'DISCORD_BOT_TOKEN=' in content and 'DISCORD_BOT_TOKEN=your_token_here' not in content
        except:
            return False

    def check_ports(self) -> Dict[int, bool]:
        """检查必要端口的利用状况"""
        # Get Flask port from settings
        flask_port = self._get_flask_port()
        ports = {flask_port: True}

        for port in ports:
            sock = None
            try:
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('127.0.0.1', port))
                ports[port] = result != 0  # True if port is available
            except:
                ports[port] = False
            finally:
                if sock:
                    sock.close()

        return ports

    def _get_flask_port(self) -> int:
        """从配置文件获取Flask端口"""
        try:
            if self.env_file.exists():
                with open(self.env_file, 'r') as f:
                    for line in f:
                        if line.startswith('FLASK_PORT='):
                            return int(line.split('=', 1)[1].strip())
        except:
            pass
        return 5000  # Default fallback

    def diagnose(self) -> Tuple[bool, List[str]]:
        """诊断环境，列出问题点"""
        issues = []
        env_info = self.detect_all()

        # OS check
        if env_info['os']['system'] not in ['darwin', 'linux']:
            issues.append(f"⚠️  Unsupported OS: {env_info['os']['system']} (macOS/Linux recommended)")

        # Python check
        py_version = env_info['python']['version'].split('.')
        if int(py_version[0]) < 3 or (int(py_version[0]) == 3 and int(py_version[1]) < 8):
            issues.append(f"⚠️  Python version {env_info['python']['version']} is too old (3.8+ required)")

        # Dependencies check
        for dep, installed in env_info['dependencies'].items():
            if not installed:
                if dep in ['tmux', 'curl', 'git']:
                    issues.append(f"❌ Missing system dependency: {dep}")
                else:
                    issues.append(f"❌ Missing Python package: {dep}")

        # Config check
        if not env_info['config']['config_dir']:
            issues.append("⚠️  Configuration directory not found (will be created during setup)")
        elif not env_info['config']['token_set']:
            issues.append("⚠️  Discord bot token not configured")

        # Port check
        for port, available in env_info['ports'].items():
            if not available:
                issues.append(f"⚠️  Port {port} is already in use")

        # Overall health
        is_healthy = len([i for i in issues if i.startswith('❌')]) == 0

        return is_healthy, issues

    def print_diagnosis(self):
        """显示诊断结果"""
        print("🔍 Claude-Discord Bridge Environment Diagnosis")
        print("=" * 50)

        env_info = self.detect_all()
        is_healthy, issues = self.diagnose()

        # System info
        print(f"\n📦 System Information:")
        print(f"  OS: {env_info['os']['system']} {env_info['os']['version']}")
        print(f"  Shell: {env_info['shell']}")
        print(f"  Python: {env_info['python']['version']}")

        # Dependencies
        print(f"\n🔧 Dependencies:")
        for dep, installed in env_info['dependencies'].items():
            status = "✅" if installed else "❌"
            print(f"  {status} {dep}")

        # Configuration
        print(f"\n⚙️  Configuration:")
        print(f"  Config directory: {'✅' if env_info['config']['config_dir'] else '❌'}")
        print(f"  Environment file: {'✅' if env_info['config']['env_file'] else '❌'}")
        print(f"  Discord token: {'✅' if env_info['config']['token_set'] else '❌'}")

        # Ports
        print(f"\n🔌 Port Availability:")
        for port, available in env_info['ports'].items():
            status = "✅ Available" if available else "❌ In use"
            print(f"  Port {port}: {status}")

        # Issues summary
        if issues:
            print(f"\n⚠️  Issues Found:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"\n✅ All checks passed!")

        print("\n" + "=" * 50)
        print(f"Overall Status: {'✅ Healthy' if is_healthy else '❌ Issues detected'}")

        return is_healthy

if __name__ == "__main__":
    detector = EnvironmentDetector()
    detector.print_diagnosis()
