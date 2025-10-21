# encoding: utf-8
"""
小红书数据爬取 Web 应用
Flask 后端API服务，提供前端界面和API接口
"""

import os
import json
import time
import threading
import uuid
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, Response
from flask_cors import CORS
from loguru import logger

# 导入爬虫模块
from search_to_json import SearchToJson
from json_to_full_data import JsonToFullData
from xhs_utils.common_util import init

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量存储任务状态
search_tasks = {}  # 搜索任务状态
parse_tasks = {}   # 解析任务状态

# 初始化爬虫实例
search_spider = SearchToJson()
full_data_processor = JsonToFullData()

# 初始化cookies
try:
    cookies_str, base_path = init()
    logger.info("✅ Cookie初始化成功")
except Exception as e:
    cookies_str = ""
    base_path = {"media": "datas/media_datas", "excel": "datas/excel_datas"}
    logger.error(f"❌ Cookie初始化失败: {e}")


def background_search_task(task_id, query, require_num, search_params):
    """
    后台执行搜索任务
    """
    try:
        search_tasks[task_id]['status'] = 'running'
        search_tasks[task_id]['message'] = '正在搜索笔记...'
        
        # 执行搜索
        success, msg, notes = search_spider.search_notes_to_json(
            query=query,
            require_num=require_num,
            cookies_str=cookies_str,
            **search_params
        )
        
        if success:
            search_tasks[task_id]['status'] = 'completed'
            search_tasks[task_id]['message'] = f'搜索完成，找到 {len(notes)} 篇笔记'
            search_tasks[task_id]['result'] = {
                'notes': notes,
                'total_count': len(notes),
                'json_file': msg.split('保存到 ')[-1] if '保存到' in msg else ''
            }
        else:
            search_tasks[task_id]['status'] = 'failed'
            search_tasks[task_id]['message'] = f'搜索失败: {msg}'
            
    except Exception as e:
        search_tasks[task_id]['status'] = 'failed'
        search_tasks[task_id]['message'] = f'搜索异常: {str(e)}'


def background_parse_task(task_id, json_file_path, parse_params):
    """
    后台执行解析任务
    """
    try:
        parse_tasks[task_id]['status'] = 'running'
        parse_tasks[task_id]['message'] = '正在解析笔记详细信息...'
        parse_tasks[task_id]['progress'] = 0
        
        # 先解析JSON文件获取笔记列表
        success, msg, note_urls = full_data_processor.parse_json_file(json_file_path)
        if not success:
            parse_tasks[task_id]['status'] = 'failed'
            parse_tasks[task_id]['message'] = f'解析JSON失败: {msg}'
            return
        
        total_notes = len(note_urls)
        successful_notes = []
        failed_notes = []
        
        # 逐个处理笔记
        for i, note_url in enumerate(note_urls):
            try:
                parse_tasks[task_id]['progress'] = int((i / total_notes) * 100)
                parse_tasks[task_id]['message'] = f'正在处理第 {i+1}/{total_notes} 个笔记...'
                
                # 获取笔记完整信息
                note_success, note_msg, full_note_info = full_data_processor.get_note_full_info(
                    note_url, cookies_str, parse_params.get('proxies'), 
                    parse_params.get('include_comments', True)
                )
                
                if note_success and full_note_info:
                    successful_notes.append(full_note_info)
                else:
                    failed_notes.append({'url': note_url, 'error': note_msg})
                
                # 添加延时避免请求过快
                time.sleep(1)
                
            except Exception as e:
                failed_notes.append({'url': note_url, 'error': str(e)})
                logger.error(f'处理笔记失败: {e}')
        
        # 保存结果
        if successful_notes:
            # 生成输出目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"parse_results_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存汇总数据
            summary_data = {
                'process_info': {
                    'source_json': json_file_path,
                    'total_notes': total_notes,
                    'successful_notes': len(successful_notes),
                    'failed_notes': len(failed_notes),
                    'process_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                'successful_notes': successful_notes,
                'failed_notes': failed_notes
            }
            
            # 保存汇总JSON
            summary_file = os.path.join(output_dir, "summary_all_notes.json")
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)
            
            # 保存单个笔记文件
            for note in successful_notes:
                note_file = os.path.join(output_dir, f"note_{note['note_id']}_full.json")
                with open(note_file, 'w', encoding='utf-8') as f:
                    json.dump(note, f, ensure_ascii=False, indent=2)
            
            parse_tasks[task_id]['result'] = {
                'total_notes': total_notes,
                'successful_notes': len(successful_notes),
                'failed_notes': len(failed_notes),
                'output_directory': output_dir,
                'summary_file': summary_file
            }
        
        parse_tasks[task_id]['status'] = 'completed'
        parse_tasks[task_id]['progress'] = 100
        parse_tasks[task_id]['message'] = f'解析完成！成功: {len(successful_notes)}, 失败: {len(failed_notes)}'
        
    except Exception as e:
        parse_tasks[task_id]['status'] = 'failed'
        parse_tasks[task_id]['message'] = f'解析异常: {str(e)}'
        logger.error(f'解析任务异常: {e}')


