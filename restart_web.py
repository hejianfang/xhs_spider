#!/usr/bin/env python3
# encoding: utf-8
"""
自动停止占用8080端口的进程并重新启动Web应用
"""

import os
import sys
import subprocess
import signal
import time

def kill_port_process(port):
    """停止占用指定端口的进程"""
    try:
        # 查找占用端口的进程
        result = subprocess.run(['lsof', '-ti', f':{port}'], 
                              capture_output=True, text=True)
        
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"🔍 发现占用端口{port}的进程: {', '.join(pids)}")
            
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"✅ 已停止进程 {pid}")
                except ProcessLookupError:
                    print(f"⚠️ 进程 {pid} 已不存在")
                except Exception as e:
                    print(f"❌ 停止进程 {pid} 失败: {e}")
            
            # 等待进程完全停止
            time.sleep(2)
            return True
        else:
            print(f"✅ 端口{port}当前空闲")
            return True
            
    except Exception as e:
        print(f"❌ 检查端口{port}失败: {e}")
        return False

def start_web_app():
    """启动Web应用"""
    print("🚀 启动小红书数据爬取Web应用...")
    try:
        # 直接执行start_web.py
        os.system("python3 start_web.py")
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def main():
    print("="*60)
    print("🔧 小红书数据爬取 Web 应用重启工具")
    print("="*60)
    
    # 停止占用8080端口的进程
    print("🛑 正在停止占用端口8080的进程...")
    if kill_port_process(8080):
        print("✅ 端口清理完成")
        
        # 启动Web应用
        start_web_app()
    else:
        print("❌ 端口清理失败，请手动处理")
        sys.exit(1)

if __name__ == '__main__':
    main()