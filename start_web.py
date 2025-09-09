#!/usr/bin/env python3
# encoding: utf-8
"""
小红书数据爬取 Web 应用启动脚本
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
    
    try:
        import flask_cors
    except ImportError:
        missing_packages.append('Flask-CORS')
    
    if missing_packages:
        print("❌ 缺少必要的依赖包:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n请运行以下命令安装依赖:")
        print("pip install Flask Flask-CORS")
        return False
    
    return True

def check_cookies():
    """检查Cookie配置"""
    env_file = '.env'
    if not os.path.exists(env_file):
        print("⚠️  警告: 未找到 .env 文件")
        print("请创建 .env 文件并配置小红书Cookie:")
        print("COOKIES=your_xiaohongshu_cookies_here")
        return False
    
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'COOKIES=' not in content or content.strip().endswith('COOKIES='):
            print("⚠️  警告: Cookie未正确配置")
            print("请在 .env 文件中设置有效的小红书Cookie")
            return False
    
    return True

def main():
    print("="*60)
    print("🔍 小红书数据爬取 Web 应用")
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
        print("⚠️  Cookie配置有问题，但可以继续启动（功能可能受限）")
    
    # 创建必要的目录
    dirs_to_create = ['templates', 'static/css', 'static/js', 'search_results']
    for dir_name in dirs_to_create:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    
    print("\n🚀 启动Web应用...")
    print("📱 访问地址: http://localhost:8080")
    print("📱 或者: http://127.0.0.1:8080")
    print("\n💡 使用说明:")
    print("   1. 在搜索框输入关键词（如：日本料理）")
    print("   2. 设置搜索数量和高级选项")
    print("   3. 点击'开始搜索'获取笔记列表")
    print("   4. 点击'解析所有笔记'获取详细信息")
    print("   5. 点击'查看详情'查看具体笔记内容")
    print("\n按 Ctrl+C 停止服务")
    print("="*60)
    
    # 启动Flask应用
    try:
        from web_app import app
        app.run(debug=False, host='0.0.0.0', port=8080)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")

if __name__ == '__main__':
    main()