#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cookie池管理工具
提供快速配置和重置Cookie池的功能
"""

from cookie_pool import CookiePool
from loguru import logger


def update_all_intervals(min_interval: int = 1, daily_limit: int = 100):
    """
    批量更新所有账号的请求间隔和每日限制

    Args:
        min_interval: 最小请求间隔（秒），默认1秒
        daily_limit: 每日请求限制，默认100次
    """
    pool = CookiePool()
    pool.update_all_settings(daily_limit=daily_limit, min_interval=min_interval)
    logger.info(f"✅ 已更新所有账号: min_interval={min_interval}秒, daily_limit={daily_limit}次/天")


def reset_all_accounts():
    """重置所有账号状态（清除错误计数和冷却时间）"""
    pool = CookiePool()

    for cookie_id in pool.accounts.keys():
        pool.reset_account(cookie_id)

    logger.info(f"✅ 已重置 {len(pool.accounts)} 个账号")


def show_pool_status():
    """显示Cookie池状态"""
    pool = CookiePool()
    status = pool.get_pool_status()

    print("\n" + "="*60)
    print("Cookie池状态")
    print("="*60)
    print(f"总账号数: {status['total_accounts']}")
    print(f"启用账号数: {status['active_accounts']}")
    print(f"当前可用账号数: {status['available_accounts']}")
    print(f"轮换策略: {status['strategy']}")
    print("\n账号详情:")
    print("-"*60)

    for i, account_info in enumerate(status['accounts'], 1):
        print(f"\n账号 {i}: {account_info['name']}")
        print(f"  状态: {'✅ 启用' if account_info['is_active'] else '❌ 禁用'}")
        print(f"  使用次数: {account_info['use_count']} (今日: {account_info['daily_use_count']}/{account_info['daily_limit']})")
        print(f"  成功/失败: {account_info['success_count']}/{account_info['fail_count']}")
        print(f"  错误计数: {account_info['error_count']}")
        print(f"  最小间隔: {account_info['min_interval']}秒")
        print(f"  总笔记数: {account_info['total_notes']}")
        if account_info['last_use_time']:
            print(f"  最后使用: {account_info['last_use_time']}")
        if account_info['cooldown_until']:
            print(f"  冷却至: {account_info['cooldown_until']}")

    print("\n" + "="*60)


def main():
    """主菜单"""
    print("\n" + "="*60)
    print("Cookie池管理工具")
    print("="*60)
    print("1. 查看Cookie池状态")
    print("2. 批量更新请求间隔设置")
    print("3. 重置所有账号状态")
    print("4. 修改轮换策略")
    print("0. 退出")
    print("="*60)

    while True:
        choice = input("\n请选择操作 (0-4): ").strip()

        if choice == '1':
            show_pool_status()

        elif choice == '2':
            try:
                min_interval = int(input("输入最小请求间隔（秒，推荐1）: ").strip())
                daily_limit = int(input("输入每日请求限制（次，推荐100）: ").strip())
                update_all_intervals(min_interval, daily_limit)
                print(f"\n✅ 配置已更新")
            except ValueError:
                print("❌ 输入无效，请输入数字")

        elif choice == '3':
            confirm = input("确认重置所有账号？(y/n): ").strip().lower()
            if confirm == 'y':
                reset_all_accounts()
                print(f"\n✅ 所有账号已重置")

        elif choice == '4':
            print("\n轮换策略选项:")
            print("  1. round_robin - 轮询（均衡使用）")
            print("  2. random - 随机选择")
            print("  3. least_used - 优先使用次数最少的")
            strategy_choice = input("选择策略 (1-3): ").strip()

            strategies = {
                '1': 'round_robin',
                '2': 'random',
                '3': 'least_used'
            }

            if strategy_choice in strategies:
                pool = CookiePool()
                pool.set_strategy(strategies[strategy_choice])
                print(f"\n✅ 策略已设置为: {strategies[strategy_choice]}")
            else:
                print("❌ 无效选择")

        elif choice == '0':
            print("再见！")
            break

        else:
            print("❌ 无效选择，请重新输入")


if __name__ == "__main__":
    main()
