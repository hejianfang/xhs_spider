# encoding: utf-8
import json
import re
import urllib
import requests
import time
from retry import retry
from requests.exceptions import ConnectionError, Timeout, RequestException
from xhs_utils.xhs_util import splice_str, generate_request_params, generate_x_b3_traceid, get_common_headers
from loguru import logger

# ==================== 配置常量 ====================

# 子评论获取配置
SUB_COMMENT_MAX_RETRIES = 5           # 遇到限流时的最大重试次数（切换Cookie）
SUB_COMMENT_RETRY_WAIT = 10           # 所有Cookie都限流时的等待时间(秒)
SUB_COMMENT_REQUEST_INTERVAL = 3      # 分页请求间隔(秒)，与Cookie池min_interval保持一致

# API错误码
API_CODE_RATE_LIMITED = 300013        # 访问频次异常

# ==================================================

"""
    获小红书的api
    :param cookies_str: 你的cookies
"""
class XHS_Apis():
    def __init__(self):
        self.base_url = "https://edith.xiaohongshu.com"

    @staticmethod
    @retry(exceptions=(ConnectionError, Timeout), tries=3, delay=2, backoff=2, logger=logger)
    def _request_with_retry(method, url, **kwargs):
        """
        带重试机制的HTTP请求

        :param method: 请求方法 ('GET' 或 'POST')
        :param url: 请求URL
        :param kwargs: requests库的其他参数
        :return: Response对象
        """
        try:
            if method.upper() == 'GET':
                response = requests.get(url, **kwargs)
            else:
                response = requests.post(url, **kwargs)
            return response
        except (ConnectionError, Timeout) as e:
            logger.warning(f"网络请求失败，正在重试: {e}")
            raise  # 让retry装饰器处理重试

    @staticmethod
    def _parse_url_params(query_string: str) -> dict:
        """
        安全地解析URL的query参数

        :param query_string: URL的query部分
        :return: 参数字典
        """
        kvDist = {}
        if not query_string:
            return kvDist

        kvs = query_string.split('&')
        for kv in kvs:
            if not kv:  # 跳过空字符串
                continue
            parts = kv.split('=')
            if len(parts) >= 2:
                kvDist[parts[0]] = parts[1]
            elif len(parts) == 1:
                kvDist[parts[0]] = ''  # 没有值的参数设为空字符串
        return kvDist

    def get_homefeed_all_channel(self, cookies_str: str, proxies: dict = None):
        """
            获取主页的所有频道
            返回主页的所有频道
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/homefeed/category"
            headers, cookies, data = generate_request_params(cookies_str, api)
            response = requests.get(self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_homefeed_recommend(self, category, cursor_score, refresh_type, note_index, cookies_str: str, proxies: dict = None):
        """
            获取主页推荐的笔记
            :param category: 你想要获取的频道
            :param cursor_score: 你想要获取的笔记的cursor
            :param refresh_type: 你想要获取的笔记的刷新类型
            :param note_index: 你想要获取的笔记的index
            :param cookies_str: 你的cookies
            返回主页推荐的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/homefeed"
            data = {
                "cursor_score": cursor_score,
                "num": 20,
                "refresh_type": refresh_type,
                "note_index": note_index,
                "unread_begin_note_id": "",
                "unread_end_note_id": "",
                "unread_note_count": 0,
                "category": category,
                "search_key": "",
                "need_num": 10,
                "image_formats": [
                    "jpg",
                    "webp",
                    "avif"
                ],
                "need_filter_image": False
            }
            headers, cookies, trans_data = generate_request_params(cookies_str, api, data)
            response = requests.post(self.base_url + api, headers=headers, data=trans_data, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_homefeed_recommend_by_num(self, category, require_num, cookies_str: str, proxies: dict = None):
        """
            根据数量获取主页推荐的笔记
            :param category: 你想要获取的频道
            :param require_num: 你想要获取的笔记的数量
            :param cookies_str: 你的cookies
            根据数量返回主页推荐的笔记
        """
        cursor_score, refresh_type, note_index = "", 1, 0
        note_list = []
        try:
            while True:
                success, msg, res_json = self.get_homefeed_recommend(category, cursor_score, refresh_type, note_index, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                if "items" not in res_json["data"]:
                    break
                notes = res_json["data"]["items"]
                note_list.extend(notes)
                cursor_score = res_json["data"]["cursor_score"]
                refresh_type = 3
                note_index += 20
                if len(note_list) > require_num:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        if len(note_list) > require_num:
            note_list = note_list[:require_num]
        return success, msg, note_list

    def get_user_info(self, user_id: str, cookies_str: str, proxies: dict = None):
        """
            获取用户的信息
            :param user_id: 你想要获取的用户的id
            :param cookies_str: 你的cookies
            返回用户的信息
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/user/otherinfo"
            params = {
                "target_user_id": user_id
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_self_info(self, cookies_str: str, proxies: dict = None):
        """
            获取用户自己的信息1
            :param cookies_str: 你的cookies
            返回用户自己的信息1
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/user/selfinfo"
            headers, cookies, data = generate_request_params(cookies_str, api)
            response = requests.get(self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json


    def get_user_self_info2(self, cookies_str: str, proxies: dict = None):
        """
            获取用户自己的信息2
            :param cookies_str: 你的cookies
            返回用户自己的信息2
        """
        res_json = None
        try:
            api = f"/api/sns/web/v2/user/me"
            headers, cookies, data = generate_request_params(cookies_str, api)
            response = requests.get(self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_note_info(self, user_id: str, cursor: str, cookies_str: str, xsec_token='', xsec_source='', proxies: dict = None):
        """
            获取用户指定位置的笔记
            :param user_id: 你想要获取的用户的id
            :param cursor: 你想要获取的笔记的cursor
            :param cookies_str: 你的cookies
            返回用户指定位置的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/user_posted"
            params = {
                "num": "30",
                "cursor": cursor,
                "user_id": user_id,
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json


    def get_user_all_notes(self, user_url: str, cookies_str: str, proxies: dict = None):
        """
           获取用户所有笔记
           :param user_id: 你想要获取的用户的id
           :param cookies_str: 你的cookies
           返回用户的所有笔记
        """
        cursor = ''
        note_list = []
        try:
            urlParse = urllib.parse.urlparse(user_url)
            user_id = urlParse.path.split("/")[-1]
            kvDist = self._parse_url_params(urlParse.query)
            xsec_token = kvDist.get('xsec_token', '')
            xsec_source = kvDist.get('xsec_source', 'pc_search')
            while True:
                success, msg, res_json = self.get_user_note_info(user_id, cursor, cookies_str, xsec_token, xsec_source, proxies)
                if not success:
                    raise Exception(msg)
                notes = res_json["data"]["notes"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_list.extend(notes)
                if len(notes) == 0 or not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_list

    def get_user_like_note_info(self, user_id: str, cursor: str, cookies_str: str, xsec_token='', xsec_source='', proxies: dict = None):
        """
            获取用户指定位置喜欢的笔记
            :param user_id: 你想要获取的用户的id
            :param cursor: 你想要获取的笔记的cursor
            :param cookies_str: 你的cookies
            返回用户指定位置喜欢的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v1/note/like/page"
            params = {
                "num": "30",
                "cursor": cursor,
                "user_id": user_id,
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_all_like_note_info(self, user_url: str, cookies_str: str, proxies: dict = None):
        """
            获取用户所有喜欢笔记
            :param user_id: 你想要获取的用户的id
            :param cookies_str: 你的cookies
            返回用户的所有喜欢笔记
        """
        cursor = ''
        note_list = []
        try:
            urlParse = urllib.parse.urlparse(user_url)
            user_id = urlParse.path.split("/")[-1]
            kvDist = self._parse_url_params(urlParse.query)
            xsec_token = kvDist.get('xsec_token', '')
            xsec_source = kvDist.get('xsec_source', 'pc_user')
            while True:
                success, msg, res_json = self.get_user_like_note_info(user_id, cursor, cookies_str, xsec_token,
                                                                      xsec_source, proxies)
                if not success:
                    raise Exception(msg)
                notes = res_json["data"]["notes"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_list.extend(notes)
                if len(notes) == 0 or not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_list

    def get_user_collect_note_info(self, user_id: str, cursor: str, cookies_str: str, xsec_token='', xsec_source='', proxies: dict = None):
        """
            获取用户指定位置收藏的笔记
            :param user_id: 你想要获取的用户的id
            :param cursor: 你想要获取的笔记的cursor
            :param cookies_str: 你的cookies
            返回用户指定位置收藏的笔记
        """
        res_json = None
        try:
            api = f"/api/sns/web/v2/note/collect/page"
            params = {
                "num": "30",
                "cursor": cursor,
                "user_id": user_id,
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token,
                "xsec_source": xsec_source,
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_user_all_collect_note_info(self, user_url: str, cookies_str: str, proxies: dict = None):
        """
            获取用户所有收藏笔记
            :param user_id: 你想要获取的用户的id
            :param cookies_str: 你的cookies
            返回用户的所有收藏笔记
        """
        cursor = ''
        note_list = []
        try:
            urlParse = urllib.parse.urlparse(user_url)
            user_id = urlParse.path.split("/")[-1]
            kvDist = self._parse_url_params(urlParse.query)
            xsec_token = kvDist.get('xsec_token', '')
            xsec_source = kvDist.get('xsec_source', 'pc_search')
            while True:
                success, msg, res_json = self.get_user_collect_note_info(user_id, cursor, cookies_str, xsec_token,
                                                                         xsec_source, proxies)
                if not success:
                    raise Exception(msg)
                notes = res_json["data"]["notes"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                note_list.extend(notes)
                if len(notes) == 0 or not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, note_list

    def get_note_info(self, url: str, cookies_str: str, proxies: dict = None):
        """
            获取笔记的详细
            :param url: 你想要获取的笔记的url
            :param cookies_str: 你的cookies
            :param xsec_source: 你的xsec_source 默认为pc_search pc_user pc_feed
            返回笔记的详细
        """
        res_json = None
        try:
            urlParse = urllib.parse.urlparse(url)
            note_id = urlParse.path.split("/")[-1]
            kvDist = self._parse_url_params(urlParse.query)
            api = f"/api/sns/web/v1/feed"
            data = {
                "source_note_id": note_id,
                "image_formats": [
                    "jpg",
                    "webp",
                    "avif"
                ],
                "extra": {
                    "need_body_topic": "1"
                },
                "xsec_source": kvDist['xsec_source'] if 'xsec_source' in kvDist else "pc_search",
                "xsec_token": kvDist['xsec_token']
            }
            headers, cookies, data = generate_request_params(cookies_str, api, data)
            # 使用带重试机制的请求方法
            response = self._request_with_retry('POST', self.base_url + api, headers=headers, data=data, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json


    def get_search_keyword(self, word: str, cookies_str: str, proxies: dict = None):
        """
            获取搜索关键词
            :param word: 你的关键词
            :param cookies_str: 你的cookies
            返回搜索关键词
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/search/recommend"
            params = {
                "keyword": urllib.parse.quote(word)
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def search_note(self, query: str, cookies_str: str, page=1, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo="", proxies: dict = None):
        """
            获取搜索笔记的结果
            :param query 搜索的关键词
            :param cookies_str 你的cookies
            :param page 搜索的页数
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            返回搜索的结果
        """
        res_json = None
        sort_type = "general"
        if sort_type_choice == 1:
            sort_type = "time_descending"
        elif sort_type_choice == 2:
            sort_type = "popularity_descending"
        elif sort_type_choice == 3:
            sort_type = "comment_descending"
        elif sort_type_choice == 4:
            sort_type = "collect_descending"
        filter_note_type = "不限"
        if note_type == 1:
            filter_note_type = "视频笔记"
        elif note_type == 2:
            filter_note_type = "普通笔记"
        filter_note_time = "不限"
        if note_time == 1:
            filter_note_time = "一天内"
        elif note_time == 2:
            filter_note_time = "一周内"
        elif note_time == 3:
            filter_note_time = "半年内"
        filter_note_range = "不限"
        if note_range == 1:
            filter_note_range = "已看过"
        elif note_range == 2:
            filter_note_range = "未看过"
        elif note_range == 3:
            filter_note_range = "已关注"
        filter_pos_distance = "不限"
        if pos_distance == 1:
            filter_pos_distance = "同城"
        elif pos_distance == 2:
            filter_pos_distance = "附近"
        if geo:
            geo = json.dumps(geo, separators=(',', ':'))
        try:
            api = "/api/sns/web/v1/search/notes"
            data = {
                "keyword": query,
                "page": page,
                "page_size": 20,
                "search_id": generate_x_b3_traceid(21),
                "sort": "general",
                "note_type": 0,
                "ext_flags": [],
                "filters": [
                    {
                        "tags": [
                            sort_type
                        ],
                        "type": "sort_type"
                    },
                    {
                        "tags": [
                            filter_note_type
                        ],
                        "type": "filter_note_type"
                    },
                    {
                        "tags": [
                            filter_note_time
                        ],
                        "type": "filter_note_time"
                    },
                    {
                        "tags": [
                            filter_note_range
                        ],
                        "type": "filter_note_range"
                    },
                    {
                        "tags": [
                            filter_pos_distance
                        ],
                        "type": "filter_pos_distance"
                    }
                ],
                "geo": geo,
                "image_formats": [
                    "jpg",
                    "webp",
                    "avif"
                ]
            }
            headers, cookies, data = generate_request_params(cookies_str, api, data)
            response = requests.post(self.base_url + api, headers=headers, data=data.encode('utf-8'), cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def search_some_note(self, query: str, require_num: int, cookies_str: str, sort_type_choice=0, note_type=0, note_time=0, note_range=0, pos_distance=0, geo="", proxies: dict = None):
        """
            指定数量搜索笔记，设置排序方式和笔记类型和笔记数量
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            :param sort_type_choice 排序方式 0 综合排序, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏
            :param note_type 笔记类型 0 不限, 1 视频笔记, 2 普通笔记
            :param note_time 笔记时间 0 不限, 1 一天内, 2 一周内天, 3 半年内
            :param note_range 笔记范围 0 不限, 1 已看过, 2 未看过, 3 已关注
            :param pos_distance 位置距离 0 不限, 1 同城, 2 附近 指定这个必须要指定 geo
            :param geo: 定位信息 经纬度
            返回搜索的结果
        """
        page = 1
        note_list = []
        try:
            while True:
                success, msg, res_json = self.search_note(query, cookies_str, page, sort_type_choice, note_type, note_time, note_range, pos_distance, geo, proxies)
                if not success:
                    raise Exception(msg)
                if "items" not in res_json["data"]:
                    break
                notes = res_json["data"]["items"]
                note_list.extend(notes)
                page += 1
                if len(note_list) >= require_num or not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        if len(note_list) > require_num:
            note_list = note_list[:require_num]
        return success, msg, note_list

    def search_user(self, query: str, cookies_str: str, page=1, proxies: dict = None):
        """
            获取搜索用户的结果
            :param query 搜索的关键词
            :param cookies_str 你的cookies
            :param page 搜索的页数
            返回搜索的结果
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/search/usersearch"
            data = {
                "search_user_request": {
                    "keyword": query,
                    "search_id": "2dn9they1jbjxwawlo4xd",
                    "page": page,
                    "page_size": 15,
                    "biz_type": "web_search_user",
                    "request_id": "22471139-1723999898524"
                }
            }
            headers, cookies, data = generate_request_params(cookies_str, api, data)
            response = requests.post(self.base_url + api, headers=headers, data=data.encode('utf-8'), cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def search_some_user(self, query: str, require_num: int, cookies_str: str, proxies: dict = None):
        """
            指定数量搜索用户
            :param query 搜索的关键词
            :param require_num 搜索的数量
            :param cookies_str 你的cookies
            返回搜索的结果
        """
        page = 1
        user_list = []
        try:
            while True:
                success, msg, res_json = self.search_user(query, cookies_str, page, proxies)
                if not success:
                    raise Exception(msg)
                if "users" not in res_json["data"]:
                    break
                users = res_json["data"]["users"]
                user_list.extend(users)
                page += 1
                if len(user_list) >= require_num or not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        if len(user_list) > require_num:
            user_list = user_list[:require_num]
        return success, msg, user_list

    def get_note_out_comment(self, note_id: str, cursor: str, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取指定位置的笔记一级评论
            :param note_id 笔记的id
            :param cursor 指定位置的评论的cursor
            :param cookies_str 你的cookies
            返回指定位置的笔记一级评论
        """
        res_json = None
        try:
            api = "/api/sns/web/v2/comment/page"
            params = {
                "note_id": note_id,
                "cursor": cursor,
                "top_comment_id": "",
                "image_formats": "jpg,webp,avif",
                "xsec_token": xsec_token
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)

            # 添加详细的调试日志
            logger.debug(f"评论API请求URL: {self.base_url + splice_api}")
            logger.debug(f"请求参数: note_id={note_id}, cursor={cursor}, xsec_token={xsec_token[:20]}...")

            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)

            # 记录响应状态
            logger.debug(f"HTTP状态码: {response.status_code}")

            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]

            # 如果data为空，记录更详细信息
            if res_json.get("data") == {}:
                logger.warning(f"评论API返回data为空！笔记ID: {note_id}, xsec_token前20位: {xsec_token[:20]}")
                logger.warning(f"完整响应: {res_json}")
                logger.warning("可能原因: 1)Cookie权限不足 2)xsec_token过期 3)笔记评论被限制 4)需要额外参数")

        except Exception as e:
            success = False
            msg = str(e)
            logger.error(f"评论请求异常: {e}")
        return success, msg, res_json

    def get_note_all_out_comment(self, note_id: str, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取笔记的全部一级评论
            :param note_id 笔记的id
            :param cookies_str 你的cookies
            返回笔记的全部一级评论
        """
        cursor = ''
        note_out_comment_list = []
        page_count = 0
        try:
            while True:
                page_count += 1
                logger.info(f"正在获取第 {page_count} 页一级评论，当前cursor: {cursor}")
                success, msg, res_json = self.get_note_out_comment(note_id, cursor, xsec_token, cookies_str, proxies)
                if not success:
                    logger.error(f"获取评论失败: {msg}")
                    raise Exception(msg)

                # 检查返回数据结构
                if not res_json or "data" not in res_json:
                    logger.error(f"API返回数据异常: {res_json}")
                    raise Exception("API返回数据格式错误，缺少data字段")

                if "comments" not in res_json["data"]:
                    logger.error(f"API返回的data中没有comments字段，完整返回: {res_json}")
                    raise Exception("API返回数据格式错误，缺少comments字段")

                comments = res_json["data"]["comments"]
                has_more = res_json["data"].get("has_more", False)
                logger.info(f"第 {page_count} 页获取到 {len(comments)} 条评论，has_more: {has_more}")
                
                note_out_comment_list.extend(comments)
                
                # 检查是否有cursor字段
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                    logger.info(f"下一页cursor: {cursor}")
                else:
                    logger.info("没有cursor字段，停止获取")
                    break
                    
                # 检查退出条件
                if len(comments) == 0:
                    logger.info("当前页没有评论，停止获取")
                    break
                if not has_more:
                    logger.info(f"has_more为False，停止获取。当前累计获取 {len(note_out_comment_list)} 条一级评论")
                    # 即使has_more为False，也检查是否还有cursor
                    if 'cursor' in res_json["data"] and res_json["data"]["cursor"]:
                        logger.warning(f"注意：has_more为False但仍有cursor: {res_json['data']['cursor']}，可能还有更多数据")
                    break
                    
                # 添加延时避免请求过快
                import time
                time.sleep(0.5)
        except Exception as e:
            success = False
            msg = str(e)
            logger.error(f"获取评论过程出错: {msg}")
        
        logger.info(f"一级评论获取完成，共 {len(note_out_comment_list)} 条")
        return success, msg, note_out_comment_list

    def get_note_inner_comment(self, comment: dict, cursor: str, xsec_token: str, cookies_str: str, proxies: dict = None):
        """
            获取指定位置的笔记二级评论
            :param comment 笔记的一级评论
            :param cursor 指定位置的评论的cursor
            :param cookies_str 你的cookies
            返回指定位置的笔记二级评论
        """
        res_json = None
        try:
            api = "/api/sns/web/v2/comment/sub/page"
            params = {
                "note_id": comment['note_id'],
                "root_comment_id": comment['id'],
                "num": "10",
                "cursor": cursor,
                "image_formats": "jpg,webp,avif",
                "top_comment_id": '',
                "xsec_token": xsec_token
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_note_all_inner_comment(self, comment: dict, xsec_token: str, cookies_str: str, proxies: dict = None, level: int = 2):
        """
            递归获取评论的所有子评论（支持多层级）
            :param comment 评论对象
            :param cookies_str 你的cookies
            :param level 当前评论层级（用于日志）
            返回包含所有子评论的评论对象
        """
        try:
            # 首先检查是否已经有sub_comments字段，如果没有则初始化
            if 'sub_comments' not in comment:
                comment['sub_comments'] = []
            
            # 检查sub_comment_count来确定是否有子评论
            sub_comment_count = comment.get('sub_comment_count', 0)
            # 确保是整数类型
            if isinstance(sub_comment_count, str):
                sub_comment_count = int(sub_comment_count) if sub_comment_count.isdigit() else 0
            
            # 如果没有子评论，直接返回
            if sub_comment_count == 0:
                logger.debug(f"评论 {comment['id']} 没有{level}级评论")
                return True, 'success', comment

            # 检查当前已有的子评论数量是否等于预期数量
            current_count = len(comment.get('sub_comments', []))

            # 如果数量已经完整（当前数≥预期数），直接递归处理
            if current_count >= sub_comment_count:
                logger.debug(f"评论 {comment['id']} 的{level}级评论已完整（{current_count}/{sub_comment_count}）")
                # 递归处理已有的子评论
                for sub_comment in comment['sub_comments']:
                    self.get_note_all_inner_comment(sub_comment, xsec_token, cookies_str, proxies, level + 1)
                return True, 'success', comment

            # 否则需要主动获取完整数据（即使sub_comment_has_more=False也要检查）
            logger.info(f"评论 {comment['id']} 需要获取完整{level}级子评论（当前{current_count}条，预期{sub_comment_count}条）")

            # 先获取完整数据到临时列表，成功后再替换（避免失败时丢失原有数据）
            cursor = comment.get('sub_comment_cursor', '')
            inner_comment_list = []
            page = 0
            fetch_success = False  # 标记是否成功获取

            # ========== 智能重试机制（无Cookie池版本，只能等待重试）==========
            max_retries = 3  # 无Cookie池时重试次数较少
            for retry_count in range(max_retries):
                try:
                    # 分页获取子评论
                    while True:
                        page += 1
                        logger.debug(f"获取评论 {comment['id']} 的第 {page} 页{level}级评论")
                        success, msg, res_json = self.get_note_inner_comment(comment, cursor, xsec_token, cookies_str, proxies)

                        if not success:
                            raise Exception(msg)

                        # ========== 识别限流错误（code 300013）==========
                        if "code" in res_json and res_json["code"] == API_CODE_RATE_LIMITED:
                            # 访问频次异常
                            rate_limit_msg = res_json.get('msg', '访问频次异常')

                            if retry_count < max_retries - 1:
                                # 还有重试机会，等待后重试
                                logger.warning(f"⚠️  限流（code {API_CODE_RATE_LIMITED}：{rate_limit_msg}），等待 {SUB_COMMENT_RETRY_WAIT} 秒后重试 ({retry_count+1}/{max_retries})")
                                time.sleep(SUB_COMMENT_RETRY_WAIT)
                                raise Exception(f"RateLimited_{retry_count}")  # 触发外层重试
                            else:
                                # 最后一次重试也失败
                                logger.error(f"❌ 限流错误，已重试{max_retries}次，放弃获取")
                                raise Exception(f"访问频次异常，重试{max_retries}次后失败")

                        # 检查数据格式
                        if "data" not in res_json or "comments" not in res_json["data"]:
                            raise Exception(f"API返回数据格式错误: {res_json}")

                        # 提取评论
                        comments = res_json["data"]["comments"]
                        inner_comment_list.extend(comments)
                        logger.debug(f"  成功获取 {len(comments)} 条子评论")

                        # 检查分页
                        if 'cursor' in res_json["data"]:
                            cursor = str(res_json["data"]["cursor"])
                        else:
                            break

                        if not res_json["data"]["has_more"]:
                            break

                        # 请求间隔（使用配置的3秒）
                        time.sleep(SUB_COMMENT_REQUEST_INTERVAL)

                    # 成功获取所有分页数据，跳出重试循环
                    fetch_success = True
                    break

                except Exception as e:
                    # 判断是否是限流错误需要重试
                    if "RateLimited_" in str(e):
                        # 限流错误，继续下一轮重试（等待后）
                        continue
                    elif retry_count < max_retries - 1:
                        # 其他错误，也尝试重试
                        logger.warning(f"获取失败: {e}，等待后重试 ({retry_count+1}/{max_retries})")
                        time.sleep(5)  # 短暂等待
                        continue
                    else:
                        # 最后一次重试也失败
                        logger.error(f"评论 {comment['id']} 获取子评论失败（重试{max_retries}次后）: {e}，保留原有{current_count}条数据")
                        break

            # 如果成功获取，替换为完整数据
            if fetch_success:
                comment['sub_comments'] = inner_comment_list
                actual_count = len(comment['sub_comments'])
                logger.info(f"✅ 评论 {comment['id']} 完整获取{level}级子评论成功：{actual_count}/{sub_comment_count} 条")
            else:
                logger.warning(f"⚠️  评论 {comment['id']} 未能获取完整子评论，保留原有{current_count}条数据")
            
            # 递归获取每个子评论的子评论（支持多层级）
            for sub_comment in comment['sub_comments']:
                # 递归调用，获取更深层级的评论
                self.get_note_all_inner_comment(sub_comment, xsec_token, cookies_str, proxies, level + 1)
                
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, comment

    def get_note_all_inner_comment_with_provider(self, comment: dict, xsec_token: str,
                                                 cookie_provider, proxies: dict = None,
                                                 level: int = 2, max_level: int = 10,
                                                 save_callback=None):
        """
        递归获取评论的所有子评论（支持Cookie池，支持多层级，支持增量保存）

        :param comment: 评论对象
        :param xsec_token: xsec_token参数
        :param cookie_provider: Cookie提供函数，返回 (success, cookie_str)
        :param proxies: 代理设置
        :param level: 当前评论层级
        :param max_level: 最大递归层级（防止无限递归）
        :param save_callback: 可选的保存回调函数，签名为 callback(comment, level)，每获取一条评论就调用
        :return: (success, msg, comment)
        """
        try:
            # 检查最大层级限制
            if level > max_level:
                logger.warning(f"达到最大层级限制 {max_level}，停止递归")
                return True, f'reached max level {max_level}', comment

            # 初始化sub_comments
            if 'sub_comments' not in comment:
                comment['sub_comments'] = []

            # 检查sub_comment_count
            sub_comment_count = comment.get('sub_comment_count', 0)
            if isinstance(sub_comment_count, str):
                sub_comment_count = int(sub_comment_count) if sub_comment_count.isdigit() else 0

            if sub_comment_count == 0:
                logger.debug(f"评论 {comment['id']} 没有{level}级评论")
                return True, 'success', comment

            # 检查当前已有的子评论数量是否等于预期数量
            current_count = len(comment.get('sub_comments', []))

            # 如果数量已经完整（当前数≥预期数），直接递归处理
            if current_count >= sub_comment_count:
                logger.debug(f"评论 {comment['id']} 的{level}级评论已完整（{current_count}/{sub_comment_count}）")
                # 递归处理已有的子评论
                for sub_comment in comment['sub_comments']:
                    self.get_note_all_inner_comment_with_provider(
                        sub_comment, xsec_token, cookie_provider, proxies, level + 1, max_level, save_callback
                    )
                return True, 'success', comment

            # 否则需要主动获取完整数据（即使sub_comment_has_more=False也要检查）
            logger.info(f"评论 {comment['id']} 需要获取完整{level}级子评论（当前{current_count}条，预期{sub_comment_count}条）")

            # 先获取完整数据到临时列表，成功后再替换（避免失败时丢失原有数据）
            cursor = comment.get('sub_comment_cursor', '')
            inner_comment_list = []
            page = 0
            fetch_success = False  # 标记是否成功获取

            # ========== 智能重试机制：先切换Cookie，都失败则等待 ==========
            for retry_count in range(SUB_COMMENT_MAX_RETRIES):
                try:
                    # 使用Cookie提供函数获取Cookie
                    success, cookies_str = cookie_provider()
                    if not success:
                        if retry_count < SUB_COMMENT_MAX_RETRIES - 1:
                            logger.warning(f"无可用Cookie，等待后重试 ({retry_count+1}/{SUB_COMMENT_MAX_RETRIES})")
                            time.sleep(SUB_COMMENT_RETRY_WAIT)
                            continue
                        else:
                            raise Exception("无可用Cookie，所有重试均失败")

                    # 分页获取子评论
                    while True:
                        page += 1
                        logger.debug(f"获取评论 {comment['id']} 的第 {page} 页{level}级评论")

                        # 请求子评论
                        success, msg, res_json = self.get_note_inner_comment(
                            comment, cursor, xsec_token, cookies_str, proxies
                        )

                        if not success:
                            raise Exception(msg)

                        # ========== 识别限流错误（code 300013）==========
                        if "code" in res_json and res_json["code"] == API_CODE_RATE_LIMITED:
                            # 访问频次异常
                            rate_limit_msg = res_json.get('msg', '访问频次异常')

                            if retry_count < SUB_COMMENT_MAX_RETRIES - 1:
                                # 还有重试机会，切换Cookie
                                logger.warning(f"⚠️  限流（code {API_CODE_RATE_LIMITED}：{rate_limit_msg}），切换Cookie重试 ({retry_count+1}/{SUB_COMMENT_MAX_RETRIES})")
                                raise Exception(f"RateLimited_{retry_count}")  # 触发外层重试
                            else:
                                # 最后一次重试，等待后再试
                                logger.warning(f"⚠️  所有Cookie都限流，等待 {SUB_COMMENT_RETRY_WAIT} 秒后最后一次重试...")
                                time.sleep(SUB_COMMENT_RETRY_WAIT)
                                # 重新获取Cookie再试一次
                                success, cookies_str = cookie_provider()
                                if not success:
                                    raise Exception("等待后仍无可用Cookie")
                                continue  # 继续当前while循环，用新Cookie重试

                        # 检查数据格式
                        if "data" not in res_json or "comments" not in res_json["data"]:
                            raise Exception(f"API返回数据格式错误: {res_json}")

                        # 提取评论
                        comments = res_json["data"]["comments"]
                        inner_comment_list.extend(comments)
                        logger.debug(f"  成功获取 {len(comments)} 条子评论")

                        # 增量保存：立即保存每条获取到的子评论
                        if save_callback:
                            for sub_comment in comments:
                                try:
                                    # 添加层级信息
                                    sub_comment['_level'] = level
                                    sub_comment['_parent_id'] = comment.get('id', '')
                                    save_callback(sub_comment, level)
                                except Exception as e:
                                    logger.warning(f"保存子评论失败: {e}")

                        # 检查分页
                        if 'cursor' in res_json["data"]:
                            cursor = str(res_json["data"]["cursor"])
                        else:
                            break

                        if not res_json["data"]["has_more"]:
                            break

                        # 请求间隔（使用配置的3秒）
                        time.sleep(SUB_COMMENT_REQUEST_INTERVAL)

                    # 成功获取所有分页数据，跳出重试循环
                    fetch_success = True
                    break

                except Exception as e:
                    # 判断是否是限流错误需要重试
                    if "RateLimited_" in str(e):
                        # 限流错误，继续下一轮重试（切换Cookie）
                        continue
                    elif retry_count < SUB_COMMENT_MAX_RETRIES - 1:
                        # 其他错误，也尝试重试
                        logger.warning(f"获取失败: {e}，切换Cookie重试 ({retry_count+1}/{SUB_COMMENT_MAX_RETRIES})")
                        time.sleep(2)  # 短暂等待
                        continue
                    else:
                        # 最后一次重试也失败，记录错误
                        logger.error(f"评论 {comment['id']} 获取子评论失败（重试{SUB_COMMENT_MAX_RETRIES}次后）: {e}，保留原有{current_count}条数据")
                        break

            # 如果成功获取，替换为完整数据
            if fetch_success:
                comment['sub_comments'] = inner_comment_list
                actual_count = len(comment['sub_comments'])
                logger.info(f"✅ 评论 {comment['id']} 完整获取{level}级子评论成功：{actual_count}/{sub_comment_count} 条")
            else:
                logger.warning(f"⚠️  评论 {comment['id']} 未能获取完整子评论，保留原有{current_count}条数据")

            # 递归处理所有子评论的子评论
            for sub_comment in comment['sub_comments']:
                try:
                    self.get_note_all_inner_comment_with_provider(
                        sub_comment, xsec_token, cookie_provider, proxies, level + 1, max_level, save_callback
                    )
                except Exception as e:
                    logger.warning(f"{level+1}级评论 {sub_comment.get('id')} 获取失败: {e}，继续处理其他评论")

            return True, 'success', comment

        except Exception as e:
            return False, str(e), comment

    def get_note_all_comment(self, url: str, cookies_str: str, proxies: dict = None):
        """
            获取一篇文章的所有评论
            :param note_id: 你想要获取的笔记的id
            :param cookies_str: 你的cookies
            返回一篇文章的所有评论
        """
        out_comment_list = []
        success = True
        msg = "获取评论成功"

        try:
            urlParse = urllib.parse.urlparse(url)
            note_id = urlParse.path.split("/")[-1]
            kvDist = self._parse_url_params(urlParse.query)
            xsec_token = kvDist.get('xsec_token', '')
            success, msg, out_comment_list = self.get_note_all_out_comment(note_id, xsec_token, cookies_str, proxies)
            if not success:
                raise Exception(msg)
            
            # 递归统计所有层级评论的函数
            def count_all_comments(comment_list, level=1):
                """递归统计所有层级的评论数量"""
                count = len(comment_list)
                level_counts = {level: count}
                
                for comment in comment_list:
                    if 'sub_comments' in comment and comment['sub_comments']:
                        sub_counts = count_all_comments(comment['sub_comments'], level + 1)
                        for sub_level, sub_count in sub_counts.items():
                            if sub_level in level_counts:
                                level_counts[sub_level] += sub_count
                            else:
                                level_counts[sub_level] = sub_count
                        count += sum(sub_counts.values())
                
                return level_counts if level == 1 else {k: v for k, v in level_counts.items()}
            
            # 处理所有一级评论及其子评论
            for i, comment in enumerate(out_comment_list):
                success, msg, new_comment = self.get_note_all_inner_comment(comment, kvDist['xsec_token'], cookies_str, proxies)
                if success:
                    # 重要：将包含子评论的新评论对象赋值回列表
                    out_comment_list[i] = new_comment
                else:
                    logger.warning(f"获取评论 {comment.get('id', 'unknown')} 的子评论失败: {msg}")
            
            # 统计所有层级的评论
            level_counts = count_all_comments(out_comment_list)
            total_comments = sum(level_counts.values())
            
            logger.info(f"=== 评论统计 ===")
            for level, count in sorted(level_counts.items()):
                logger.info(f"{level}级评论: {count} 条")
            logger.info(f"所有评论总计: {total_comments} 条")
            
        except Exception as e:
            success = False
            msg = str(e)
            out_comment_list = []
            
        return success, msg, out_comment_list

    def get_unread_message(self, cookies_str: str, proxies: dict = None):
        """
            获取未读消息
            :param cookies_str: 你的cookies
            返回未读消息
        """
        res_json = None
        try:
            api = "/api/sns/web/unread_count"
            headers, cookies, data = generate_request_params(cookies_str, api)
            response = requests.get(self.base_url + api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_metions(self, cursor: str, cookies_str: str, proxies: dict = None):
        """
            获取评论和@提醒
            :param cursor: 你想要获取的评论和@提醒的cursor
            :param cookies_str: 你的cookies
            返回评论和@提醒
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/you/mentions"
            params = {
                "num": "20",
                "cursor": cursor
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_all_metions(self, cookies_str: str, proxies: dict = None):
        """
            获取全部的评论和@提醒
            :param cookies_str: 你的cookies
            返回全部的评论和@提醒
        """
        cursor = ''
        metions_list = []
        try:
            while True:
                success, msg, res_json = self.get_metions(cursor, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                metions = res_json["data"]["message_list"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                metions_list.extend(metions)
                if not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, metions_list

    def get_likesAndcollects(self, cursor: str, cookies_str: str, proxies: dict = None):
        """
            获取赞和收藏
            :param cursor: 你想要获取的赞和收藏的cursor
            :param cookies_str: 你的cookies
            返回赞和收藏
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/you/likes"
            params = {
                "num": "20",
                "cursor": cursor
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_all_likesAndcollects(self, cookies_str: str, proxies: dict = None):
        """
            获取全部的赞和收藏
            :param cookies_str: 你的cookies
            返回全部的赞和收藏
        """
        cursor = ''
        likesAndcollects_list = []
        try:
            while True:
                success, msg, res_json = self.get_likesAndcollects(cursor, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                likesAndcollects = res_json["data"]["message_list"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                likesAndcollects_list.extend(likesAndcollects)
                if not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, likesAndcollects_list

    def get_new_connections(self, cursor: str, cookies_str: str, proxies: dict = None):
        """
            获取新增关注
            :param cursor: 你想要获取的新增关注的cursor
            :param cookies_str: 你的cookies
            返回新增关注
        """
        res_json = None
        try:
            api = "/api/sns/web/v1/you/connections"
            params = {
                "num": "20",
                "cursor": cursor
            }
            splice_api = splice_str(api, params)
            headers, cookies, data = generate_request_params(cookies_str, splice_api)
            response = requests.get(self.base_url + splice_api, headers=headers, cookies=cookies, proxies=proxies)
            res_json = response.json()
            success, msg = res_json["success"], res_json["msg"]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, res_json

    def get_all_new_connections(self, cookies_str: str, proxies: dict = None):
        """
            获取全部的新增关注
            :param cookies_str: 你的cookies
            返回全部的新增关注
        """
        cursor = ''
        connections_list = []
        try:
            while True:
                success, msg, res_json = self.get_new_connections(cursor, cookies_str, proxies)
                if not success:
                    raise Exception(msg)
                connections = res_json["data"]["message_list"]
                if 'cursor' in res_json["data"]:
                    cursor = str(res_json["data"]["cursor"])
                else:
                    break
                connections_list.extend(connections)
                if not res_json["data"]["has_more"]:
                    break
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, connections_list

    @staticmethod
    def get_note_no_water_video(note_id):
        """
            获取笔记无水印视频
            :param note_id: 你想要获取的笔记的id
            返回笔记无水印视频
        """
        success = True
        msg = '成功'
        video_addr = None
        try:
            headers = get_common_headers()
            url = f"https://www.xiaohongshu.com/explore/{note_id}"
            response = requests.get(url, headers=headers)
            res = response.text
            video_addr = re.findall(r'<meta name="og:video" content="(.*?)">', res)[0]
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, video_addr


    @staticmethod
    def get_note_no_water_img(img_url):
        """
            获取笔记无水印图片
            :param img_url: 你想要获取的图片的url
            返回笔记无水印图片
        """
        success = True
        msg = '成功'
        new_url = None
        try:
            # https://sns-webpic-qc.xhscdn.com/202403211626/c4fcecea4bd012a1fe8d2f1968d6aa91/110/0/01e50c1c135e8c010010000000018ab74db332_0.jpg!nd_dft_wlteh_webp_3
            if '.jpg' in img_url:
                img_id = '/'.join([split for split in img_url.split('/')[-3:]]).split('!')[0]
                # return f"http://ci.xiaohongshu.com/{img_id}?imageview2/2/w/1920/format/png"
                # return f"http://ci.xiaohongshu.com/{img_id}?imageview2/2/w/format/png"
                # return f'https://sns-img-hw.xhscdn.com/{img_id}'
                new_url = f'https://sns-img-qc.xhscdn.com/{img_id}'

            # 'https://sns-webpic-qc.xhscdn.com/202403231640/ea961053c4e0e467df1cc93afdabd630/spectrum/1000g0k0200n7mj8fq0005n7ikbllol6q50oniuo!nd_dft_wgth_webp_3'
            elif 'spectrum' in img_url:
                img_id = '/'.join(img_url.split('/')[-2:]).split('!')[0]
                # return f'http://sns-webpic.xhscdn.com/{img_id}?imageView2/2/w/1920/format/jpg'
                new_url = f'http://sns-webpic.xhscdn.com/{img_id}?imageView2/2/w/format/jpg'
            else:
                # 'http://sns-webpic-qc.xhscdn.com/202403181511/64ad2ea67ce04159170c686a941354f5/1040g008310cs1hii6g6g5ngacg208q5rlf1gld8!nd_dft_wlteh_webp_3'
                img_id = img_url.split('/')[-1].split('!')[0]
                # return f"http://ci.xiaohongshu.com/{img_id}?imageview2/2/w/1920/format/png"
                # return f"http://ci.xiaohongshu.com/{img_id}?imageview2/2/w/format/png"
                # return f'https://sns-img-hw.xhscdn.com/{img_id}'
                new_url = f'https://sns-img-qc.xhscdn.com/{img_id}'
        except Exception as e:
            success = False
            msg = str(e)
        return success, msg, new_url

if __name__ == '__main__':
    """
        此文件为小红书api的使用示例
        所有涉及数据爬取的api都在此文件中
        数据注入的api违规请勿尝试
    """
    xhs_apis = XHS_Apis()
    cookies_str = r''
    # 获取用户信息
    user_url = 'https://www.xiaohongshu.com/user/profile/67a332a2000000000d008358?xsec_token=ABTf9yz4cLHhTycIlksF0jOi1yIZgfcaQ6IXNNGdKJ8xg=&xsec_source=pc_feed'
    success, msg, user_info = xhs_apis.get_user_info('67a332a2000000000d008358', cookies_str)
    logger.info(f'获取用户信息结果 {json.dumps(user_info, ensure_ascii=False)}: {success}, msg: {msg}')
    success, msg, note_list = xhs_apis.get_user_all_notes(user_url, cookies_str)
    logger.info(f'获取用户所有笔记结果 {json.dumps(note_list, ensure_ascii=False)}: {success}, msg: {msg}')
    # 获取笔记信息
    note_url = r'https://www.xiaohongshu.com/explore/67d7c713000000000900e391?xsec_token=AB1ACxbo5cevHxV_bWibTmK8R1DDz0NnAW1PbFZLABXtE=&xsec_source=pc_user'
    success, msg, note_info = xhs_apis.get_note_info(note_url, cookies_str)
    logger.info(f'获取笔记信息结果 {json.dumps(note_info, ensure_ascii=False)}: {success}, msg: {msg}')
    # 获取搜索关键词
    query = "榴莲"
    success, msg, search_keyword = xhs_apis.get_search_keyword(query, cookies_str)
    logger.info(f'获取搜索关键词结果 {json.dumps(search_keyword, ensure_ascii=False)}: {success}, msg: {msg}')
    # 搜索笔记
    query = "榴莲"
    query_num = 10
    sort = "general"
    note_type = 0
    success, msg, notes = xhs_apis.search_some_note(query, query_num, cookies_str, sort, note_type)
    logger.info(f'搜索笔记结果 {json.dumps(notes, ensure_ascii=False)}: {success}, msg: {msg}')
    # 获取笔记评论
    note_url = r'https://www.xiaohongshu.com/explore/67d7c713000000000900e391?xsec_token=AB1ACxbo5cevHxV_bWibTmK8R1DDz0NnAW1PbFZLABXtE=&xsec_source=pc_user'
    success, msg, note_all_comment = xhs_apis.get_note_all_comment(note_url, cookies_str)
    logger.info(f'获取笔记评论结果 {json.dumps(note_all_comment, ensure_ascii=False)}: {success}, msg: {msg}')




