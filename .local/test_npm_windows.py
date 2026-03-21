#!/usr/bin/env python3
"""
Windows npm 环境诊断脚本
在 Windows 上运行此脚本来诊断 npm 安装和配置问题
"""

import subprocess
import platform
import os
import sys
from pathlib import Path

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def run_command(cmd, shell=False):
    """安全地运行命令并返回结果"""
    try:
        if isinstance(cmd, str) and not shell:
            cmd = cmd.split()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=shell,
            timeout=10
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except FileNotFoundError as e:
        return {
            'success': False,
            'error': f'FileNotFoundError: {e}',
            'stdout': '',
            'stderr': ''
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Command timeout',
            'stdout': '',
            'stderr': ''
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Exception: {type(e).__name__}: {e}',
            'stdout': '',
            'stderr': ''
        }

def main():
    print_section("系统信息")
    print(f"操作系统: {platform.system()}")
    print(f"平台: {platform.platform()}")
    print(f"Python 版本: {sys.version}")
    print(f"Python 可执行文件: {sys.executable}")

    print_section("环境变量 PATH")
    path_env = os.environ.get('PATH', '')
    for i, path in enumerate(path_env.split(os.pathsep), 1):
        print(f"{i}. {path}")

    print_section("测试 1: 查找 npm (使用 where 命令 - Windows)")
    if platform.system() == "Windows":
        result = run_command("where npm", shell=True)
        if result['success']:
            print(f"✓ 找到 npm:")
            print(result['stdout'])
        else:
            print(f"✗ 未找到 npm")
            if 'error' in result:
                print(f"  错误: {result['error']}")
    else:
        print("⊘ 跳过 (非 Windows 系统)")

    print_section("测试 2: 查找 npm (使用 which 命令 - Unix-like)")
    result = run_command("which npm", shell=True)
    if result['success']:
        print(f"✓ 找到 npm:")
        print(result['stdout'])
    else:
        print(f"✗ 未找到 npm")
        if 'error' in result:
            print(f"  错误: {result['error']}")

    print_section("测试 3: 直接运行 npm (不使用 shell)")
    result = run_command(['npm', '--version'])
    if result['success']:
        print(f"✓ npm 版本: {result['stdout']}")
    else:
        print(f"✗ 无法运行 npm")
        if 'error' in result:
            print(f"  错误: {result['error']}")
        if result.get('stderr'):
            print(f"  stderr: {result['stderr']}")

    print_section("测试 4: 运行 npm.cmd (Windows 特定)")
    if platform.system() == "Windows":
        result = run_command(['npm.cmd', '--version'])
        if result['success']:
            print(f"✓ npm.cmd 版本: {result['stdout']}")
        else:
            print(f"✗ 无法运行 npm.cmd")
            if 'error' in result:
                print(f"  错误: {result['error']}")
    else:
        print("⊘ 跳过 (非 Windows 系统)")

    print_section("测试 5: 使用 shell=True 运行 npm")
    result = run_command('npm --version', shell=True)
    if result['success']:
        print(f"✓ npm 版本 (shell=True): {result['stdout']}")
    else:
        print(f"✗ 无法运行 npm (shell=True)")
        if 'error' in result:
            print(f"  错误: {result['error']}")
        if result.get('stderr'):
            print(f"  stderr: {result['stderr']}")

    print_section("测试 6: 检查 Node.js")
    result = run_command(['node', '--version'])
    if result['success']:
        print(f"✓ Node.js 版本: {result['stdout']}")
    else:
        print(f"✗ 无法运行 node")
        if 'error' in result:
            print(f"  错误: {result['error']}")

    print_section("测试 7: 常见 npm 安装路径检查 (Windows)")
    if platform.system() == "Windows":
        common_paths = [
            Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'nodejs' / 'npm.cmd',
            Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')) / 'nodejs' / 'npm.cmd',
            Path(os.environ.get('APPDATA', '')) / 'npm' / 'npm.cmd',
            Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'nodejs' / 'npm.cmd',
        ]

        for path in common_paths:
            if path.exists():
                print(f"✓ 找到: {path}")
            else:
                print(f"✗ 不存在: {path}")
    else:
        print("⊘ 跳过 (非 Windows 系统)")

    print_section("诊断总结")
    print("\n如果所有测试都失败，可能的原因：")
    print("1. Node.js/npm 未安装")
    print("   解决：从 https://nodejs.org/ 下载并安装")
    print("\n2. npm 不在 PATH 环境变量中")
    print("   解决：重新安装 Node.js 或手动添加到 PATH")
    print("\n3. 需要重启终端/命令提示符")
    print("   解决：关闭并重新打开终端")
    print("\n如果某些测试成功，记录哪个方法有效，以便在代码中使用。")
    print("="*60)

if __name__ == "__main__":
    main()
