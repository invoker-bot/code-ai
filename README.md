# ai-code-switcher

一个用于切换 AI 编码工具配置文件并启动相应 CLI 的工具。

## 功能特性

- 管理多个 AI 编码工具配置文件（Claude、Codex、Gemini）
- 快速切换不同的配置文件
- 统一的命令行接口
- 支持一键升级所有 AI CLI 工具

## 安装

```bash
pip install -e .
```

## 使用方法

### 列出所有配置文件

```bash
code-ai list
```

### 添加新配置文件

```bash
code-ai add
```

### 使用指定配置文件启动

```bash
# 使用 fox-gemini 配置启动 Gemini CLI
code-ai fox-gemini

# 使用 4399 配置启动 Claude CLI
code-ai 4399

# 传递额外参数
code-ai fox-claude -p "hi"
```

### 删除配置文件

```bash
code-ai remove <profile-name>
```

### 升级 AI CLI 工具

```bash
code-ai upgrade
```

该命令会通过 npm 升级以下工具：
- @anthropic-ai/claude-code
- @openai/codex
- @google/gemini-cli

### 查看版本

```bash
code-ai --version
```

### 查看帮助

```bash
code-ai --help
```

## 配置

配置文件存储在用户目录下，包含各个配置文件的设置信息。

## 开发

### 项目结构

```
src/code_ai/
├── __init__.py      # 包初始化
├── cli.py           # 命令行入口
├── config.py        # 配置管理
├── launcher.py      # 启动器
└── profiles.py      # 配置文件管理
```

### 依赖

- Python >= 3.8
- pyyaml >= 5.0

## 许可证

MIT
