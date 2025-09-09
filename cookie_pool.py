#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cookie号池管理系统
实现多账号轮换、状态追踪、限流控制
"""

import json
import time
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger
import hashlib

class CookieAccount:
    """单个Cookie账号"""
    
    def __init__(self, cookie_str: str, name: str = None, remark: str = ""):
        """
        初始化Cookie账号
        
        Args:
            cookie_str: Cookie字符串
            name: 账号名称/标识
            remark: 备注信息
        """
        self.cookie_str = cookie_str
        self.cookie_id = self._generate_id(cookie_str)
        self.name = name or f"账号_{self.cookie_id[:8]}"
        self.remark = remark
        
        # 状态信息
        self.is_active = True  # 是否可用
        self.last_use_time = None  # 最后使用时间
        self.use_count = 0  # 使用次数
        self.error_count = 0  # 错误次数
        self.daily_use_count = 0  # 今日使用次数
        self.daily_limit = 100  # 每日限制次数
        
        # 冷却控制
        self.cooldown_until = None  # 冷却结束时间
        self.min_interval = 3  # 最小使用间隔(秒)
        
        # 统计信息
        self.success_count = 0  # 成功次数
        self.fail_count = 0  # 失败次数
        self.total_notes = 0  # 总共爬取笔记数
        self.create_time = datetime.now()
        self.last_reset_date = datetime.now().date()
    
    def _generate_id(self, cookie_str: str) -> str:
        """生成Cookie唯一ID"""
        return hashlib.md5(cookie_str.encode()).hexdigest()
    
    def can_use(self) -> Tuple[bool, str]:
        """
        检查是否可以使用
        
        Returns:
            (是否可用, 原因说明)
        """
        if not self.is_active:
            return False, "账号已禁用"
        
        # 检查冷却时间
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            remaining = (self.cooldown_until - datetime.now()).total_seconds()
            return False, f"冷却中，还需等待 {int(remaining)} 秒"
        
        # 检查最小间隔
        if self.last_use_time:
            elapsed = (datetime.now() - self.last_use_time).total_seconds()
            if elapsed < self.min_interval:
                return False, f"请求过快，需等待 {int(self.min_interval - elapsed)} 秒"
        
        # 检查每日限制
        self._check_daily_reset()
        if self.daily_use_count >= self.daily_limit:
            return False, f"已达每日限制 ({self.daily_limit} 次)"
        
        # 检查错误率
        if self.error_count >= 5:
            return False, "错误次数过多，账号可能异常"
        
        return True, "可用"
    
    def _check_daily_reset(self):
        """检查并重置每日计数"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_use_count = 0
            self.last_reset_date = today
            logger.info(f"账号 {self.name} 每日计数已重置")
    
    def use(self):
        """标记使用"""
        self.last_use_time = datetime.now()
        self.use_count += 1
        self.daily_use_count += 1
        logger.debug(f"账号 {self.name} 被使用，今日第 {self.daily_use_count} 次")
    
    def mark_success(self, notes_count: int = 1):
        """标记成功"""
        self.success_count += 1
        self.total_notes += notes_count
        self.error_count = max(0, self.error_count - 1)  # 成功后减少错误计数
        logger.debug(f"账号 {self.name} 成功获取 {notes_count} 条笔记")
    
    def mark_error(self, error_msg: str = ""):
        """标记错误"""
        self.fail_count += 1
        self.error_count += 1
        
        # 根据错误次数设置冷却时间
        if self.error_count >= 3:
            cooldown_minutes = min(self.error_count * 5, 60)  # 最多冷却60分钟
            self.cooldown_until = datetime.now() + timedelta(minutes=cooldown_minutes)
            logger.warning(f"账号 {self.name} 错误次数过多，冷却 {cooldown_minutes} 分钟")
        
        # 错误次数过多时禁用账号
        if self.error_count >= 10:
            self.is_active = False
            logger.error(f"账号 {self.name} 错误次数过多，已禁用")
        
        logger.warning(f"账号 {self.name} 发生错误: {error_msg}")
    
    def set_cooldown(self, seconds: int):
        """设置冷却时间"""
        self.cooldown_until = datetime.now() + timedelta(seconds=seconds)
        logger.info(f"账号 {self.name} 设置冷却 {seconds} 秒")
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'cookie_id': self.cookie_id,
            'name': self.name,
            'remark': self.remark,
            'is_active': self.is_active,
            'use_count': self.use_count,
            'daily_use_count': self.daily_use_count,
            'daily_limit': self.daily_limit,
            'min_interval': self.min_interval,
            'success_count': self.success_count,
            'fail_count': self.fail_count,
            'error_count': self.error_count,
            'total_notes': self.total_notes,
            'last_use_time': self.last_use_time.isoformat() if self.last_use_time else None,
            'cooldown_until': self.cooldown_until.isoformat() if self.cooldown_until else None,
            'create_time': self.create_time.isoformat()
        }