@app.route('/')
def index():
    """
    主页面
    """
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def api_search():
    """
    搜索笔记API
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        require_num = int(data.get('require_num', 20))
        
        if not query:
            return jsonify({
                'success': False,
                'message': '请输入搜索关键词'
            })
        
        if require_num <= 0 or require_num > 100:
            return jsonify({
                'success': False,
                'message': '搜索数量必须在1-100之间'
            })
        
        # 搜索参数
        search_params = {
            'sort_type_choice': int(data.get('sort_type', 0)),
            'note_type': int(data.get('note_type', 0)),
            'note_time': int(data.get('note_time', 0)),
            'note_range': int(data.get('note_range', 0)),
            'pos_distance': int(data.get('pos_distance', 0)),
            'geo': data.get('geo'),
            'proxies': data.get('proxies')
        }
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        search_tasks[task_id] = {
            'status': 'pending',
            'message': '任务已创建，等待执行...',
            'query': query,
            'require_num': require_num,
            'create_time': datetime.now().isoformat(),
            'result': None
        }
        
        # 启动后台任务
        thread = threading.Thread(
            target=background_search_task,
            args=(task_id, query, require_num, search_params)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': '搜索任务已启动',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"搜索API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        })


@app.route('/api/search/status/<task_id>')
def api_search_status(task_id):
    """
    查询搜索任务状态
    """
    if task_id not in search_tasks:
        return jsonify({
            'success': False,
            'message': '任务不存在'
        })
    
    task = search_tasks[task_id]
    return jsonify({
        'success': True,
        'task': {
            'task_id': task_id,
            'status': task['status'],
            'message': task['message'],
            'query': task['query'],
            'require_num': task['require_num'],
            'create_time': task['create_time'],
            'result': task['result']
        }
    })


@app.route('/api/parse', methods=['POST'])
def api_parse():
    """
    解析笔记详细信息API
    """
    try:
        data = request.get_json()
        json_file_path = data.get('json_file_path', '').strip()
        
        if not json_file_path or not os.path.exists(json_file_path):
            return jsonify({
                'success': False,
                'message': 'JSON文件路径无效'
            })
        
        # 解析参数
        parse_params = {
            'include_comments': data.get('include_comments', True),
            'download_media': data.get('download_media', True),
            'save_format': data.get('save_format', 'json'),
            'proxies': data.get('proxies')
        }
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        parse_tasks[task_id] = {
            'status': 'pending',
            'message': '任务已创建，等待执行...',
            'json_file_path': json_file_path,
            'create_time': datetime.now().isoformat(),
            'result': None
        }
        
        # 启动后台任务
        thread = threading.Thread(
            target=background_parse_task,
            args=(task_id, json_file_path, parse_params)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': '解析任务已启动',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"解析API错误: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        })


@app.route('/api/parse/status/<task_id>')
def api_parse_status(task_id):
    """
    查询解析任务状态
    """
    if task_id not in parse_tasks:
        return jsonify({
            'success': False,
            'message': '任务不存在'
        })
    
    task = parse_tasks[task_id]
    return jsonify({
        'success': True,
        'task': {
            'task_id': task_id,
            'status': task['status'],
            'message': task['message'],
            'progress': task.get('progress', 0),
            'json_file_path': task['json_file_path'],
            'create_time': task['create_time'],
            'result': task['result']
        }
    })


@app.route('/api/single_note_detail', methods=['POST'])
def api_single_note_detail():
    """
    获取单个笔记详细信息API（实时解析）
    """
    try:
        data = request.get_json()
        note_url = data.get('note_url', '').strip()
        include_comments = data.get('include_comments', True)
        
        if not note_url:
            return jsonify({
                'success': False,
                'message': '笔记URL不能为空'
            })
        
        # 实时获取笔记详情
        success, msg, note_detail = full_data_processor.get_note_full_info(
            note_url, cookies_str, None, include_comments
        )
        
        if success and note_detail:
            return jsonify({
                'success': True,
                'note_detail': note_detail
            })
        else:
            return jsonify({
                'success': False,
                'message': f'获取笔记详情失败: {msg}'
            })
            
    except Exception as e:
        logger.error(f"获取单个笔记详情错误: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        })


@app.route('/api/note_detail')
def api_note_detail():
    """
    获取笔记详细信息API
    """
    try:
        note_id = request.args.get('note_id')
        output_dir = request.args.get('output_dir')
        
        if not note_id or not output_dir:
            return jsonify({
                'success': False,
                'message': '参数缺失'
            })
        
        # 查找笔记的JSON文件
        note_json_file = os.path.join(output_dir, f"note_{note_id}_full.json")
        
        if not os.path.exists(note_json_file):
            return jsonify({
                'success': False,
                'message': '笔记详情文件不存在'
            })
        
        # 读取笔记详情
        with open(note_json_file, 'r', encoding='utf-8') as f:
            note_detail = json.load(f)
        
        return jsonify({
            'success': True,
            'note_detail': note_detail
        })
        
    except Exception as e:
        logger.error(f"获取笔记详情错误: {e}")
        return jsonify({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        })


@app.route('/api/system_status')
def api_system_status():
    """
    获取系统状态API
    """
    return jsonify({
        'success': True,
        'status': {
            'cookies_available': bool(cookies_str),
            'running_search_tasks': len([t for t in search_tasks.values() if t['status'] == 'running']),
            'running_parse_tasks': len([t for t in parse_tasks.values() if t['status'] == 'running']),
            'total_search_tasks': len(search_tasks),
            'total_parse_tasks': len(parse_tasks)
        }
    })


@app.route('/api/proxy_image')
def api_proxy_image():
    """
    图片代理API，解决小红书图片防盗链问题
    """
    try:
        image_url = request.args.get('url')
        if not image_url:
            return jsonify({
                'success': False,
                'message': '图片URL不能为空'
            }), 400
        
        # 设置小红书请求头，模拟正常浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }
        
        # 添加cookie如果可用
        if cookies_str:
            headers['Cookie'] = cookies_str
        
        # 请求图片
        response = requests.get(image_url, headers=headers, timeout=10, stream=True)
        
        if response.status_code == 200:
            # 返回图片数据
            return Response(
                response.content,
                content_type=response.headers.get('content-type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=3600',  # 缓存1小时
                    'Access-Control-Allow-Origin': '*'
                }
            )
        else:
            logger.error(f"图片请求失败: {response.status_code} - {image_url}")
            return jsonify({
                'success': False,
                'message': f'图片请求失败: {response.status_code}'
            }), response.status_code
            
    except Exception as e:
        logger.error(f"图片代理错误: {e}")
        return jsonify({
            'success': False,
            'message': f'代理错误: {str(e)}'
        }), 500


@app.route('/api/download/<path:filename>')
def api_download_file(filename):
    """
    文件下载API
    """
    try:
        file_path = os.path.join(os.getcwd(), filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({
                'success': False,
                'message': '文件不存在'
            }), 404
    except Exception as e:
        logger.error(f"文件下载错误: {e}")
        return jsonify({
            'success': False,
            'message': f'下载错误: {str(e)}'
        }), 500


if __name__ == '__main__':
    # 创建模板目录
    template_dir = 'templates'
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    # 创建静态文件目录
    static_dir = 'static'
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    
    logger.info("🚀 启动小红书数据爬取Web应用")
    logger.info("📱 访问地址: http://localhost:8888")

    app.run(debug=True, host='0.0.0.0', port=8888)