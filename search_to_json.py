# encoding: utf-8
"""
搜索指定关键词的笔记，将搜索结果保存为JSON格式
实现步骤1：搜索并获取笔记基本信息，保存为JSON格式
"""

import json
import os
import time
from datetime import datetime
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init


class SearchToJson:
    """
    关键词搜索笔记并保存为JSON格式的类
    """
    
    def __init__(self):
        """
        初始化类实例
        """
        self.xhs_apis = XHS_Apis()
    
    def _convert_count(self, count_str):
        """
        转换数字字符串为整数
        小红书API返回的数字可能是字符串格式，如 "37700"
        """
        if isinstance(count_str, str):
            try:
                return int(count_str)
            except ValueError:
                return 0
        return count_str if isinstance(count_str, int) else 0
        
    def search_notes_to_json(self, query: str, require_num: int, cookies_str: str, 
                            output_file: str = None, sort_type_choice: int = 0, 
                            note_type: int = 0, note_time: int = 0, note_range: int = 0, 
                            pos_distance: int = 0, geo: dict = None, proxies: dict = None):
        """
        搜索指定关键词的笔记，将结果保存为JSON格式
        
        :param query: 搜索的关键词
        :param require_num: 需要搜索的数量
        :param cookies_str: 小红书cookies字符串
        :param output_file: 输出JSON文件路径，如果不指定则自动生成
        :param sort_type_choice: 排序方式 0=综合排序, 1=最新, 2=最多点赞, 3=最多评论, 4=最多收藏
        :param note_type: 笔记类型 0=不限, 1=视频笔记, 2=普通笔记
        :param note_time: 笔记时间 0=不限, 1=一天内, 2=一周内, 3=半年内
        :param note_range: 笔记范围 0=不限, 1=已看过, 2=未看过, 3=已关注
        :param pos_distance: 位置距离 0=不限, 1=同城, 2=附近
        :param geo: 地理位置信息 {"latitude": 纬度, "longitude": 经度}
        :param proxies: 代理设置
        :return: 成功状态, 消息, 笔记列表
        """
        try:
            # 调用搜索API获取笔记列表
            success, msg, notes = self.xhs_apis.search_some_note(
                query, require_num, cookies_str, sort_type_choice, 
                note_type, note_time, note_range, pos_distance, geo, proxies
            )
            
            if not success:
                logger.error(f'搜索失败: {msg}')
                return False, msg, []
            
            # 过滤出笔记类型的内容
            filtered_notes = list(filter(lambda x: x['model_type'] == "note", notes))
            logger.info(f'搜索关键词 "{query}" 找到 {len(filtered_notes)} 篇笔记')
            
            # 处理笔记数据，添加更多有用信息
            processed_notes = []
            for note in filtered_notes:
                note_card = note.get('note_card', {})
                user_info = note_card.get('user', {})
                interact_info = note_card.get('interact_info', {})
                cover_info = note_card.get('cover', {})
                
                processed_note = {
                    'note_id': note['id'],
                    'title': note_card.get('display_title', '') or note_card.get('title', ''),
                    'desc': note_card.get('desc', ''),
                    'note_type': note_card.get('type', ''),
                    'xsec_token': note.get('xsec_token', ''),
                    'note_url': f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note.get('xsec_token', '')}",
                    'user_id': user_info.get('user_id', ''),
                    'user_nickname': user_info.get('nickname', '') or user_info.get('nick_name', ''),
                    'user_avatar': user_info.get('avatar', ''),
                    'interact_info': {
                        'liked_count': self._convert_count(interact_info.get('liked_count', 0)),
                        'collected_count': self._convert_count(interact_info.get('collected_count', 0)),
                        'comment_count': self._convert_count(interact_info.get('comment_count', 0)),
                        'share_count': self._convert_count(interact_info.get('shared_count', 0))
                    },
                    'cover': {
                        'url': cover_info.get('url_default', '') or cover_info.get('url', ''),
                        'info_list': cover_info.get('info_list', [])
                    },
                    'search_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'search_query': query
                }
                processed_notes.append(processed_note)
            
            # 生成输出文件名
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                # 创建搜索结果目录
                search_dir = "search_results"
                if not os.path.exists(search_dir):
                    os.makedirs(search_dir)
                output_file = os.path.join(search_dir, f"search_{query}_{timestamp}.json")
            
            # 创建完整的搜索结果数据
            result_data = {
                'search_info': {
                    'query': query,
                    'require_num': require_num,
                    'actual_num': len(processed_notes),
                    'sort_type': sort_type_choice,
                    'note_type': note_type,
                    'note_time': note_time,
                    'note_range': note_range,
                    'pos_distance': pos_distance,
                    'geo': geo,
                    'search_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                'notes': processed_notes
            }
            
            # 保存为JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            logger.success(f'搜索结果已保存到: {output_file}')
            logger.info(f'共找到 {len(processed_notes)} 篇笔记')
            
            return True, f'搜索成功，结果已保存到 {output_file}', processed_notes
            
        except Exception as e:
            error_msg = f'搜索过程中发生错误: {str(e)}'
            logger.error(error_msg)
            return False, error_msg, []
    
    def batch_search_to_json(self, queries: list, require_num: int, cookies_str: str, 
                           output_dir: str = "search_results", **kwargs):
        """
        批量搜索多个关键词并分别保存为JSON文件
        
        :param queries: 关键词列表
        :param require_num: 每个关键词搜索的数量
        :param cookies_str: 小红书cookies字符串
        :param output_dir: 输出目录
        :param kwargs: 其他搜索参数
        :return: 搜索结果汇总
        """
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        results = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for query in queries:
            logger.info(f'开始搜索关键词: {query}')
            
            output_file = os.path.join(output_dir, f"search_{query}_{timestamp}.json")
            success, msg, notes = self.search_notes_to_json(
                query, require_num, cookies_str, output_file, **kwargs
            )
            
            results.append({
                'query': query,
                'success': success,
                'message': msg,
                'note_count': len(notes) if notes else 0,
                'output_file': output_file if success else None
            })
            
            # 避免请求过于频繁
            time.sleep(2)
        
        # 保存批量搜索汇总结果
        summary_file = os.path.join(output_dir, f"batch_search_summary_{timestamp}.json")
        summary_data = {
            'batch_info': {
                'total_queries': len(queries),
                'successful_queries': len([r for r in results if r['success']]),
                'total_notes': sum([r['note_count'] for r in results]),
                'search_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            'results': results
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)
        
        logger.success(f'批量搜索完成，汇总结果保存到: {summary_file}')
        return results


if __name__ == '__main__':
    """
    搜索关键词笔记并保存为JSON格式的示例使用
    """
    # 初始化配置
    cookies_str, base_path = init()
    search_spider = SearchToJson()
    
    # 单个关键词搜索示例
    query = "日本料理"
    require_num = 20
    
    success, msg, notes = search_spider.search_notes_to_json(
        query=query,
        require_num=require_num,
        cookies_str=cookies_str,
        sort_type_choice=0,  # 综合排序
        note_type=0,  # 不限类型
        note_time=0,  # 不限时间
    )
    
    if success:
        print(f"✅ 搜索成功: {msg}")
    else:
        print(f"❌ 搜索失败: {msg}")
    
    # 批量搜索示例
    """
    queries = ["日本料理", "意大利面", "中式快餐"]
    results = search_spider.batch_search_to_json(
        queries=queries,
        require_num=10,
        cookies_str=cookies_str,
        sort_type_choice=0,
        note_type=0
    )
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['query']}: {result['note_count']} 篇笔记")
    """