class CookiePool:
    """Cookie号池管理器"""
    
    def __init__(self, config_file: str = "cookie_pool_config.json"):
        """
        初始化Cookie池
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.accounts: Dict[str, CookieAccount] = {}
        self.lock = threading.Lock()
        
        # 轮换策略
        self.strategy = "round_robin"  # round_robin, random, least_used
        self.last_used_index = -1
        
        # 加载配置
        self.load_config()
        
    def load_config(self):
        """加载配置文件"""
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                for account_data in config.get('accounts', []):
                    account = CookieAccount(
                        cookie_str=account_data['cookie_str'],
                        name=account_data.get('name'),
                        remark=account_data.get('remark', '')
                    )
                    # 恢复状态
                    account.is_active = account_data.get('is_active', True)
                    account.use_count = account_data.get('use_count', 0)
                    account.success_count = account_data.get('success_count', 0)
                    account.fail_count = account_data.get('fail_count', 0)
                    account.error_count = account_data.get('error_count', 0)
                    account.total_notes = account_data.get('total_notes', 0)
                    account.daily_limit = account_data.get('daily_limit', 100)
                    account.min_interval = account_data.get('min_interval', 3)
                    
                    self.accounts[account.cookie_id] = account
                    
                self.strategy = config.get('strategy', 'round_robin')
                logger.info(f"加载了 {len(self.accounts)} 个Cookie账号")
                
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
    
    def save_config(self):
        """保存配置文件"""
        try:
            config = {
                'strategy': self.strategy,
                'accounts': []
            }
            
            for account in self.accounts.values():
                config['accounts'].append({
                    'cookie_str': account.cookie_str,
                    'name': account.name,
                    'remark': account.remark,
                    'is_active': account.is_active,
                    'use_count': account.use_count,
                    'success_count': account.success_count,
                    'fail_count': account.fail_count,
                    'error_count': account.error_count,
                    'total_notes': account.total_notes,
                    'daily_limit': account.daily_limit,
                    'min_interval': account.min_interval
                })
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            logger.info("配置已保存")
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
    
    def add_account(self, cookie_str: str, name: str = None, remark: str = "") -> bool:
        """
        添加Cookie账号
        
        Args:
            cookie_str: Cookie字符串
            name: 账号名称
            remark: 备注
            
        Returns:
            是否添加成功
        """
        account = CookieAccount(cookie_str, name, remark)
        
        with self.lock:
            if account.cookie_id in self.accounts:
                logger.warning(f"账号已存在: {account.name}")
                return False
            
            self.accounts[account.cookie_id] = account
            self.save_config()
            logger.info(f"添加账号: {account.name}")
            return True
    
    def remove_account(self, cookie_id: str) -> bool:
        """移除Cookie账号"""
        with self.lock:
            if cookie_id in self.accounts:
                account = self.accounts.pop(cookie_id)
                self.save_config()
                logger.info(f"移除账号: {account.name}")
                return True
            return False
    
    def get_available_account(self) -> Optional[CookieAccount]:
        """
        获取可用的Cookie账号
        
        Returns:
            可用的账号对象，如果没有则返回None
        """
        with self.lock:
            available_accounts = []
            
            for account in self.accounts.values():
                can_use, reason = account.can_use()
                if can_use:
                    available_accounts.append(account)
                else:
                    logger.debug(f"账号 {account.name} 不可用: {reason}")
            
            if not available_accounts:
                logger.warning("没有可用的Cookie账号")
                return None
            
            # 根据策略选择账号
            if self.strategy == "random":
                selected = random.choice(available_accounts)
            elif self.strategy == "least_used":
                selected = min(available_accounts, key=lambda x: x.daily_use_count)
            else:  # round_robin
                self.last_used_index = (self.last_used_index + 1) % len(available_accounts)
                selected = available_accounts[self.last_used_index]
            
            selected.use()
            logger.info(f"选择账号: {selected.name} (今日第 {selected.daily_use_count} 次)")
            return selected
    
    def mark_account_success(self, cookie_id: str, notes_count: int = 1):
        """标记账号成功"""
        if cookie_id in self.accounts:
            self.accounts[cookie_id].mark_success(notes_count)
            self.save_config()
    
    def mark_account_error(self, cookie_id: str, error_msg: str = ""):
        """标记账号错误"""
        if cookie_id in self.accounts:
            self.accounts[cookie_id].mark_error(error_msg)
            self.save_config()
    
    def get_pool_status(self) -> dict:
        """获取号池状态"""
        total = len(self.accounts)
        active = sum(1 for a in self.accounts.values() if a.is_active)
        available = sum(1 for a in self.accounts.values() if a.can_use()[0])
        
        return {
            'total_accounts': total,
            'active_accounts': active,
            'available_accounts': available,
            'strategy': self.strategy,
            'accounts': [account.to_dict() for account in self.accounts.values()]
        }
    
    def set_strategy(self, strategy: str):
        """设置轮换策略"""
        if strategy in ['round_robin', 'random', 'least_used']:
            self.strategy = strategy
            self.save_config()
            logger.info(f"轮换策略已设置为: {strategy}")
    
    def reset_account(self, cookie_id: str):
        """重置账号状态"""
        if cookie_id in self.accounts:
            account = self.accounts[cookie_id]
            account.is_active = True
            account.error_count = 0
            account.cooldown_until = None
            account.daily_use_count = 0
            self.save_config()
            logger.info(f"账号 {account.name} 已重置")
    
    def update_account_settings(self, cookie_id: str, daily_limit: int = None, min_interval: int = None):
        """更新账号设置"""
        if cookie_id in self.accounts:
            account = self.accounts[cookie_id]
            if daily_limit is not None:
                account.daily_limit = daily_limit
            if min_interval is not None:
                account.min_interval = min_interval
            self.save_config()
            logger.info(f"账号 {account.name} 设置已更新")
            return True
        return False
    
    def update_all_settings(self, daily_limit: int = None, min_interval: int = None):
        """批量更新所有账号设置"""
        for account in self.accounts.values():
            if daily_limit is not None:
                account.daily_limit = daily_limit
            if min_interval is not None:
                account.min_interval = min_interval
        self.save_config()
        logger.info(f"所有账号设置已更新: 每日限制={daily_limit}, 最小间隔={min_interval}")
    
    def batch_add_from_file(self, file_path: str) -> int:
        """
        从文件批量添加Cookie
        文件格式：每行一个Cookie，可选格式：
        - cookie_string
        - name|cookie_string
        - name|cookie_string|remark
        
        Returns:
            成功添加的数量
        """
        added_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('|')
                    if len(parts) == 1:
                        cookie_str = parts[0]
                        name = None
                        remark = ""
                    elif len(parts) == 2:
                        name, cookie_str = parts
                        remark = ""
                    else:
                        name, cookie_str, remark = parts[:3]
                    
                    if self.add_account(cookie_str, name, remark):
                        added_count += 1
                        
            logger.info(f"从文件添加了 {added_count} 个账号")
            
        except Exception as e:
            logger.error(f"批量添加失败: {e}")
            
        return added_count


# 全局Cookie池实例
cookie_pool = CookiePool()


def initialize_pool_from_env():
    """从.env文件初始化号池"""
    try:
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        
        # 尝试从环境变量加载多个Cookie
        cookies_str = os.getenv('COOKIES', '')
        if cookies_str:
            # 支持多个Cookie，用双换行符分隔
            cookies_list = cookies_str.split('\n\n')
            for i, cookie in enumerate(cookies_list):
                cookie = cookie.strip()
                if cookie:
                    cookie_pool.add_account(
                        cookie_str=cookie,
                        name=f"环境变量账号_{i+1}"
                    )
            
            logger.info(f"从环境变量加载了 {len(cookies_list)} 个Cookie")
            
    except Exception as e:
        logger.error(f"从环境变量初始化失败: {e}")


if __name__ == "__main__":
    # 测试代码
    pool = CookiePool()
    
    # 添加测试账号
    pool.add_account("test_cookie_1", "测试账号1", "测试用")
    pool.add_account("test_cookie_2", "测试账号2", "测试用")
    
    # 获取可用账号
    account = pool.get_available_account()
    if account:
        print(f"获取到账号: {account.name}")
        
        # 模拟使用
        import time
        time.sleep(1)
        
        # 标记成功
        pool.mark_account_success(account.cookie_id, 10)
    
    # 查看状态
    status = pool.get_pool_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))