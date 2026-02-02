# Claude-Discord Bridge

无缝连接Claude Code和Discord，支持多会话、斜杠命令、多张图片发送的便携式桥接工具。

## 主要特点
- **可扩展的多会话**: 只需创建一个Discord bot，每次添加频道时Claude Code会话会自动增设。
- **图片附件支持**: 完全支持图片分析工作流
- **斜杠命令支持**: 命令也可以通过Discord执行
- **完全自动设置**: 一键环境检测与一键导入
- **便携式设计**: 不依赖绝对路径或系统特定设置

## 操作流程
1. 创建Discord Bot。授予权限并生成Bot令牌
2. 启动install.sh，开始安装。
3. 安装时，最多可以设置3个Bot令牌和频道ID。
   （之后可以使用vai add-session {channel id}进一步添加）
4. 在CLAUDE.md中记录Discord的回复规则。
5. 使用「vai」启动。
6. 使用「vai view」在tmux中实时直接操作·监视多个会话
7. 从Discord聊天 → Claude Code会回复。

## 系统要求
- macOS 或 Linux
- Python 3.8以上
- tmux
- Discord Bot令牌（在[Discord Developer Portal](https://discord.com/developers/applications)创建）

## 安装 / 卸载
```bash
git clone https://github.com/yamkz/claude-discord-bridge.git
cd claude-discord-bridge
./install.sh
```

```bash
cd claude-discord-bridge
./uninstall.sh
```

## 快速开始
**1. 在CLAUDE.md中添加**
请在您工作位置的CLAUDE.md文件中添加以下设置：
[CLAUDE.md设置示例](./CLAUDE.md)

**1. 启动桥接，确认会话状况**
```bash
vai
vai view
```

**2. 在Discord中测试**

**3. 停止**
```bash
vexit
```

## 命令一览
### 基本命令
- `vai` - 启动全功能（Discord bot + 路由 + Claude Code会话群）
- `vai status` - 确认运行状态
- `vai doctor` - 执行环境诊断
- `vai view` - 实时显示全会话
  (目前仅实现最多6画面显示)
- `vexit` - 停止全功能
- `vai add-session <频道ID>`- 添加频道ID
- `vai list-session`- 频道ID一览
- `dp [session] "消息"` - 向Discord发送消息

## 许可证
MIT License - 详情请参阅LICENSE文件
