# encoding: utf-8
"""
解析JSON文件，获取笔记的完整信息并保存
实现步骤2：读取JSON文件，爬取完整的笔记信息（包括图片、视频、文字、评论）
"""

import json
import os
from datetime import datetime
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, download_note, handle_comment_info


class JsonToFullData:
    """
    解析JSON文件并获取完整笔记信息的类
    """
    
    def __init__(self):
        """
        初始化类实例
        """
        self.xhs_apis = XHS_Apis()
        
    def parse_json_file(self, json_file_path: str):
        """
        解析JSON文件，提取笔记URL列表
        
        :param json_file_path: JSON文件路径
        :return: 成功状态, 消息, 笔记URL列表
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'notes' not in data:
                return False, 'JSON文件格式错误，缺少notes字段', []
            
            notes = data['notes']
            note_urls = []
            
            for note in notes:
                if 'note_url' in note:
                    note_urls.append(note['note_url'])
                elif 'note_id' in note and 'xsec_token' in note:
                    # 根据note_id和xsec_token构建URL
                    note_url = f"https://www.xiaohongshu.com/explore/{note['note_id']}?xsec_token={note['xsec_token']}"
                    note_urls.append(note_url)
            
            logger.info(f'从 {json_file_path} 解析出 {len(note_urls)} 个笔记URL')
            return True, f'成功解析 {len(note_urls)} 个笔记URL', note_urls
            
        except Exception as e:
            error_msg = f'解析JSON文件失败: {str(e)}'
            logger.error(error_msg)
            return False, error_msg, []
    
    def get_note_full_info(self, note_url: str, cookies_str: str, proxies: dict = None, include_comments: bool = True):
        """
        获取单个笔记的完整信息
        
        :param note_url: 笔记URL
        :param cookies_str: 小红书cookies字符串
        :param proxies: 代理设置
        :param include_comments: 是否包含评论数据
        :return: 成功状态, 消息, 笔记完整信息
        """
        try:
            # 获取笔记基本信息
            success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, proxies)
            if not success:
                return False, f'获取笔记信息失败: {msg}', None
            
            # 处理笔记信息
            note_info = note_info['data']['items'][0]
            note_info['url'] = note_url
            processed_note = handle_note_info(note_info)
            
            # 获取评论数据
            if include_comments:
                try:
                    logger.info(f'开始获取评论数据: {note_url}')
                    comment_success, comment_msg, comments = self.xhs_apis.get_note_all_comment(
                        note_url, cookies_str, proxies
                    )
                    logger.info(f'评论API返回: success={comment_success}, msg={comment_msg}, comments_count={len(comments) if comments else 0}')
                    
                    if comment_success and comments:
                        processed_comments = []
                        for comment in comments:
                            comment['note_id'] = processed_note['note_id']
                            comment['note_url'] = note_url
                            processed_comment = handle_comment_info(comment)
                            processed_comments.append(processed_comment)
                        processed_note['comments'] = processed_comments
                        logger.info(f'获取评论数据成功，共 {len(processed_comments)} 条评论')
                    else:
                        processed_note['comments'] = []
                        logger.warning(f'获取评论数据失败: success={comment_success}, msg={comment_msg}')
                        # 账号可能被限制，跳过评论获取
                except Exception as e:
                    processed_note['comments'] = []
                    logger.warning(f'获取评论数据异常: {str(e)}')
            else:
                processed_note['comments'] = []
            
            # 添加获取时间戳
            processed_note['crawl_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return True, '获取笔记完整信息成功', processed_note
            
        except Exception as e:
            error_msg = f'获取笔记完整信息失败: {str(e)}'
            logger.error(error_msg)
            return False, error_msg, None
    
    def process_json_to_full_data(self, json_file_path: str, cookies_str: str, 
                                 output_dir: str = None, include_comments: bool = True, 
                                 download_media: bool = True, save_format: str = 'json',
                                 proxies: dict = None):
        """
        处理JSON文件，获取所有笔记的完整信息并保存
        
        :param json_file_path: 输入的JSON文件路径
        :param cookies_str: 小红书cookies字符串
        :param output_dir: 输出目录，如果不指定则自动生成
        :param include_comments: 是否包含评论数据
        :param download_media: 是否下载媒体文件（图片、视频）
        :param save_format: 保存格式 'json', 'excel', 'all'
        :param proxies: 代理设置
        :return: 成功状态, 消息, 处理结果统计
        """
        try:
            # 解析JSON文件
            parse_success, parse_msg, note_urls = self.parse_json_file(json_file_path)
            if not parse_success:
                return False, parse_msg, {}
            
            # 创建输出目录
            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                json_filename = os.path.splitext(os.path.basename(json_file_path))[0]
                output_dir = f"full_data_{json_filename}_{timestamp}"
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 创建媒体文件目录
            if download_media:
                media_dir = os.path.join(output_dir, "media_files")
                if not os.path.exists(media_dir):
                    os.makedirs(media_dir)
            
            # 处理每个笔记
            successful_notes = []
            failed_notes = []
            all_comments = []
            
            for i, note_url in enumerate(note_urls, 1):
                logger.info(f'正在处理第 {i}/{len(note_urls)} 个笔记: {note_url}')
                
                success, msg, full_note_info = self.get_note_full_info(
                    note_url, cookies_str, proxies, include_comments
                )
                
                if success and full_note_info:
                    successful_notes.append(full_note_info)
                    
                    # 收集评论数据
                    if include_comments and 'comments' in full_note_info:
                        all_comments.extend(full_note_info['comments'])
                    
                    # 下载媒体文件
                    if download_media:
                        try:
                            base_path = {'media': media_dir, 'excel': output_dir}
                            download_note(full_note_info, media_dir, 'media')
                            logger.info(f'媒体文件下载成功: {full_note_info["title"]}')
                        except Exception as e:
                            logger.warning(f'媒体文件下载失败: {str(e)}')
                    
                    # 保存单个笔记的完整信息为JSON
                    if save_format in ['json', 'all']:
                        note_json_file = os.path.join(
                            output_dir, 
                            f"note_{full_note_info['note_id']}_full.json"
                        )
                        with open(note_json_file, 'w', encoding='utf-8') as f:
                            json.dump(full_note_info, f, ensure_ascii=False, indent=2)
                else:
                    failed_notes.append({
                        'url': note_url,
                        'error': msg
                    })
                    logger.error(f'处理失败: {msg}')
            
            # 保存汇总数据
            summary_data = {
                'process_info': {
                    'source_json': json_file_path,
                    'total_notes': len(note_urls),
                    'successful_notes': len(successful_notes),
                    'failed_notes': len(failed_notes),
                    'total_comments': len(all_comments),
                    'include_comments': include_comments,
                    'download_media': download_media,
                    'process_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                'successful_notes': successful_notes,
                'failed_notes': failed_notes
            }
            
            # 保存汇总JSON文件
            if save_format in ['json', 'all']:
                summary_file = os.path.join(output_dir, "summary_all_notes.json")
                with open(summary_file, 'w', encoding='utf-8') as f:
                    json.dump(summary_data, f, ensure_ascii=False, indent=2)
                logger.success(f'汇总JSON文件保存到: {summary_file}')
            
            # 保存为Excel格式
            if save_format in ['excel', 'all']:
                from xhs_utils.data_util import save_to_xlsx
                
                # 保存笔记数据到Excel
                if successful_notes:
                    excel_file = os.path.join(output_dir, "notes_data.xlsx")
                    save_to_xlsx(successful_notes, excel_file)
                    logger.success(f'笔记Excel文件保存到: {excel_file}')
                
                # 保存评论数据到Excel
                if include_comments and all_comments:
                    comment_excel_file = os.path.join(output_dir, "comments_data.xlsx")
                    save_to_xlsx(all_comments, comment_excel_file, 'comment')
                    logger.success(f'评论Excel文件保存到: {comment_excel_file}')
            
            # 保存处理结果统计
            result_stats = {
                'total_notes': len(note_urls),
                'successful_notes': len(successful_notes),
                'failed_notes': len(failed_notes),
                'success_rate': len(successful_notes) / len(note_urls) * 100 if note_urls else 0,
                'total_comments': len(all_comments),
                'output_directory': output_dir
            }
            
            logger.success(f'处理完成！成功: {len(successful_notes)}, 失败: {len(failed_notes)}')
            logger.success(f'结果保存到目录: {output_dir}')
            
            return True, '处理完成', result_stats
            
        except Exception as e:
            error_msg = f'处理JSON文件失败: {str(e)}'
            logger.error(error_msg)
            return False, error_msg, {}
    
    def batch_process_json_files(self, json_files: list, cookies_str: str, 
                               output_base_dir: str = "batch_full_data", **kwargs):
        """
        批量处理多个JSON文件
        
        :param json_files: JSON文件路径列表
        :param cookies_str: 小红书cookies字符串
        :param output_base_dir: 输出基础目录
        :param kwargs: 其他处理参数
        :return: 批量处理结果
        """
        if not os.path.exists(output_base_dir):
            os.makedirs(output_base_dir)
        
        batch_results = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for json_file in json_files:
            logger.info(f'开始处理JSON文件: {json_file}')
            
            # 为每个JSON文件创建独立的输出目录
            json_name = os.path.splitext(os.path.basename(json_file))[0]
            output_dir = os.path.join(output_base_dir, f"{json_name}_{timestamp}")
            
            success, msg, stats = self.process_json_to_full_data(
                json_file, cookies_str, output_dir, **kwargs
            )
            
            batch_results.append({
                'json_file': json_file,
                'success': success,
                'message': msg,
                'stats': stats,
                'output_dir': output_dir if success else None
            })
        
        # 保存批量处理汇总结果
        batch_summary = {
            'batch_info': {
                'total_files': len(json_files),
                'successful_files': len([r for r in batch_results if r['success']]),
                'total_notes_processed': sum([r['stats'].get('total_notes', 0) for r in batch_results]),
                'total_successful_notes': sum([r['stats'].get('successful_notes', 0) for r in batch_results]),
                'process_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            'results': batch_results
        }
        
        batch_summary_file = os.path.join(output_base_dir, f"batch_summary_{timestamp}.json")
        with open(batch_summary_file, 'w', encoding='utf-8') as f:
            json.dump(batch_summary, f, ensure_ascii=False, indent=2)
        
        logger.success(f'批量处理完成，汇总结果保存到: {batch_summary_file}')
        return batch_results


if __name__ == '__main__':
    """
    解析JSON文件并获取完整笔记信息的示例使用
    """
    # 初始化配置
    cookies_str, base_path = init()
    json_processor = JsonToFullData()
    
    # 示例：处理单个JSON文件
    json_file_path = "search_results/search_日本料理_20250905_183800.json"  # 请修改为实际文件路径
    
    # 检查文件是否存在
    if os.path.exists(json_file_path):
        success, msg, stats = json_processor.process_json_to_full_data(
            json_file_path=json_file_path,
            cookies_str=cookies_str,
            include_comments=True,  # 包含评论数据
            download_media=True,    # 下载媒体文件
            save_format='all'       # 保存为JSON和Excel格式
        )
        
        if success:
            print(f"✅ 处理成功: {msg}")
            print(f"📊 统计信息: {stats}")
        else:
            print(f"❌ 处理失败: {msg}")
    else:
        print(f"❌ JSON文件不存在: {json_file_path}")
        print("请先运行 search_to_json.py 生成JSON文件")
    
    # 批量处理示例（注释掉，需要时启用）
    """
    json_files = [
        "search_results/search_日本料理_20240101_120000.json",
        "search_results/search_意大利面_20240101_120000.json"
    ]
    
    existing_files = [f for f in json_files if os.path.exists(f)]
    if existing_files:
        results = json_processor.batch_process_json_files(
            json_files=existing_files,
            cookies_str=cookies_str,
            include_comments=True,
            download_media=True,
            save_format='all'
        )
        
        for result in results:
            status = "✅" if result['success'] else "❌"
            file_name = os.path.basename(result['json_file'])
            print(f"{status} {file_name}: {result['message']}")
    """