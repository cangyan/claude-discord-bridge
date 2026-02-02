#!/usr/bin/env python3
"""
tmux Manager
管理tmux会话
"""

import os
import sys
import subprocess
from pathlib import Path

class TmuxManager:
    """进行tmux会话管理的类"""

    def __init__(self, session_name="claude-discord-bridge"):
        self.session_name = session_name
        self.claude_session_prefix = "claude-session"

    def is_session_exists(self) -> bool:
        """检查tmux会话是否存在"""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.session_name],
                capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("Error: tmux is not installed")
            return False

    def create_session(self) -> bool:
        """创建新的tmux会话"""
        if self.is_session_exists():
            print(f"tmux session '{self.session_name}' already exists")
            return True

        try:
            # Create new detached session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", self.session_name],
                check=True
            )
            print(f"✅ Created tmux session: {self.session_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating tmux session: {e}")
            return False

    def kill_session(self) -> bool:
        """终止tmux会话"""
        if not self.is_session_exists():
            print(f"tmux session '{self.session_name}' does not exist")
            return True

        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                check=True
            )
            print(f"✅ Killed tmux session: {self.session_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error killing tmux session: {e}")
            return False

    def send_command(self, pane: str, command: str) -> bool:
        """向tmux窗格发送命令"""
        if not self.is_session_exists():
            print(f"tmux session '{self.session_name}' does not exist")
            return False

        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", f"{self.session_name}:{pane}", command, "Enter"],
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error sending command to tmux: {e}")
            return False

    def create_panes(self) -> bool:
        """创建所需的窗格"""
        if not self.is_session_exists():
            if not self.create_session():
                return False

        try:
            # Split window horizontally
            subprocess.run(
                ["tmux", "split-window", "-h", "-t", f"{self.session_name}:0"],
                check=True
            )

            # Split the right pane vertically
            subprocess.run(
                ["tmux", "split-window", "-v", "-t", f"{self.session_name}:0.1"],
                check=True
            )

            print("✅ Created tmux panes")
            return True
        except subprocess.CalledProcessError:
            # Panes might already exist
            return True

    def attach(self):
        """附加到tmux会话"""
        if not self.is_session_exists():
            print(f"tmux session '{self.session_name}' does not exist")
            return

        try:
            subprocess.run(["tmux", "attach-session", "-t", self.session_name])
        except subprocess.CalledProcessError as e:
            print(f"Error attaching to tmux session: {e}")

    def list_panes(self) -> list:
        """获取窗格列表"""
        if not self.is_session_exists():
            return []

        try:
            result = subprocess.run(
                ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_index}"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
            return []
        except subprocess.CalledProcessError:
            return []

    def create_claude_session(self, session_num: int, work_dir: str, options: str = "") -> bool:
        """创建Claude Code用的tmux会话"""
        session_name = f"{self.claude_session_prefix}-{session_num}"

        # Check if session already exists
        if self.is_claude_session_exists(session_num):
            print(f"Claude session {session_num} already exists")
            return True

        try:
            # Build Claude command
            claude_cmd = f"cd \"{work_dir}\" && claude {options}".strip()

            # Create new detached session with Claude Code
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name, claude_cmd],
                check=True
            )
            print(f"✅ Created Claude session {session_num}: {session_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating Claude session {session_num}: {e}")
            return False

    def is_claude_session_exists(self, session_num: int) -> bool:
        """检查Claude Code用的会话是否存在"""
        session_name = f"{self.claude_session_prefix}-{session_num}"
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def kill_claude_session(self, session_num: int) -> bool:
        """终止Claude Code用的会话"""
        session_name = f"{self.claude_session_prefix}-{session_num}"

        if not self.is_claude_session_exists(session_num):
            return True

        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                check=True
            )
            print(f"✅ Killed Claude session {session_num}: {session_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error killing Claude session {session_num}: {e}")
            return False

    def kill_all_claude_sessions(self) -> bool:
        """终止所有Claude Code用会话"""
        try:
            # List all sessions and filter Claude sessions
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                sessions = result.stdout.strip().split('\n')
                claude_sessions = [s for s in sessions if s.startswith(self.claude_session_prefix)]

                for session in claude_sessions:
                    try:
                        subprocess.run(["tmux", "kill-session", "-t", session], check=True)
                        print(f"✅ Killed Claude session: {session}")
                    except subprocess.CalledProcessError:
                        pass

            return True
        except subprocess.CalledProcessError:
            return True

    def list_claude_sessions(self) -> list:
        """获取Claude Code用会话列表"""
        sessions = []
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                all_sessions = result.stdout.strip().split('\n')
                claude_sessions = [s for s in all_sessions if s.startswith(self.claude_session_prefix)]

                for session in claude_sessions:
                    # Extract session number
                    try:
                        num = int(session.split('-')[-1])
                        sessions.append((num, session))
                    except ValueError:
                        pass

                sessions.sort(key=lambda x: x[0])

            return sessions
        except subprocess.CalledProcessError:
            return []

def setup_tmux_environment():
    """设置tmux环境"""
    manager = TmuxManager()

    # Check if tmux is installed
    if subprocess.run(["which", "tmux"], capture_output=True).returncode != 0:
        print("❌ tmux is not installed. Please install it first.")
        print("  macOS: brew install tmux")
        print("  Ubuntu/Debian: sudo apt-get install tmux")
        return False

    # Create session and panes
    if not manager.create_session():
        return False

    if not manager.create_panes():
        return False

    print("✅ tmux environment is ready")
    print(f"  To attach: tmux attach -t {manager.session_name}")

    return True

if __name__ == "__main__":
    # Test tmux setup
    setup_tmux_environment()
