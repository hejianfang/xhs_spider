#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Flask Web应用 - 小红书搜索结果管理界面
提供JSON文件管理和批量解析功能
"""

from flask import Flask, render_template, jsonify, request
import os
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from xhs_utils.common_util import init
from json_to_full_data import JsonToFullData
from typing import Dict, List, Any
from cookie_pool import cookie_pool, initialize_pool_from_env
from loguru import logger

# 配置日志输出
logger.remove()  # 移除默认handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)
# 创建logs目录
os.makedirs("logs", exist_ok=True)
# 添加文件输出
logger.add(
    "logs/web_interface.log",
    rotation="10 MB",  # 日志文件达到10MB时轮转
    retention="7 days",  # 保留7天的日志
    encoding="utf-8",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
)

logger.info("=" * 60)
logger.info("小红书JSON文件管理系统启动中...")
logger.info("=" * 60)

app = Flask(__name__)

# ========== 启动时清理临时文件 ==========
def cleanup_temp_files():
    """清理search_results目录下的临时文件"""
    try:
        temp_pattern = os.path.join(SEARCH_RESULTS_DIR, 'temp_single_*.json')
        import glob
        temp_files = glob.glob(temp_pattern)

        if temp_files:
            logger.info(f"🧹 发现 {len(temp_files)} 个临时文件，开始清理...")
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    logger.info(f"   ✅ 已删除: {os.path.basename(temp_file)}")
                except Exception as e:
                    logger.warning(f"   ❌ 删除失败: {os.path.basename(temp_file)}, 错误: {e}")
            logger.info("✅ 临时文件清理完成")
        else:
            logger.info("✅ 未发现临时文件")
    except Exception as e:
        logger.error(f"清理临时文件时出错: {e}")

# 启动时执行清理
cleanup_temp_files()

# 配置
SEARCH_RESULTS_DIR = "search_results"
TEMPLATES_DIR = "templates"

# 初始化环境
cookies_str, base_path = init()
logger.info("环境初始化完成")

# 初始化Cookie池
initialize_pool_from_env()
if not cookie_pool.accounts and cookies_str:
    # 如果池为空但有默认Cookie，添加到池中
    cookie_pool.add_account(cookies_str, "默认账号", "从.env文件加载")
    logger.info("已从.env文件加载默认Cookie账号")
else:
    logger.info(f"Cookie池已加载 {len(cookie_pool.accounts)} 个账号")

@app.route('/')
def index():
    """渲染主页"""
    return render_template('json_manager.html')

@app.route('/cookie-pool')
def cookie_pool_page():
    """渲染Cookie池管理页面"""
    return render_template('cookie_pool.html')

@app.route('/api/list-json-files')
def list_json_files():
    """获取search_results目录下的所有JSON文件信息"""
    try:
        files_info = []
        search_dir = Path(SEARCH_RESULTS_DIR)
        
        if not search_dir.exists():
            return jsonify({
                'success': True,
                'files': [],
                'message': 'search_results目录不存在'
            })
        
        # 遍历所有JSON文件
        for json_file in search_dir.glob('*.json'):
            try:
                file_stat = json_file.stat()
                file_info = {
                    'filename': json_file.name,
                    'size': file_stat.st_size,
                    'created_time': file_stat.st_ctime,
                    'modified_time': file_stat.st_mtime
                }
                
                # 尝试读取文件内容获取更多信息
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        # 提取关键词和笔记数量
                        if isinstance(data, dict):
                            file_info['keyword'] = data.get('query', '未知')
                            notes = data.get('notes', [])
                            file_info['note_count'] = len(notes)

                            # 统计预期评论总数
                            total_expected_comments = 0
                            for note in notes:
                                interact_info = note.get('interact_info', {})
                                comment_count_str = interact_info.get('comment_count', '0')
                                try:
                                    # 将字符串转为整数（去掉可能的逗号等）
                                    comment_count = int(str(comment_count_str).replace(',', ''))
                                    total_expected_comments += comment_count
                                except:
                                    pass
                            file_info['total_expected_comments'] = total_expected_comments

                        elif isinstance(data, list):
                            file_info['note_count'] = len(data)
                            # 尝试从文件名提取关键词
                            if 'search_' in json_file.name:
                                parts = json_file.stem.split('_')
                                if len(parts) >= 2:
                                    file_info['keyword'] = parts[1]

                            # 统计预期评论总数
                            total_expected_comments = 0
                            for note in data:
                                interact_info = note.get('interact_info', {})
                                comment_count_str = interact_info.get('comment_count', '0')
                                try:
                                    comment_count = int(str(comment_count_str).replace(',', ''))
                                    total_expected_comments += comment_count
                                except:
                                    pass
                            file_info['total_expected_comments'] = total_expected_comments
                except:
                    file_info['note_count'] = 0
                    file_info['keyword'] = '未知'
                    file_info['total_expected_comments'] = 0
                
                files_info.append(file_info)
                
            except Exception as e:
                logger.warning(f"处理文件 {json_file} 时出错: {e}")
                continue
        
        # 按创建时间排序（最新的在前）
        files_info.sort(key=lambda x: x['created_time'], reverse=True)
        
        return jsonify({
            'success': True,
            'files': files_info,
            'total': len(files_info)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取文件列表失败: {str(e)}'
        }), 500

@app.route('/api/view-json/<filename>')
def view_json(filename):
    """查看JSON文件内容"""
    try:
        # 安全检查：确保文件名不包含路径遍历
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'message': '非法文件名'
            }), 400
        
        file_path = Path(SEARCH_RESULTS_DIR) / filename
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'message': '文件不存在'
            }), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        return jsonify({
            'success': True,
            'content': content,
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'读取文件失败: {str(e)}'
        }), 500

@app.route('/api/parse-json', methods=['POST'])
def parse_json():
    """解析JSON文件并获取完整数据"""
    try:
        data = request.json
        files_to_parse = data.get('files', [])
        save_format = data.get('save_format', 'all')
        include_comments = data.get('include_comments', True)
        download_media = data.get('download_media', True)
        output_name = data.get('output_name', '')
        # 新增参数
        min_completion_rate = data.get('min_completion_rate', 0.9)
        force_retry = data.get('force_retry', False)
        resume_incomplete = data.get('resume_incomplete', False)

        logger.info(f"开始解析任务: 文件数={len(files_to_parse)}, 格式={save_format}, 评论={include_comments}, 媒体={download_media}")

        if not files_to_parse:
            return jsonify({
                'success': False,
                'message': '没有选择要解析的文件'
            }), 400

        # 创建解析器实例，传入Cookie池
        parser = JsonToFullData(cookie_pool=cookie_pool)
        logger.info(f"解析器已初始化，Cookie池状态: {len(cookie_pool.accounts)} 个账号")

        # 统计结果
        results = {
            'success_count': 0,
            'failed_count': 0,
            'failed_files': [],
            'output_paths': []
        }

        # 批量处理文件
        for filename in files_to_parse:
            try:
                logger.info(f"正在处理文件: {filename}")
                json_path = os.path.join(SEARCH_RESULTS_DIR, filename)

                if not os.path.exists(json_path):
                    logger.error(f"文件不存在: {filename}")
                    results['failed_count'] += 1
                    results['failed_files'].append({
                        'filename': filename,
                        'error': '文件不存在'
                    })
                    continue

                # 生成输出目录名
                if output_name:
                    output_dir = output_name
                else:
                    # 从文件名提取信息作为输出目录名
                    base_name = Path(filename).stem
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_dir = f"parsed_{base_name}_{timestamp}"

                # 检查Cookie池是否有可用账号
                if len(cookie_pool.accounts) == 0:
                    logger.error(f"Cookie池中没有可用账号")
                    results['failed_count'] += 1
                    results['failed_files'].append({
                        'filename': filename,
                        'error': '没有可用的Cookie账号，请检查号池'
                    })
                    continue

                logger.info(f"开始解析文件，Cookie池将自动重试所有账号")

                # 调用解析函数（内部会自动使用Cookie池重试）
                try:
                    success, message, stats = parser.process_json_to_full_data(
                        json_file_path=json_path,
                        cookies_str=None,  # 不再需要手动传Cookie，由Cookie池管理
                        output_dir=output_dir,
                        include_comments=include_comments,
                        download_media=download_media,
                        save_format=save_format,
                        min_completion_rate=min_completion_rate,
                        force_retry=force_retry,
                        resume_incomplete=resume_incomplete
                    )

                    if success:
                        notes_count = stats.get('total_notes', 0) if isinstance(stats, dict) else 1
                        comments_count = stats.get('total_comments', 0)
                        logger.info(f"文件 {filename} 解析成功: 共{notes_count}条笔记, {comments_count}条评论")
                    else:
                        logger.error(f"文件 {filename} 解析失败: {message}")

                except Exception as e:
                    logger.error(f"文件 {filename} 解析异常: {e}")
                    success = False
                    message = str(e)

                if success:
                    results['success_count'] += 1
                    results['output_paths'].append(output_dir)
                else:
                    results['failed_count'] += 1
                    results['failed_files'].append({
                        'filename': filename,
                        'error': message
                    })
                    
            except Exception as e:
                results['failed_count'] += 1
                results['failed_files'].append({
                    'filename': filename,
                    'error': str(e)
                })

        # 返回结果
        logger.info(f"解析任务完成: 成功 {results['success_count']} 个, 失败 {results['failed_count']} 个")
        return jsonify({
            'success': True,
            'results': results,
            'message': f'处理完成: 成功 {results["success_count"]} 个, 失败 {results["failed_count"]} 个'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'解析过程出错: {str(e)}'
        }), 500

@app.route('/api/delete-json', methods=['POST'])
def delete_json():
    """删除JSON文件"""
    try:
        data = request.json
        files_to_delete = data.get('files', [])
        
        if not files_to_delete:
            return jsonify({
                'success': False,
                'message': '没有选择要删除的文件'
            }), 400
        
        deleted_count = 0
        failed_files = []
        
        for filename in files_to_delete:
            try:
                # 安全检查
                if '..' in filename or '/' in filename or '\\' in filename:
                    failed_files.append({
                        'filename': filename,
                        'error': '非法文件名'
                    })
                    continue
                
                file_path = Path(SEARCH_RESULTS_DIR) / filename
                
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
                else:
                    failed_files.append({
                        'filename': filename,
                        'error': '文件不存在'
                    })
                    
            except Exception as e:
                failed_files.append({
                    'filename': filename,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'failed_files': failed_files,
            'message': f'删除完成: 成功 {deleted_count} 个, 失败 {len(failed_files)} 个'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'删除过程出错: {str(e)}'
        }), 500

@app.route('/api/system-info')
def system_info():
    """获取系统信息"""
    try:
        # 统计信息
        search_dir = Path(SEARCH_RESULTS_DIR)
        json_files = list(search_dir.glob('*.json')) if search_dir.exists() else []
        
        total_notes = 0
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        notes = data.get('notes', [])
                        total_notes += len(notes)
                    elif isinstance(data, list):
                        total_notes += len(data)
            except:
                continue
        
        return jsonify({
            'success': True,
            'info': {
                'total_json_files': len(json_files),
                'total_notes': total_notes,
                'cookies_configured': bool(cookies_str),
                'base_path': base_path,
                'search_results_dir': str(search_dir.absolute()) if search_dir.exists() else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取系统信息失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/status')
def get_pool_status():
    """获取Cookie池状态"""
    try:
        status = cookie_pool.get_pool_status()
        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取号池状态失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/add', methods=['POST'])
def add_cookie():
    """添加Cookie账号"""
    try:
        data = request.json
        cookie_str = data.get('cookie_str', '')
        name = data.get('name', '')
        remark = data.get('remark', '')

        if not cookie_str:
            return jsonify({
                'success': False,
                'message': 'Cookie不能为空'
            }), 400

        success = cookie_pool.add_account(cookie_str, name, remark)

        if success:
            logger.info(f"添加Cookie账号成功: {name}")
            return jsonify({
                'success': True,
                'message': '账号添加成功'
            })
        else:
            logger.warning(f"添加Cookie账号失败 (已存在): {name}")
            return jsonify({
                'success': False,
                'message': '账号已存在'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'添加账号失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/remove/<cookie_id>', methods=['DELETE'])
def remove_cookie(cookie_id):
    """移除Cookie账号"""
    try:
        success = cookie_pool.remove_account(cookie_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '账号移除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '账号不存在'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'移除账号失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/reset/<cookie_id>', methods=['POST'])
def reset_cookie(cookie_id):
    """重置Cookie账号状态"""
    try:
        cookie_pool.reset_account(cookie_id)
        return jsonify({
            'success': True,
            'message': '账号重置成功'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'重置账号失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/strategy', methods=['POST'])
def set_strategy():
    """设置轮换策略"""
    try:
        data = request.json
        strategy = data.get('strategy', 'round_robin')
        
        if strategy not in ['round_robin', 'random', 'least_used']:
            return jsonify({
                'success': False,
                'message': '无效的策略类型'
            }), 400
        
        cookie_pool.set_strategy(strategy)
        return jsonify({
            'success': True,
            'message': f'策略已设置为: {strategy}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'设置策略失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/batch-add', methods=['POST'])
def batch_add_cookies():
    """批量添加Cookie"""
    try:
        data = request.json
        cookies_text = data.get('cookies_text', '')
        
        if not cookies_text:
            return jsonify({
                'success': False,
                'message': '内容不能为空'
            }), 400
        
        added_count = 0
        lines = cookies_text.strip().split('\n')
        
        for line in lines:
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
            
            if cookie_pool.add_account(cookie_str.strip(), name, remark):
                added_count += 1
        
        return jsonify({
            'success': True,
            'message': f'成功添加 {added_count} 个账号',
            'added_count': added_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'批量添加失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/settings', methods=['POST'])
def update_pool_settings():
    """更新池设置"""
    try:
        data = request.json
        daily_limit = data.get('daily_limit')
        min_interval = data.get('min_interval')
        
        if daily_limit is not None:
            daily_limit = int(daily_limit)
            if daily_limit < 1 or daily_limit > 1000:
                return jsonify({
                    'success': False,
                    'message': '每日限制必须在1-1000之间'
                }), 400
        
        if min_interval is not None:
            min_interval = int(min_interval)
            if min_interval < 1 or min_interval > 60:
                return jsonify({
                    'success': False,
                    'message': '最小间隔必须在1-60秒之间'
                }), 400
        
        # 更新所有账号的设置
        cookie_pool.update_all_settings(daily_limit, min_interval)
        
        return jsonify({
            'success': True,
            'message': '设置已保存'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'保存设置失败: {str(e)}'
        }), 500

@app.route('/api/cookie-pool/account/<cookie_id>/settings', methods=['POST'])
def update_account_settings(cookie_id):
    """更新单个账号设置"""
    try:
        data = request.json
        daily_limit = data.get('daily_limit')
        min_interval = data.get('min_interval')

        if daily_limit is not None:
            daily_limit = int(daily_limit)
        if min_interval is not None:
            min_interval = int(min_interval)

        success = cookie_pool.update_account_settings(cookie_id, daily_limit, min_interval)

        if success:
            return jsonify({
                'success': True,
                'message': '账号设置已更新'
            })
        else:
            return jsonify({
                'success': False,
                'message': '账号不存在'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新账号设置失败: {str(e)}'
        }), 500

@app.route('/api/list-parsed-dirs')
def list_parsed_dirs():
    """列出所有已解析的目录及其进度信息"""
    try:
        parsed_dirs = []

        # 查找所有parsed开头的目录
        for item in os.listdir('.'):
            if item.startswith('parsed_') and os.path.isdir(item):
                progress_file = os.path.join(item, 'progress.json')
                dir_info = {
                    'dirname': item,
                    'has_progress': os.path.exists(progress_file),
                    'created_time': os.path.getctime(item)
                }

                # 如果有进度文件，读取进度信息
                if dir_info['has_progress']:
                    try:
                        with open(progress_file, 'r', encoding='utf-8') as f:
                            progress_data = json.load(f)
                            dir_info['progress'] = {
                                'task_id': progress_data.get('task_id'),
                                'json_source': progress_data.get('json_source'),
                                'start_time': progress_data.get('start_time'),
                                'last_update': progress_data.get('last_update'),
                                'total_notes': progress_data.get('total_notes', 0),
                                'statistics': progress_data.get('statistics', {})
                            }
                    except Exception as e:
                        logger.warning(f"读取进度文件失败: {progress_file}, 错误: {e}")
                        dir_info['progress'] = None

                parsed_dirs.append(dir_info)

        # 按创建时间排序（最新的在前）
        parsed_dirs.sort(key=lambda x: x['created_time'], reverse=True)

        return jsonify({
            'success': True,
            'directories': parsed_dirs,
            'total': len(parsed_dirs)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取解析目录列表失败: {str(e)}'
        }), 500

@app.route('/api/list-all-notes')
def list_all_notes():
    """获取所有JSON文件中的笔记及其进度信息"""
    try:
        all_notes = []
        search_dir = Path(SEARCH_RESULTS_DIR)

        if not search_dir.exists():
            return jsonify({
                'success': True,
                'notes': [],
                'message': 'search_results目录不存在'
            })

        # 1. 先收集所有parsed目录的进度信息
        progress_data = {}
        for item in os.listdir('.'):
            if item.startswith('parsed_') and os.path.isdir(item):
                progress_file = os.path.join(item, 'progress.json')
                if os.path.exists(progress_file):
                    try:
                        with open(progress_file, 'r', encoding='utf-8') as f:
                            prog = json.load(f)
                            # 保存这个输出目录的进度数据
                            progress_data[item] = prog
                    except:
                        pass

        # 2. 遍历所有JSON文件，提取笔记信息
        for json_file in search_dir.glob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 提取笔记列表
                notes = []
                if isinstance(data, dict):
                    notes = data.get('notes', [])
                elif isinstance(data, list):
                    notes = data

                # 处理每个笔记
                for note in notes:
                    note_id = note.get('note_id', '')
                    if not note_id:
                        continue

                    # 提取基本信息
                    title = note.get('title', '未知标题')
                    note_url = note.get('note_url', '')
                    user_nickname = note.get('user_nickname', '')

                    # 提取预期评论数
                    interact_info = note.get('interact_info', {})
                    expected_comments_str = interact_info.get('comment_count', '0')
                    try:
                        expected_comments = int(str(expected_comments_str).replace(',', ''))
                    except:
                        expected_comments = 0

                    # 查找该笔记的进度信息（遍历所有progress_data）
                    fetched_comments = 0
                    status = 'pending'
                    completion_rate = 0
                    output_dir = None
                    last_cursor = ''

                    # 实时进度信息（初始化）
                    realtime_progress = {
                        'current_page': 0,
                        'crawl_speed': 0,
                        'latest_error': None,
                        'latest_warning': None
                    }

                    for dir_name, prog in progress_data.items():
                        notes_progress = prog.get('notes_progress', {})
                        if note_id in notes_progress:
                            note_prog = notes_progress[note_id]
                            status = note_prog.get('status', 'pending')
                            comments = note_prog.get('comments', {})
                            fetched_comments = comments.get('total_fetched', 0)
                            last_cursor = comments.get('last_cursor', '')
                            output_dir = dir_name

                            # ========== 提取实时进度信息 ==========
                            realtime_progress['current_page'] = comments.get('current_page', 0)
                            realtime_progress['crawl_speed'] = comments.get('crawl_speed', 0)

                            # 提取最新的错误和警告
                            errors = comments.get('errors', [])
                            warnings = comments.get('warnings', [])
                            if errors:
                                realtime_progress['latest_error'] = errors[-1].get('message', '')
                            if warnings:
                                realtime_progress['latest_warning'] = warnings[-1].get('message', '')

                            # 计算完成度
                            if expected_comments > 0:
                                completion_rate = round((fetched_comments / expected_comments) * 100, 1)

                                # 智能状态判断：如果预期评论数>0但已获取=0，且标记为完成，说明数据有问题
                                if status == 'completed' and fetched_comments == 0:
                                    status = 'pending'  # 重置为待处理
                                    completion_rate = 0
                                # 如果获取了部分评论但未达到100%，状态应该是processing
                                elif status == 'completed' and completion_rate < 100:
                                    status = 'processing'
                            else:
                                completion_rate = 100 if comments.get('completed', False) else 0
                            break

                    # 组装笔记信息
                    note_info = {
                        'note_id': note_id,
                        'title': title,
                        'user_nickname': user_nickname,
                        'note_url': note_url,
                        'source_file': json_file.name,
                        'expected_comments': expected_comments,
                        'fetched_comments': fetched_comments,
                        'completion_rate': completion_rate,
                        'status': status,
                        'output_dir': output_dir,
                        'has_cursor': bool(last_cursor),
                        'realtime_progress': realtime_progress  # ✅ 添加实时进度信息
                    }

                    all_notes.append(note_info)

            except Exception as e:
                logger.warning(f"处理文件 {json_file} 时出错: {e}")
                continue

        # 按状态排序：processing > failed > pending > completed
        status_order = {'processing': 0, 'failed': 1, 'pending': 2, 'completed': 3}
        all_notes.sort(key=lambda x: (status_order.get(x['status'], 99), x['source_file']))

        return jsonify({
            'success': True,
            'notes': all_notes,
            'total': len(all_notes)
        })

    except Exception as e:
        logger.error(f"获取笔记列表失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取笔记列表失败: {str(e)}'
        }), 500

@app.route('/api/parse-single-note', methods=['POST'])
def parse_single_note():
    """解析单个笔记"""
    try:
        data = request.json
        note_id = data.get('note_id')
        source_file = data.get('source_file')
        include_comments = data.get('include_comments', True)
        download_media = data.get('download_media', True)
        save_format = data.get('save_format', 'all')
        # 新增参数
        min_completion_rate = data.get('min_completion_rate', 0.9)
        force_retry = data.get('force_retry', False)
        resume_incomplete = data.get('resume_incomplete', False)

        logger.info(f"开始解析单个笔记: note_id={note_id}, source_file={source_file}")

        if not note_id or not source_file:
            return jsonify({
                'success': False,
                'message': '缺少必要参数: note_id 或 source_file'
            }), 400

        # 1. 从源文件中读取笔记信息
        json_path = os.path.join(SEARCH_RESULTS_DIR, source_file)
        if not os.path.exists(json_path):
            return jsonify({
                'success': False,
                'message': f'源文件不存在: {source_file}'
            }), 404

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            # 查找目标笔记
            notes = file_data.get('notes', []) if isinstance(file_data, dict) else file_data
            target_note = None
            for note in notes:
                if note.get('note_id') == note_id:
                    target_note = note
                    break

            if not target_note:
                return jsonify({
                    'success': False,
                    'message': f'在文件中未找到笔记: {note_id}'
                }), 404

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'读取源文件失败: {str(e)}'
            }), 500

        # 2. 确定或创建输出目录
        # 优先查找是否已有这个笔记的进度
        output_dir = None
        for item in os.listdir('.'):
            if item.startswith('parsed_') and os.path.isdir(item):
                progress_file = os.path.join(item, 'progress.json')
                if os.path.exists(progress_file):
                    try:
                        with open(progress_file, 'r', encoding='utf-8') as f:
                            prog = json.load(f)
                            if note_id in prog.get('notes_progress', {}):
                                output_dir = item
                                logger.info(f"找到现有进度目录: {output_dir}")
                                break
                    except:
                        pass

        # 如果没有找到，创建新的输出目录
        if not output_dir:
            base_name = Path(source_file).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"parsed_{base_name}_{timestamp}"
            logger.info(f"创建新的输出目录: {output_dir}")

        # 3. 检查Cookie池
        if len(cookie_pool.accounts) == 0:
            return jsonify({
                'success': False,
                'message': 'Cookie池中没有可用账号，请先添加Cookie'
            }), 400

        # 4. ✨ 直接传递笔记数据（无需创建临时文件）
        from json_to_full_data import JsonToFullData
        parser = JsonToFullData(cookie_pool=cookie_pool)

        logger.info(f"📋 直接处理笔记数据: {note_id}")

        success, message, stats = parser.process_json_to_full_data(
            note_data_list=[target_note],  # ✨ 直接传递笔记数据
            cookies_str=None,  # 使用Cookie池
            output_dir=output_dir,
            include_comments=include_comments,
            download_media=download_media,
            save_format=save_format,
            min_completion_rate=min_completion_rate,
            force_retry=force_retry,
            resume_incomplete=resume_incomplete
        )

        if success:
            logger.info(f"✅ 单笔记解析成功: {note_id}")
            return jsonify({
                'success': True,
                'message': f'笔记解析成功',
                'note_id': note_id,
                'output_dir': output_dir,
                'stats': stats
            })
        else:
            logger.error(f"❌ 单笔记解析失败: {note_id}, 原因: {message}")
            return jsonify({
                'success': False,
                'message': f'解析失败: {message}'
            }), 500

    except Exception as e:
        logger.error(f"解析单笔记异常: {e}")
        return jsonify({
            'success': False,
            'message': f'解析过程出错: {str(e)}'
        }), 500

@app.route('/api/progress/<dirname>')
def get_progress(dirname):
    """获取指定目录的进度详情"""
    try:
        # 安全检查
        if '..' in dirname or '/' in dirname or '\\' in dirname:
            return jsonify({
                'success': False,
                'message': '非法目录名'
            }), 400

        progress_file = os.path.join(dirname, 'progress.json')

        if not os.path.exists(progress_file):
            return jsonify({
                'success': False,
                'message': '进度文件不存在'
            }), 404

        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)

        # 读取源JSON文件获取真实的预期评论数
        json_source = progress_data.get('json_source', '')
        expected_comments_map = {}  # note_id -> expected_comments

        if json_source and os.path.exists(json_source):
            try:
                with open(json_source, 'r', encoding='utf-8') as f:
                    source_data = json.load(f)
                    source_notes = []
                    if isinstance(source_data, dict):
                        source_notes = source_data.get('notes', [])
                    elif isinstance(source_data, list):
                        source_notes = source_data

                    for note in source_notes:
                        note_id = note.get('note_id', '')
                        interact_info = note.get('interact_info', {})
                        comment_count_str = interact_info.get('comment_count', '0')
                        try:
                            expected_comments_map[note_id] = int(str(comment_count_str).replace(',', ''))
                        except:
                            expected_comments_map[note_id] = 0
            except:
                pass

        # 整理每个笔记的进度信息
        notes_progress = progress_data.get('notes_progress', {})
        notes_detail = []

        # 重新统计真实状态
        real_statistics = {
            'completed': 0,
            'failed': 0,
            'processing': 0,
            'pending': 0,
            'skipped': 0
        }

        for note_id, note_info in notes_progress.items():
            # 提取评论进度
            comments = note_info.get('comments', {})
            total_fetched = comments.get('total_fetched', 0)

            # 使用真实的预期评论数（优先从源文件读取）
            total_expected = expected_comments_map.get(note_id, comments.get('total_expected', 0))

            # 获取原始状态
            status = note_info.get('status', 'unknown')

            # 计算完成度
            if total_expected > 0:
                completion_rate = (total_fetched / total_expected) * 100

                # 智能状态判断（与list_all_notes保持一致）
                if status == 'completed' and total_fetched == 0:
                    status = 'pending'  # 重置为待处理
                    completion_rate = 0
                elif status == 'completed' and completion_rate < 100:
                    status = 'processing'
            else:
                completion_rate = 100 if comments.get('completed', False) else 0

            # 统计真实状态
            if status in real_statistics:
                real_statistics[status] += 1

            notes_detail.append({
                'note_id': note_id,
                'note_url': note_info.get('note_url', ''),
                'status': status,  # 使用修正后的状态
                'error_message': note_info.get('error_message'),
                'start_time': note_info.get('start_time'),
                'end_time': note_info.get('end_time'),
                'basic_info_saved': note_info.get('basic_info_saved', False),
                'comments': {
                    'enabled': comments.get('enabled', False),
                    'total_expected': total_expected,  # 使用真实值
                    'total_fetched': total_fetched,
                    'completion_rate': round(completion_rate, 1),
                    'completed': comments.get('completed', False),
                    'last_cursor': comments.get('last_cursor', '')
                },
                'media': note_info.get('media', {})
            })

        # 按状态排序：processing > failed > pending > completed
        status_order = {'processing': 0, 'failed': 1, 'pending': 2, 'completed': 3}
        notes_detail.sort(key=lambda x: status_order.get(x['status'], 99))

        # 用修正后的统计替换原始统计
        progress_data['statistics'] = real_statistics

        return jsonify({
            'success': True,
            'progress': progress_data,
            'notes_detail': notes_detail
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'读取进度信息失败: {str(e)}'
        }), 500

def main():
    """主函数"""
    # 确保必要的目录存在
    os.makedirs(SEARCH_RESULTS_DIR, exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    # 启动Flask应用
    logger.info("=" * 50)
    logger.info("🚀 小红书搜索结果管理系统启动中...")
    logger.info("=" * 50)
    logger.info(f"📁 搜索结果目录: {os.path.abspath(SEARCH_RESULTS_DIR)}")
    logger.info(f"🔧 Cookie配置状态: {'已配置' if cookies_str else '未配置'}")
    logger.info(f"📝 日志文件: logs/web_interface.log")
    logger.info("=" * 50)
    logger.info("🌐 访问地址: http://localhost:5001")
    logger.info("💡 提示: 按 Ctrl+C 停止服务")
    logger.info("=" * 50)

    app.run(debug=True, host='0.0.0.0', port=5001)

if __name__ == '__main__':
    main()