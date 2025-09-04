#!/usr/bin/env python3
"""
测试配置保存功能
"""

import sys
import os
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nextcloud_music_player.config_manager import ConfigManager

def test_sync_folder_save():
    """测试同步目录保存功能"""
    print("🧪 测试配置保存功能...")
    
    # 创建配置管理器
    config_manager = ConfigManager("test_app")
    
    # 获取当前同步目录
    current_sync_folder = config_manager.get("connection.default_sync_folder", "")
    print(f"📁 当前同步目录: '{current_sync_folder}'")
    
    # 测试保存新的同步目录
    test_folder = "/mp3/音乐/测试目录/"
    print(f"💾 设置新的同步目录: '{test_folder}'")
    
    config_manager.set("connection.default_sync_folder", test_folder)
    save_success = config_manager.save_config()
    
    if save_success:
        print("✅ 配置保存成功")
    else:
        print("❌ 配置保存失败")
        return False
    
    # 重新加载配置验证
    config_manager_new = ConfigManager("test_app")
    reloaded_folder = config_manager_new.get("connection.default_sync_folder", "")
    
    print(f"🔄 重新加载后的同步目录: '{reloaded_folder}'")
    
    if reloaded_folder == test_folder:
        print("✅ 配置保存和重新加载测试通过")
        return True
    else:
        print("❌ 配置保存或重新加载失败")
        return False

def test_auto_save_behavior():
    """测试自动保存行为"""
    print("\n🧪 测试自动保存行为...")
    
    config_manager = ConfigManager("test_app")
    
    # 模拟用户修改配置
    test_values = [
        "/mp3/音乐/目录1/",
        "/mp3/音乐/目录2/",
        "/mp3/音乐/目录3/"
    ]
    
    for test_value in test_values:
        print(f"🔧 设置同步目录: '{test_value}'")
        config_manager.set("connection.default_sync_folder", test_value)
        
        # 立即保存（模拟修复后的行为）
        save_success = config_manager.save_config()
        if save_success:
            print(f"✅ 配置 '{test_value}' 保存成功")
        else:
            print(f"❌ 配置 '{test_value}' 保存失败")
    
    # 验证最后的值
    final_value = config_manager.get("connection.default_sync_folder", "")
    print(f"🏁 最终配置值: '{final_value}'")
    
    expected_final = test_values[-1]
    if final_value == expected_final:
        print("✅ 自动保存行为测试通过")
        return True
    else:
        print("❌ 自动保存行为测试失败")
        return False

if __name__ == "__main__":
    print("🚀 开始测试配置管理器...")
    
    test1_passed = test_sync_folder_save()
    test2_passed = test_auto_save_behavior()
    
    print(f"\n📊 测试结果:")
    print(f"   - 同步目录保存测试: {'✅ 通过' if test1_passed else '❌ 失败'}")
    print(f"   - 自动保存行为测试: {'✅ 通过' if test2_passed else '❌ 失败'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过！配置保存功能正常工作。")
    else:
        print("\n⚠️ 部分测试失败，需要进一步检查。")
