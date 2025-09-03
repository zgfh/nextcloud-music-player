#!/usr/bin/env python3
"""
测试Linux构建环境的脚本
用于验证系统依赖是否正确安装
"""

import sys
import subprocess
import os

def run_command(cmd, description):
    """运行命令并捕获输出"""
    print(f"\n=== {description} ===")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"Command: {cmd}")
        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def check_python_packages():
    """检查Python包是否可以导入"""
    packages = [
        'toga',
        'requests', 
        'httpx',
        'pygame',
        'mutagen'
    ]
    
    print("\n=== Checking Python packages ===")
    for package in packages:
        try:
            __import__(package)
            print(f"✓ {package} is available")
        except ImportError as e:
            print(f"✗ {package} is NOT available: {e}")

def check_system_packages():
    """检查系统包是否可用"""
    commands = [
        ("pkg-config --version", "pkg-config"),
        ("gcc --version", "gcc compiler"),
        ("pkg-config --exists cairo", "cairo development files"),
        ("pkg-config --exists pango", "pango development files"),
        ("pkg-config --exists gobject-introspection-1.0", "gobject-introspection"),
        ("pkg-config --exists webkit2gtk-4.1 || pkg-config --exists webkit2gtk-4.0", "webkit2gtk"),
    ]
    
    print("\n=== Checking system packages ===")
    for cmd, desc in commands:
        success = run_command(cmd, desc)
        if success:
            print(f"✓ {desc} is available")
        else:
            print(f"✗ {desc} is NOT available")

def main():
    print("Linux Build Environment Test")
    print("=" * 50)
    
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Working directory: {os.getcwd()}")
    
    check_python_packages()
    check_system_packages()
    
    # 测试briefcase
    print("\n=== Testing briefcase ===")
    run_command("python -m briefcase --version", "briefcase version")
    
    print("\n=== Test completed ===")

if __name__ == "__main__":
    main()
