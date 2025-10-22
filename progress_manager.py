# encoding: utf-8
"""
进度管理器 - 支持断点续爬功能
"""

import json
import os
import re
import traceback
from datetime import datetime
from loguru import logger


class ProgressManager:
    """
    进度管理器类

    功能：
    - 记录每个笔记的处理进度
    - 支持笔记、评论、媒体文件三层断点
    - 提供进度查询和统计
    """

    def __init__(self, output_dir: str, json_source: str = None):
        """
        初始化进度管理器

        :param output_dir: 输出目录
        :param json_source: 源JSON文件路径
        """
        self.output_dir = output_dir
        self.progress_file = os.path.join(output_dir, "progress.json")
        self.progress_data = None

        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 加载或创建进度文件
        self._load_or_create_progress(json_source)

    def _load_or_create_progress(self, json_source: str = None):
        """加载现有进度文件或创建新的"""
        if os.path.exists(self.progress_file):
            # 加载现有进度
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.progress_data = json.load(f)
                logger.info(f"✅ 加载进度文件: {self.progress_file}")
                logger.info(f"   上次更新: {self.progress_data.get('last_update')}")
                stats = self.progress_data.get('statistics', {})
                logger.info(f"   已完成: {stats.get('completed', 0)}, "
                          f"失败: {stats.get('failed', 0)}, "
                          f"待处理: {stats.get('pending', 0)}")
            except Exception as e:
                logger.warning(f"加载进度文件失败: {e}，创建新的进度文件")
                self.progress_data = self._create_new_progress(json_source)
        else:
            # 创建新进度
            self.progress_data = self._create_new_progress(json_source)
            logger.info(f"📝 创建新的进度文件: {self.progress_file}")

    def _create_new_progress(self, json_source: str = None) -> dict:
        """创建新的进度数据结构"""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return {
            'task_id': task_id,
            'json_source': json_source or 'unknown',
            'output_dir': self.output_dir,
            'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'last_update': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_notes': 0,
            'notes_progress': {},
            'statistics': {
                'completed': 0,
                'failed': 0,
                'skipped': 0,
                'processing': 0,
                'pending': 0
            }
        }

    def save_progress(self):
        """保存进度到文件（增强版：添加重试机制和详细日志）"""
        max_retries = 3
        retry_delay = 0.1  # 100ms

        for attempt in range(max_retries):
            try:
                self.progress_data['last_update'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 先写入临时文件，再重命名（原子操作）
                temp_file = self.progress_file + '.tmp'
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.progress_data, f, ensure_ascii=False, indent=2)
                    f.flush()  # 确保写入磁盘
                    os.fsync(f.fileno())  # 强制同步到磁盘

                # 原子性重命名
                os.replace(temp_file, self.progress_file)

                # 验证写入成功
                if os.path.exists(self.progress_file):
                    file_size = os.path.getsize(self.progress_file)
                    if file_size > 0:
                        logger.debug(f"✅ 进度已保存: {self.progress_file} ({file_size} bytes)")
                        return True
                    else:
                        logger.warning(f"⚠️ 进度文件大小为0，重试中... ({attempt + 1}/{max_retries})")
                else:
                    logger.warning(f"⚠️ 进度文件不存在，重试中... ({attempt + 1}/{max_retries})")

            except Exception as e:
                logger.error(f"❌ 保存进度文件失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                logger.debug(f"错误详情: {traceback.format_exc()}")

                # 清理临时文件
                temp_file = self.progress_file + '.tmp'
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass

            # 等待后重试
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)

        logger.error(f"🔴 保存进度文件最终失败，已尝试 {max_retries} 次")
        return False

    def extract_note_id(self, note_url: str) -> str:
        """从URL中提取笔记ID"""
        match = re.search(r'/explore/([a-f0-9]+)', note_url)
        if match:
            return match.group(1)
        return None

    def is_note_completed(self, note_id: str) -> bool:
        """
        判断笔记是否已完成

        优先检查进度文件，如果没有则检查文件存在性
        """
        # 1. 检查进度文件
        if note_id in self.progress_data['notes_progress']:
            note_progress = self.progress_data['notes_progress'][note_id]
            return note_progress.get('status') == 'completed'

        # 2. 检查文件存在性（向后兼容）
        full_file = os.path.join(self.output_dir, f"note_{note_id}_full.json")
        if os.path.exists(full_file):
            # 文件存在但进度中没有，自动补充到进度
            self._补充已存在文件到进度(note_id)
            return True

        return False

    def _补充已存在文件到进度(self, note_id: str):
        """将已存在的文件补充到进度记录"""
        basic_file = os.path.join(self.output_dir, f"note_{note_id}_basic.json")
        comments_file = os.path.join(self.output_dir, f"note_{note_id}_comments.jsonl")
        full_file = os.path.join(self.output_dir, f"note_{note_id}_full.json")

        if note_id not in self.progress_data['notes_progress']:
            self.progress_data['notes_progress'][note_id] = {
                'status': 'completed',
                'note_url': 'unknown',
                'basic_info_saved': os.path.exists(basic_file),
                'comments': {
                    'enabled': os.path.exists(comments_file),
                    'completed': os.path.exists(comments_file)
                },
                'media': {
                    'enabled': False,
                    'completed': False
                },
                'end_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'error_message': None
            }
            self.progress_data['statistics']['completed'] += 1
            self.save_progress()
            logger.debug(f"补充已存在笔记到进度: {note_id}")

    def mark_note_processing(self, note_id: str, note_url: str):
        """标记笔记开始处理"""
        if note_id not in self.progress_data['notes_progress']:
            self.progress_data['notes_progress'][note_id] = {
                'status': 'processing',
                'note_url': note_url,
                'basic_info_saved': False,
                'comments': {
                    'enabled': False,
                    'total_expected': 0,
                    'total_fetched': 0,
                    'last_cursor': '',
                    'completed': False,
                    # ========== 实时进度字段 ==========
                    'current_page': 0,          # 当前正在爬取的页数
                    'crawl_speed': 0,           # 爬取速度（评论数/秒）
                    'errors': [],               # 错误列表
                    'warnings': [],             # 警告列表
                    'last_update_time': None    # 最后更新时间
                },
                'media': {
                    'enabled': False,
                    'images': {
                        'total': 0,
                        'downloaded': 0,
                        'urls': []
                    },
                    'videos': {
                        'total': 0,
                        'downloaded': 0,
                        'urls': []
                    },
                    'completed': False
                },
                'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'end_time': None,
                'error_message': None
            }
            self.progress_data['statistics']['processing'] += 1
            if self.progress_data['statistics']['pending'] > 0:
                self.progress_data['statistics']['pending'] -= 1
        else:
            # 重新处理失败的笔记
            self.progress_data['notes_progress'][note_id]['status'] = 'processing'
            self.progress_data['notes_progress'][note_id]['start_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.progress_data['notes_progress'][note_id]['error_message'] = None

            # 重置实时进度字段
            if 'comments' not in self.progress_data['notes_progress'][note_id]:
                self.progress_data['notes_progress'][note_id]['comments'] = {}
            comments = self.progress_data['notes_progress'][note_id]['comments']
            comments.update({
                'current_page': 0,
                'crawl_speed': 0,
                'errors': [],
                'warnings': [],
                'last_update_time': None
            })

            if self.progress_data['statistics']['failed'] > 0:
                self.progress_data['statistics']['failed'] -= 1
            self.progress_data['statistics']['processing'] += 1

        self.save_progress()

    def mark_note_completed(self, note_id: str, details: dict = None):
        """标记笔记完成"""
        if note_id in self.progress_data['notes_progress']:
            self.progress_data['notes_progress'][note_id]['status'] = 'completed'
            self.progress_data['notes_progress'][note_id]['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 更新详细信息
            if details:
                if 'comments' in details:
                    self.progress_data['notes_progress'][note_id]['comments'].update(details['comments'])
                if 'media' in details:
                    self.progress_data['notes_progress'][note_id]['media'].update(details['media'])

            # 更新统计
            if self.progress_data['statistics']['processing'] > 0:
                self.progress_data['statistics']['processing'] -= 1
            self.progress_data['statistics']['completed'] += 1

            self.save_progress()

    def mark_note_failed(self, note_id: str, error_message: str):
        """标记笔记失败"""
        if note_id in self.progress_data['notes_progress']:
            self.progress_data['notes_progress'][note_id]['status'] = 'failed'
            self.progress_data['notes_progress'][note_id]['error_message'] = error_message
            self.progress_data['notes_progress'][note_id]['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 更新统计
            if self.progress_data['statistics']['processing'] > 0:
                self.progress_data['statistics']['processing'] -= 1
            self.progress_data['statistics']['failed'] += 1

            self.save_progress()

    def update_basic_info(self, note_id: str, saved: bool = True):
        """更新基本信息保存状态"""
        if note_id in self.progress_data['notes_progress']:
            self.progress_data['notes_progress'][note_id]['basic_info_saved'] = saved
            self.save_progress()

    def update_comments_progress(self, note_id: str, total_expected: int = None,
                                 total_fetched: int = None, last_cursor: str = None,
                                 completed: bool = None, current_page: int = None,
                                 error: str = None, warning: str = None):
        """
        更新评论获取进度（支持实时进度）

        :param note_id: 笔记ID
        :param total_expected: 预期评论总数
        :param total_fetched: 已获取评论数
        :param last_cursor: 最后一个游标
        :param completed: 是否完成
        :param current_page: 当前页数
        :param error: 错误信息
        :param warning: 警告信息
        """
        if note_id in self.progress_data['notes_progress']:
            comments = self.progress_data['notes_progress'][note_id]['comments']

            # 更新基本进度
            if total_expected is not None:
                comments['total_expected'] = total_expected
            if total_fetched is not None:
                # 计算爬取速度
                old_fetched = comments.get('total_fetched', 0)
                last_update = comments.get('last_update_time')
                current_time = datetime.now()

                if last_update and old_fetched < total_fetched:
                    try:
                        last_time = datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S")
                        time_diff = (current_time - last_time).total_seconds()
                        if time_diff > 0:
                            comments_diff = total_fetched - old_fetched
                            comments['crawl_speed'] = round(comments_diff / time_diff, 2)
                    except:
                        pass

                comments['total_fetched'] = total_fetched
                comments['last_update_time'] = current_time.strftime("%Y-%m-%d %H:%M:%S")

            if last_cursor is not None:
                comments['last_cursor'] = last_cursor
            if completed is not None:
                comments['completed'] = completed
                if completed:
                    # 完成时重置实时字段
                    comments['current_page'] = 0
                    comments['crawl_speed'] = 0

            # 更新实时进度字段
            if current_page is not None:
                comments['current_page'] = current_page

            # 添加错误/警告信息
            if error:
                if 'errors' not in comments:
                    comments['errors'] = []
                comments['errors'].append({
                    'message': error,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                # 只保留最近10条错误
                comments['errors'] = comments['errors'][-10:]

            if warning:
                if 'warnings' not in comments:
                    comments['warnings'] = []
                comments['warnings'].append({
                    'message': warning,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                # 只保留最近10条警告
                comments['warnings'] = comments['warnings'][-10:]

            comments['enabled'] = True
            self.save_progress()

    def update_media_progress(self, note_id: str, media_type: str,
                             total: int = None, downloaded: int = None,
                             urls: list = None, completed: bool = None):
        """
        更新媒体文件下载进度

        :param media_type: 'images' 或 'videos'
        """
        if note_id in self.progress_data['notes_progress']:
            media = self.progress_data['notes_progress'][note_id]['media']

            if media_type in ['images', 'videos']:
                if total is not None:
                    media[media_type]['total'] = total
                if downloaded is not None:
                    media[media_type]['downloaded'] = downloaded
                if urls is not None:
                    media[media_type]['urls'] = urls

            if completed is not None:
                media['completed'] = completed

            media['enabled'] = True
            self.save_progress()

    def get_note_progress(self, note_id: str) -> dict:
        """获取笔记的进度信息"""
        return self.progress_data['notes_progress'].get(note_id, {})

    def get_pending_notes(self, all_note_urls: list) -> list:
        """
        获取待处理的笔记列表

        :param all_note_urls: 所有笔记URL列表
        :return: 待处理的笔记URL列表
        """
        # 更新总数
        self.progress_data['total_notes'] = len(all_note_urls)

        pending_notes = []
        completed_count = 0
        failed_count = 0

        for note_url in all_note_urls:
            note_id = self.extract_note_id(note_url)
            if not note_id:
                logger.warning(f"无法从URL提取笔记ID: {note_url}")
                pending_notes.append(note_url)
                continue

            # 检查是否已完成
            if self.is_note_completed(note_id):
                completed_count += 1
                continue

            # 检查是否失败（失败的会重新处理）
            note_progress = self.get_note_progress(note_id)
            if note_progress.get('status') == 'failed':
                failed_count += 1
                logger.info(f"重新处理失败笔记: {note_id} (原因: {note_progress.get('error_message')})")

            pending_notes.append(note_url)

        # 更新统计
        self.progress_data['statistics']['completed'] = completed_count
        self.progress_data['statistics']['pending'] = len(pending_notes)
        self.save_progress()

        logger.info(f"📊 进度统计:")
        logger.info(f"   总计: {len(all_note_urls)} 个笔记")
        logger.info(f"   已完成: {completed_count} 个 (跳过)")
        logger.info(f"   待处理: {len(pending_notes)} 个")
        if failed_count > 0:
            logger.info(f"   包含失败重试: {failed_count} 个")

        return pending_notes

    def get_statistics(self) -> dict:
        """获取统计信息"""
        return self.progress_data['statistics'].copy()

    def estimate_remaining_time(self, notes_processed: int, elapsed_seconds: float) -> str:
        """
        估算剩余时间

        :param notes_processed: 已处理笔记数
        :param elapsed_seconds: 已用时间（秒）
        :return: 格式化的剩余时间
        """
        if notes_processed == 0:
            return "计算中..."

        pending = self.progress_data['statistics']['pending']
        if pending == 0:
            return "即将完成"

        avg_time_per_note = elapsed_seconds / notes_processed
        remaining_seconds = int(avg_time_per_note * pending)

        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60

        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟{seconds}秒"
        else:
            return f"{seconds}秒"
