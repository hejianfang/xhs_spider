#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书JSON文件管理界面启动脚本
用于管理和解析search_results目录下的JSON文件
"""

import sys
import os

def check_requirements():
    """检查必要的依赖"""
    missing_packages = []
    
    try:
        import flask
    except ImportError:
        missing_packages.append('Flask')
    
    if missing_packages:
        print("❌ 缺少必要的依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装依赖:")
        print("pip install Flask")
        return False
    
    return True

def check_cookies():
    """检查Cookie配置"""
    env_file = '.env'
    if not os.path.exists(env_file):
        print("⚠️  警告: 未找到 .env 文件")
        print("请创建 .env 文件并配置小红书Cookie:")
        print("COOKIES=your_xiaohongshu_cookies_here")
        print("注意：没有Cookie将无法进行解析操作")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'COOKIES=' not in content or content.strip().endswith('COOKIES='):
            print("⚠️  警告: Cookie未正确配置")
            print("请在 .env 文件中设置有效的小红书Cookie")
            print("注意：没有Cookie将无法进行解析操作")
            return False
    
    return True

def check_search_results():
    """检查search_results目录"""
    search_dir = 'search_results'
    if not os.path.exists(search_dir):
        os.makedirs(search_dir)
        print(f"📁 创建了 {search_dir} 目录")
        return 0
    
    # 统计JSON文件数量
    json_files = [f for f in os.listdir(search_dir) if f.endswith('.json')]
    return len(json_files)

def main():
    print("="*60)
    print("📊 小红书JSON文件管理系统")
    print("="*60)
    
    # 检查依赖
    print("📦 检查依赖包...")
    if not check_requirements():
        return
    print("✅ 依赖检查通过")
    
    # 检查Cookie配置
    print("🍪 检查Cookie配置...")
    cookie_ok = check_cookies()
    if cookie_ok:
        print("✅ Cookie配置正常")
    else:
        print("⚠️  Cookie未配置，解析功能将无法使用")
    
    # 检查search_results目录
    print("📁 检查数据目录...")
    json_count = check_search_results()
    if json_count > 0:
        print(f"✅ 找到 {json_count} 个JSON文件")
    else:
        print("📝 暂无JSON文件，请先使用搜索功能生成数据")
    
    # 创建必要的目录
    dirs_to_create = ['templates', 'search_results']
    for dir_name in dirs_to_create:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    
    print("\n🚀 启动JSON文件管理界面...")
    print("📱 访问地址: http://localhost:5001")
    print("📱 或者: http://127.0.0.1:5001")
    print("\n💡 功能说明:")
    print("   1. 查看所有搜索结果JSON文件")
    print("   2. 批量选择文件进行解析")
    print("   3. 配置解析选项（评论、媒体文件等）")
    print("   4. 一键解析获取完整笔记数据")
    print("   5. 查看解析进度和结果")
    print("\n按 Ctrl+C 停止服务")
    print("="*60)
    
    # 启动Flask应用
    try:
        from web_interface import app
        app.run(debug=False, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("请确保 web_interface.py 文件存在")

if __name__ == '__main__':
    main()