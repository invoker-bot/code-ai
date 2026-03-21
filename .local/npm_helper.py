#!/usr/bin/env python3
"""
跨平台 npm 命令执行辅助函数
解决 Windows 上 subprocess 无法找到 npm 的问题
"""

import subprocess
import platform
import shutil
from typing import List, Union


def get_npm_command() -> str:
    """
    获取适合当前平台的 npm 命令

    Returns:
        str: Windows 上返回 'npm.cmd'，其他平台返回 'npm'
    """
    if platform.system() == "Windows":
        return "npm.cmd"
    return "npm"


def run_npm_command(args: Union[str, List[str]], shell: bool = None, **kwargs):
    """
    跨平台运行 npm 命令

    Args:
        args: npm 命令参数，可以是字符串或列表
              例如: "install -g package" 或 ["install", "-g", "package"]
        shell: 是否使用 shell，如果为 None 则自动判断
        **kwargs: 传递给 subprocess.run 的其他参数

    Returns:
        subprocess.CompletedProcess: 命令执行结果

    Examples:
        # 方式 1: 使用列表（推荐）
        run_npm_command(["install", "-g", "typescript"])

        # 方式 2: 使用字符串
        run_npm_command("install -g typescript")

        # 方式 3: 强制使用 shell
        run_npm_command("npm install -g typescript", shell=True)
    """
    # 自动判断是否使用 shell
    if shell is None:
        shell = isinstance(args, str)

    # 构建命令
    if isinstance(args, str):
        if shell:
            # 使用 shell 时，直接使用 npm（shell 会自动找到 npm.cmd）
            cmd = f"npm {args}" if not args.startswith("npm") else args
        else:
            # 不使用 shell 时，需要分割字符串并添加正确的 npm 命令
            npm_cmd = get_npm_command()
            cmd = [npm_cmd] + args.split()
    else:
        # 列表形式
        if shell:
            cmd = " ".join(["npm"] + args)
        else:
            npm_cmd = get_npm_command()
            cmd = [npm_cmd] + args

    return subprocess.run(cmd, shell=shell, **kwargs)


def check_npm_installed() -> bool:
    """
    检查 npm 是否已安装

    Returns:
        bool: 如果 npm 可用返回 True，否则返回 False
    """
    try:
        result = run_npm_command(
            ["--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_npm_version() -> str:
    """
    获取 npm 版本

    Returns:
        str: npm 版本号，如果获取失败返回空字符串
    """
    try:
        result = run_npm_command(
            ["--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


# 示例用法
if __name__ == "__main__":
    print(f"当前平台: {platform.system()}")
    print(f"npm 命令: {get_npm_command()}")
    print(f"npm 已安装: {check_npm_installed()}")

    if check_npm_installed():
        version = get_npm_version()
        print(f"npm 版本: {version}")

        print("\n测试运行 npm 命令:")

        # 测试 1: 列表形式（推荐）
        print("\n1. 使用列表形式:")
        result = run_npm_command(
            ["list", "-g", "--depth=0"],
            capture_output=True,
            text=True
        )
        print(f"   返回码: {result.returncode}")
        if result.returncode == 0:
            print(f"   输出前 200 字符: {result.stdout[:200]}")

        # 测试 2: 字符串形式 + shell
        print("\n2. 使用字符串形式 (shell=True):")
        result = run_npm_command(
            "config get prefix",
            shell=True,
            capture_output=True,
            text=True
        )
        print(f"   返回码: {result.returncode}")
        if result.returncode == 0:
            print(f"   npm prefix: {result.stdout.strip()}")
    else:
        print("\n❌ npm 未安装或不可用")
        print("请从 https://nodejs.org/ 安装 Node.js")
