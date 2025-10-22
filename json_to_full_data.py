# encoding: utf-8
"""
解析JSON文件，获取笔记的完整信息并保存
实现步骤2：读取JSON文件，爬取完整的笔记信息（包括图片、视频、文字、评论）
"""

import json
import os
import time
import traceback
from datetime import datetime
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, download_note, handle_comment_info
from progress_manager import ProgressManager


def parse_comment_count(count_str):
    """
    解析评论数量字符串，支持中文"万"和英文"w"

    示例:
    - "2.1万" -> 21000
    - "3.5w" -> 35000
    - "1234" -> 1234
    - 1234 -> 1234

    :param count_str: 评论数量字符串或整数
    :return: 整数形式的评论数量
    """
    try:
        # 如果已经是整数，直接返回
        if isinstance(count_str, int):
            return count_str

        # 如果是字符串，进行解析
        if isinstance(count_str, str):
            count_str = count_str.strip()

            # 处理包含"万"的情况
            if '万' in count_str:
                num_str = count_str.replace('万', '').strip()
                return int(float(num_str) * 10000)

            # 处理包含"w"或"W"的情况
            elif 'w' in count_str.lower():
                num_str = count_str.replace('w', '').replace('W', '').strip()
                return int(float(num_str) * 10000)

            # 纯数字字符串
            else:
                return int(count_str)

        # 其他类型返回0
        return 0
    except Exception as e:
        logger.warning(f"解析评论数量失败: {count_str}, 错误: {e}")
        return 0


class JsonToFullData:
    """
    解析JSON文件并获取完整笔记信息的类
    """

    def __init__(self, cookie_pool=None):
        """
        初始化类实例

        :param cookie_pool: Cookie池实例，用于自动切换Cookie重试
        """
        self.xhs_apis = XHS_Apis()
        self.cookie_pool = cookie_pool
        self.progress_manager = None  # 将在process时初始化
        
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

    def get_with_cookie_pool_retry(self, api_func, *args, **kwargs):
        """
        使用Cookie池所有账号进行重试
        遍历整个池，只有所有Cookie都失败才放弃

        :param api_func: 要调用的API方法
        :param args: API方法的位置参数
        :param kwargs: API方法的关键字参数（不包含cookies_str）
        :return: success, msg, data, account（使用的账号）
        """
        if not self.cookie_pool:
            # 如果没有Cookie池，使用传入的cookies_str
            if 'cookies_str' in kwargs:
                try:
                    success, msg, data = api_func(*args, **kwargs)
                    return success, msg, data, None
                except Exception as e:
                    return False, str(e), None, None
            else:
                return False, "未提供Cookie且Cookie池不可用", None, None

        tried_cookie_ids = set()  # 记录已尝试的Cookie ID
        total_accounts = len(self.cookie_pool.accounts)

        if total_accounts == 0:
            logger.error("Cookie池中没有可用账号")
            return False, "Cookie池为空", None, None

        logger.info(f"Cookie池共有 {total_accounts} 个账号可供重试")

        wait_rounds = 0  # 等待轮数计数器
        max_wait_rounds = 3  # 最大等待轮数

        while len(tried_cookie_ids) < total_accounts:
            # 获取可用账号
            account = self.cookie_pool.get_available_account()

            if not account:
                # 如果没有可用账号，检查是否所有账号都已尝试过
                if len(tried_cookie_ids) >= total_accounts:
                    logger.error("所有Cookie账号均已尝试")
                    break

                # 如果还有未尝试的账号，但暂时都不可用（可能在冷却中）
                if wait_rounds < max_wait_rounds:
                    wait_rounds += 1
                    wait_time = 2  # 等待2秒让账号冷却
                    logger.warning(f"所有账号暂时不可用，等待 {wait_time} 秒后重试 (第 {wait_rounds}/{max_wait_rounds} 轮)")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"等待 {max_wait_rounds} 轮后仍无可用账号")
                    break

            # 跳过已尝试的Cookie
            if account.cookie_id in tried_cookie_ids:
                continue

            tried_cookie_ids.add(account.cookie_id)
            logger.info(f"尝试Cookie账号: {account.name} ({len(tried_cookie_ids)}/{total_accounts})")

            try:
                # 调用API，传入Cookie
                success, msg, data = api_func(*args, cookies_str=account.cookie_str, **kwargs)

                if success:
                    self.cookie_pool.mark_account_success(account.cookie_id)
                    logger.info(f"✅ Cookie {account.name} 请求成功")
                    return success, msg, data, account
                else:
                    self.cookie_pool.mark_account_error(account.cookie_id, msg)
                    logger.warning(f"❌ Cookie {account.name} 失败: {msg}，切换下一个")

            except Exception as e:
                self.cookie_pool.mark_account_error(account.cookie_id, str(e))
                logger.warning(f"❌ Cookie {account.name} 异常: {e}，切换下一个")

        # 所有Cookie都失败
        logger.error(f"所有 {total_accounts} 个Cookie账号均已尝试失败")
        return False, f"所有Cookie账号({total_accounts}个)均失败", None, None

    def save_comments_streaming(self, note_id: str, xsec_token: str, output_file: str,
                                expected_comment_count: int = 0, cookies_str: str = None,
                                proxies: dict = None):
        """
        流式获取评论，每页立即保存到JSONL文件（支持断点续传）
        失败时遍历所有Cookie重试

        :param note_id: 笔记ID
        :param xsec_token: xsec_token参数
        :param output_file: 输出的JSONL文件路径
        :param expected_comment_count: 预期的评论总数（从笔记基本信息获取）
        :param proxies: 代理设置
        :return: 获取到的总评论数
        """
        # ========== 断点续传：检查是否有之前的进度 ==========
        resume_cursor = ''
        resume_page = 0
        resume_total = 0

        if self.progress_manager:
            note_progress = self.progress_manager.get_note_progress(note_id)
            comments_progress = note_progress.get('comments', {})

            if comments_progress.get('last_cursor'):
                resume_cursor = comments_progress['last_cursor']
                resume_total = comments_progress.get('total_fetched', 0)
                resume_page = resume_total // 10  # 假设每页10条
                logger.info(f"🔄 检测到评论断点，从第 {resume_page + 1} 页继续（已有{resume_total}条）")

        cursor = resume_cursor
        page = resume_page
        total_comments = resume_total

        # ========== 设置预期评论总数 ==========
        if self.progress_manager and expected_comment_count > 0:
            logger.info(f"📊 设置预期评论总数: {expected_comment_count:,}")
            self.progress_manager.update_comments_progress(
                note_id=note_id,
                total_expected=expected_comment_count
            )

        # 创建或追加评论文件
        file_mode = 'a' if resume_total > 0 else 'w'
        if file_mode == 'w':
            # 首次获取，清空文件
            with open(output_file, 'w', encoding='utf-8') as f:
                pass

        logger.info(f"开始流式获取评论: note_id={note_id} (从cursor={cursor[:20] if cursor else '开头'})")

        while True:
            page += 1
            # 保存当前页的cursor（用于断点续传）
            current_page_cursor = cursor

            # 计算进度百分比（如果有预期数量）
            progress_info = ""
            if expected_comment_count > 0 and total_comments > 0:
                progress_pct = (total_comments / expected_comment_count) * 100
                progress_info = f" | 进度: {total_comments:,}/{expected_comment_count:,} ({progress_pct:.1f}%)"

            logger.info(f"📄 正在获取第 {page} 页一级评论{progress_info}")

            # ========== 实时更新当前页数 ==========
            if self.progress_manager:
                self.progress_manager.update_comments_progress(
                    note_id=note_id,
                    current_page=page
                )

            # 使用Cookie池全遍历重试
            success, msg, res_json, account = self.get_with_cookie_pool_retry(
                self.xhs_apis.get_note_out_comment,
                note_id, cursor, xsec_token,
                proxies=proxies
            )

            if not success:
                error_msg = f"第 {page} 页获取失败（所有Cookie已尝试）: {msg}"
                logger.error(error_msg)
                # ========== 记录错误到进度 ==========
                if self.progress_manager:
                    self.progress_manager.update_comments_progress(
                        note_id=note_id,
                        error=error_msg
                    )
                break

            # 检查返回数据结构
            if not res_json or 'data' not in res_json:
                warning_msg = f"第 {page} 页返回数据异常，停止获取"
                logger.warning(warning_msg)
                # ========== 记录警告到进度 ==========
                if self.progress_manager:
                    self.progress_manager.update_comments_progress(
                        note_id=note_id,
                        warning=warning_msg
                    )
                break

            data = res_json.get('data', {})

            # 检查是否有comments字段
            if 'comments' not in data:
                warning_msg = f"第 {page} 页返回data中没有comments字段"
                logger.warning(warning_msg)
                logger.debug(f"返回数据: {res_json}")

                # 如果是第1页且data为空，很可能是xsec_token过期
                if page == 1 and data == {}:
                    error_msg = "xsec_token已过期或Cookie权限不足，评论API返回空数据"
                    logger.error("=" * 60)
                    logger.error("❌ 评论API返回空数据，可能原因：")
                    logger.error("   1. xsec_token已过期（最常见）")
                    logger.error("   2. Cookie权限不足")
                    logger.error("   3. 笔记评论被限制或已删除")
                    logger.error("")
                    logger.error("💡 解决方案：")
                    logger.error("   • 方案A: 重新搜索该关键词，获取新的笔记URL")
                    logger.error("   • 方案B: 浏览器访问笔记页面，复制新URL（包含最新xsec_token）")
                    logger.error("   • 方案C: 更新Cookie池中的Cookie")
                    logger.error("=" * 60)
                    # ========== 记录错误到进度 ==========
                    if self.progress_manager:
                        self.progress_manager.update_comments_progress(
                            note_id=note_id,
                            error=error_msg
                        )
                else:
                    # ========== 记录警告到进度 ==========
                    if self.progress_manager:
                        self.progress_manager.update_comments_progress(
                            note_id=note_id,
                            warning=warning_msg
                        )
                break

            comments = data['comments']
            has_more = data.get('has_more', False)

            # ✅ 增量保存评论（每获取一条就立即保存）
            if comments:
                logger.info(f"第 {page} 页获取到 {len(comments)} 条一级评论，开始增量获取并保存所有层级的子评论...")

                # 定义Cookie提供函数
                def get_cookie_for_comment():
                    """为评论获取提供Cookie（支持Cookie池和单Cookie）"""
                    # 优先使用当前请求的account（Cookie池）
                    if account and account.cookie_str:
                        return True, account.cookie_str
                    # 其次尝试从Cookie池获取新账号
                    elif self.cookie_pool:
                        temp_account = self.cookie_pool.get_available_account()
                        if temp_account:
                            return True, temp_account.cookie_str
                    # 最后使用提供的cookies_str（单Cookie模式）
                    elif cookies_str:
                        return True, cookies_str
                    # 都没有则返回失败
                    logger.error("❌ 无可用Cookie：既没有Cookie池也没有提供cookies_str参数")
                    return False, None

                # 创建增量保存回调函数（每获取一条子评论就立即保存）
                page_saved_count = 0  # 本页已保存的评论计数（包括子评论）
                last_progress_update = 0  # 上次更新进度时的评论数

                def save_comment_callback(comment_data, level):
                    """
                    增量保存单条评论的回调函数（增强版：实时更新进度）
                    :param comment_data: 评论数据（已包含_level和_parent_id）
                    :param level: 评论层级
                    """
                    nonlocal page_saved_count, total_comments, last_progress_update
                    try:
                        # 添加note_id字段
                        comment_data['note_id'] = note_id

                        # 立即追加到JSONL文件
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(comment_data, ensure_ascii=False) + '\n')
                            f.flush()  # 立即刷新到磁盘

                        page_saved_count += 1
                        total_comments += 1

                        # ========== ✅ 每50条更新一次进度（实时性） ==========
                        if self.progress_manager and (total_comments - last_progress_update) >= 50:
                            self.progress_manager.update_comments_progress(
                                note_id=note_id,
                                total_fetched=total_comments,
                                current_page=page
                            )
                            last_progress_update = total_comments
                            logger.debug(f"    🔄 实时进度已更新: {total_comments:,} 条评论")

                        # 每100条打印一次进度
                        if page_saved_count % 100 == 0:
                            logger.debug(f"    已增量保存 {page_saved_count} 条评论（累计: {total_comments:,}）")
                    except Exception as e:
                        logger.warning(f"    保存评论失败: {e}")

                # 处理每条一级评论，获取所有层级的子评论
                for idx, comment in enumerate(comments, 1):
                    # 先保存一级评论本身
                    comment['note_id'] = note_id
                    comment['_level'] = 1  # 一级评论
                    comment['_parent_id'] = ''  # 一级评论无父级

                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(comment, ensure_ascii=False) + '\n')
                        f.flush()

                    page_saved_count += 1
                    total_comments += 1

                    # 检查是否有子评论
                    sub_count = comment.get('sub_comment_count', 0)
                    logger.debug(f"  [{idx}/{len(comments)}] 评论 {comment.get('id', 'N/A')[:20]}, sub_comment_count={sub_count}")

                    if isinstance(sub_count, str):
                        sub_count = int(sub_count) if sub_count.isdigit() else 0

                    if sub_count > 0:
                        logger.info(f"  💬 [{idx}/{len(comments)}] 评论ID: {comment.get('id', 'N/A')[:16]}... | 预期子评论: {sub_count:,} 条")

                        try:
                            # 使用新方法获取所有层级的子评论，传入保存回调
                            sub_start_time = time.time()
                            success, msg, full_comment = self.xhs_apis.get_note_all_inner_comment_with_provider(
                                comment, xsec_token, get_cookie_for_comment, proxies,
                                level=2, max_level=10,  # 最多支持10层评论
                                save_callback=save_comment_callback  # ✅ 传入增量保存回调
                            )
                            sub_elapsed = time.time() - sub_start_time

                            if success:
                                actual_sub_count = len(full_comment.get('sub_comments', []))
                                logger.info(f"  ✅ 子评论获取完成 | 实际获取: {actual_sub_count:,} 条 | 耗时: {sub_elapsed:.1f}秒")

                                # 如果实际获取数少于预期，发出警告
                                if actual_sub_count < sub_count * 0.9:  # 允许10%的误差
                                    warning_msg = f"子评论数量不足：预期{sub_count}条，实际{actual_sub_count}条 ({actual_sub_count/sub_count*100:.1f}%)"
                                    logger.warning(f"  ⚠️ {warning_msg}")
                                    if self.progress_manager:
                                        self.progress_manager.update_comments_progress(
                                            note_id=note_id,
                                            warning=warning_msg
                                        )
                            else:
                                warning_msg = f"子评论获取失败: {msg}"
                                logger.warning(f"  ❌ {warning_msg}")
                                # ========== 记录警告到进度 ==========
                                if self.progress_manager:
                                    self.progress_manager.update_comments_progress(
                                        note_id=note_id,
                                        warning=warning_msg
                                    )

                        except Exception as e:
                            warning_msg = f"处理评论异常: {e}"
                            logger.warning(f"  ⚠️ {warning_msg}，继续处理下一条")
                            # ========== 记录警告到进度 ==========
                            if self.progress_manager:
                                self.progress_manager.update_comments_progress(
                                    note_id=note_id,
                                    warning=warning_msg
                                )

                logger.info(f"✅ 第 {page} 页已增量保存 {page_saved_count} 条评论（累计: {total_comments}）")
            else:
                logger.info(f"第 {page} 页没有评论数据，停止获取")
                break

            # 检查是否还有更多
            if not has_more:
                logger.info(f"has_more为False，评论获取完成")
                # 标记评论获取完成，保存最后状态
                if self.progress_manager:
                    self.progress_manager.update_comments_progress(
                        note_id=note_id,
                        total_fetched=total_comments,
                        last_cursor=cursor,  # 保存当前cursor（已经是最后一页了）
                        completed=True
                    )
                break

            # 获取下一页cursor
            if 'cursor' in data:
                next_cursor = str(data['cursor'])
                logger.debug(f"下一页cursor: {next_cursor}")

                # ========== 更新评论进度（支持断点续传）==========
                # 重要：在成功处理完当前页后，保存下一页的cursor
                # 这样断点续传时，会从下一页开始，不会重复也不会丢失数据
                if self.progress_manager:
                    self.progress_manager.update_comments_progress(
                        note_id=note_id,
                        total_fetched=total_comments,
                        last_cursor=next_cursor,  # ✅ 保存下一页的cursor作为断点
                        current_page=page
                    )

                # 更新cursor为下一页
                cursor = next_cursor
            else:
                logger.info("没有cursor字段，评论获取完成")
                # 标记评论获取完成，保存最后状态
                if self.progress_manager:
                    self.progress_manager.update_comments_progress(
                        note_id=note_id,
                        total_fetched=total_comments,
                        last_cursor=cursor,  # 保存最后一个cursor
                        completed=True
                    )
                break

            # 避免请求过快
            time.sleep(0.5)

        # 如果循环正常结束（不是break退出），说明可能有异常
        # 不应该无条件标记为完成，因为可能是因为错误提前退出
        logger.info(f"📊 评论获取结束，共 {total_comments:,} 条评论（包含所有层级）保存到: {output_file}")

        # 计算完成度
        if expected_comment_count > 0:
            completion_pct = (total_comments / expected_comment_count) * 100
            if completion_pct < 50:
                logger.warning(f"⚠️ 完成度过低: {completion_pct:.1f}% ({total_comments:,}/{expected_comment_count:,})")
                logger.warning(f"💡 可能的原因：")
                logger.warning(f"  1. xsec_token已过期（最常见） - 需要重新获取URL")
                logger.warning(f"  2. Cookie权限不足或限流 - 尝试使用Cookie池")
                logger.warning(f"  3. API返回has_more=false但实际还有更多数据 - 可能是小红书的限制")
            elif completion_pct < 90:
                logger.info(f"📈 完成度: {completion_pct:.1f}% ({total_comments:,}/{expected_comment_count:,})")
            else:
                logger.success(f"✅ 完成度: {completion_pct:.1f}% ({total_comments:,}/{expected_comment_count:,})")

        return total_comments

    def get_note_full_info(self, note_url: str, cookies_str: str = None, output_dir: str = None,
                           proxies: dict = None, include_comments: bool = True):
        """
        获取单个笔记的完整信息（支持分步保存和Cookie池重试）

        :param note_url: 笔记URL
        :param cookies_str: 小红书cookies字符串（如果使用Cookie池则可选）
        :param output_dir: 输出目录（如果指定则分步保存文件）
        :param proxies: 代理设置
        :param include_comments: 是否包含评论数据
        :return: 成功状态, 消息, 笔记完整信息
        """
        try:
            # 步骤1: 获取笔记基本信息（使用Cookie池重试）
            logger.info(f'开始获取笔记基本信息: {note_url}')

            if self.cookie_pool:
                # 使用Cookie池重试
                success, msg, note_info, account = self.get_with_cookie_pool_retry(
                    self.xhs_apis.get_note_info,
                    note_url,
                    proxies=proxies
                )
            else:
                # 直接使用提供的Cookie
                success, msg, note_info = self.xhs_apis.get_note_info(note_url, cookies_str, proxies)
                account = None

            if not success:
                return False, f'获取笔记信息失败: {msg}', None

            # 处理笔记信息
            note_info = note_info['data']['items'][0]
            note_info['url'] = note_url
            processed_note = handle_note_info(note_info)
            note_id = processed_note['note_id']

            # 添加获取时间戳
            processed_note['crawl_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # ✅ 步骤2: 立即保存基本信息（如果指定了output_dir）
            if output_dir:
                basic_file = os.path.join(output_dir, f"note_{note_id}_basic.json")
                with open(basic_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_note, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ 笔记基本信息已保存: {basic_file}")

            # 步骤3: 流式获取和保存评论
            if include_comments:
                try:
                    # 提取xsec_token
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(note_url)
                    query_params = parse_qs(parsed.query)
                    xsec_token = query_params.get('xsec_token', [''])[0]

                    if not xsec_token:
                        logger.error(f"❌ URL中没有xsec_token参数，无法获取评论")
                        logger.error(f"建议：重新搜索关键词或访问笔记页面获取新URL")
                        processed_note['comments'] = []
                        processed_note['comment_count'] = 0
                        return True, '笔记基本信息获取成功，但缺少xsec_token无法获取评论', processed_note

                    if output_dir:
                        # 解析预期的评论总数
                        expected_count = parse_comment_count(processed_note.get('comment_count', 0))
                        logger.info(f"📊 笔记显示评论数: {processed_note.get('comment_count', '未知')}, 解析为: {expected_count:,}")

                        # 确定使用的cookie（优先使用account的cookie，否则使用传入的cookies_str）
                        cookie_to_use = account.cookie_str if account and hasattr(account, 'cookie_str') else cookies_str

                        # 流式保存到JSONL文件
                        comments_file = os.path.join(output_dir, f"note_{note_id}_comments.jsonl")
                        total_comments = self.save_comments_streaming(
                            note_id, xsec_token, comments_file,
                            expected_comment_count=expected_count,  # ✅ 传递预期评论数
                            cookies_str=cookie_to_use,  # ✅ 传递Cookie字符串
                            proxies=proxies
                        )
                        processed_note['comment_count'] = total_comments
                        processed_note['comments_file'] = comments_file
                        logger.info(f"✅ 评论数据已保存: {comments_file} (共{total_comments}条)")
                    else:
                        # 兼容旧模式：内存中获取评论
                        logger.info(f'获取评论数据（旧模式）: {note_url}')
                        if self.cookie_pool:
                            success, msg, comments, account = self.get_with_cookie_pool_retry(
                                self.xhs_apis.get_note_all_comment,
                                note_url,
                                proxies=proxies
                            )
                        else:
                            success, msg, comments = self.xhs_apis.get_note_all_comment(
                                note_url, cookies_str, proxies
                            )

                        if success and comments:
                            processed_note['comments'] = comments
                            logger.info(f'获取评论数据成功，共 {len(comments)} 条评论')
                        else:
                            processed_note['comments'] = []
                            logger.warning(f'获取评论数据失败: {msg}')

                except Exception as e:
                    processed_note['comments'] = []
                    processed_note['comment_count'] = 0
                    logger.warning(f'获取评论数据异常: {str(e)}')
            else:
                processed_note['comments'] = []
                processed_note['comment_count'] = 0

            # ✅ 步骤4: 保存或更新完整信息JSON（如果指定了output_dir）
            if output_dir:
                full_file = os.path.join(output_dir, f"note_{note_id}_full.json")
                with open(full_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_note, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ 笔记完整信息已保存: {full_file}")

            return True, '获取笔记完整信息成功', processed_note

        except Exception as e:
            error_msg = f'获取笔记完整信息失败: {str(e)}'
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            return False, error_msg, None
    
    def process_json_to_full_data(self, json_file_path: str = None, cookies_str: str = None,
                                 output_dir: str = None, include_comments: bool = True,
                                 download_media: bool = True, save_format: str = 'json',
                                 proxies: dict = None, note_data_list: list = None):
        """
        处理JSON文件或笔记数据列表，获取所有笔记的完整信息并保存

        :param json_file_path: 输入的JSON文件路径（与note_data_list二选一）
        :param cookies_str: 小红书cookies字符串（使用Cookie池时可选）
        :param output_dir: 输出目录，如果不指定则自动生成
        :param include_comments: 是否包含评论数据
        :param download_media: 是否下载媒体文件（图片、视频）
        :param save_format: 保存格式 'json', 'excel', 'all'
        :param proxies: 代理设置
        :param note_data_list: 直接传入笔记数据列表（与json_file_path二选一）✨新增
        :return: 成功状态, 消息, 处理结果统计
        """
        try:
            # ========== ✨ 新增：支持直接传入笔记数据 ==========
            if note_data_list is not None:
                # 从笔记数据中提取URL列表
                note_urls = []
                for note in note_data_list:
                    if 'note_url' in note:
                        note_urls.append(note['note_url'])
                    elif 'note_id' in note and 'xsec_token' in note:
                        note_url = f"https://www.xiaohongshu.com/explore/{note['note_id']}?xsec_token={note['xsec_token']}"
                        note_urls.append(note_url)

                if not note_urls:
                    return False, '笔记数据中没有有效的URL', {}

                # 使用笔记数据作为来源标识
                json_source = f"direct_data_{len(note_urls)}_notes"
                logger.info(f'直接处理 {len(note_urls)} 个笔记数据（无需JSON文件）')

            elif json_file_path is not None:
                # 传统方式：解析JSON文件
                parse_success, parse_msg, note_urls = self.parse_json_file(json_file_path)
                if not parse_success:
                    return False, parse_msg, {}
                json_source = json_file_path

            else:
                return False, '必须提供 json_file_path 或 note_data_list 参数之一', {}
            
            # 创建输出目录
            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if json_file_path:
                    json_filename = os.path.splitext(os.path.basename(json_file_path))[0]
                    output_dir = f"parsed_{json_filename}_{timestamp}"
                else:
                    output_dir = f"parsed_direct_data_{timestamp}"

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # ========== 初始化进度管理器（支持断点续爬）==========
            self.progress_manager = ProgressManager(output_dir, json_source)

            # 获取待处理笔记列表（自动跳过已完成）
            pending_note_urls = self.progress_manager.get_pending_notes(note_urls)

            if len(pending_note_urls) == 0:
                logger.success("🎉 所有笔记已处理完成！")
                # 读取汇总数据返回
                summary_file = os.path.join(output_dir, "summary_all_notes.json")
                if os.path.exists(summary_file):
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                    result_stats = {
                        'total_notes': len(note_urls),
                        'successful_notes': summary_data['process_info']['successful_notes'],
                        'failed_notes': summary_data['process_info']['failed_notes'],
                        'total_comments': summary_data['process_info']['total_comments'],
                        'output_directory': output_dir
                    }
                    return True, '所有笔记已完成', result_stats
                else:
                    return True, '所有笔记已完成', {}

            # 创建媒体文件目录
            if download_media:
                media_dir = os.path.join(output_dir, "media_files")
                if not os.path.exists(media_dir):
                    os.makedirs(media_dir)

            # 处理每个笔记
            successful_notes = []
            failed_notes = []
            total_comments_count = 0

            # 记录开始时间（用于估算剩余时间）
            process_start_time = time.time()

            for i, note_url in enumerate(pending_note_urls, 1):
                note_id = None
                try:
                    # ========== 显示详细进度 ==========
                    elapsed = time.time() - process_start_time
                    remaining_time = self.progress_manager.estimate_remaining_time(i - 1, elapsed)
                    stats = self.progress_manager.get_statistics()

                    progress_msg = (
                        f"\n{'='*60}\n"
                        f"[{i}/{len(pending_note_urls)}] 总进度: {stats['completed']}/{len(note_urls)} "
                        f"({stats['completed']/len(note_urls)*100:.1f}%)\n"
                        f"成功: {stats['completed']} | 失败: {stats['failed']} | "
                        f"剩余: {stats['pending']} | 预计剩余时间: {remaining_time}\n"
                        f"{'='*60}"
                    )
                    logger.info(progress_msg)

                    # ========== 标记笔记开始处理 ==========
                    note_id = self.progress_manager.extract_note_id(note_url)
                    if note_id:
                        self.progress_manager.mark_note_processing(note_id, note_url)

                    logger.info(f'正在处理笔记: {note_url}')

                    # 使用新的分步保存方法
                    success, msg, full_note_info = self.get_note_full_info(
                        note_url,
                        cookies_str=cookies_str,
                        output_dir=output_dir,  # 传递output_dir启用分步保存
                        proxies=proxies,
                        include_comments=include_comments
                    )

                    if success and full_note_info:
                        successful_notes.append(full_note_info)

                        # 统计评论数
                        comment_count = full_note_info.get('comment_count', 0)
                        total_comments_count += comment_count

                        # 下载媒体文件
                        if download_media:
                            try:
                                download_note(full_note_info, media_dir, 'media')
                                logger.info(f'媒体文件下载成功: {full_note_info["title"]}')
                            except Exception as e:
                                logger.warning(f'媒体文件下载失败: {str(e)}')

                        # ========== 标记笔记完成 ==========
                        if note_id:
                            details = {
                                'comments': {
                                    'enabled': include_comments,
                                    'total_fetched': comment_count,
                                    'completed': True
                                },
                                'media': {
                                    'enabled': download_media,
                                    'completed': True
                                }
                            }
                            self.progress_manager.mark_note_completed(note_id, details)

                        # 注意：单个笔记的JSON文件已经在get_note_full_info中保存，无需重复保存
                    else:
                        failed_notes.append({
                            'url': note_url,
                            'error': msg,
                            'note_id': note_id
                        })
                        logger.error(f'处理失败: {msg}')

                        # ========== 标记笔记失败 ==========
                        if note_id:
                            self.progress_manager.mark_note_failed(note_id, msg)

                except Exception as e:
                    # ========== 捕获任何未预期的异常，确保不中断整个批处理 ==========
                    error_msg = f'处理笔记时发生异常: {str(e)}'
                    logger.error(error_msg)
                    logger.debug(f"异常详情: {traceback.format_exc()}")

                    failed_notes.append({
                        'url': note_url,
                        'error': error_msg,
                        'note_id': note_id,
                        'exception': True
                    })

                    # 标记笔记失败
                    if note_id:
                        try:
                            self.progress_manager.mark_note_failed(note_id, error_msg)
                        except Exception as mark_error:
                            logger.warning(f"标记笔记失败状态时出错: {mark_error}")

                    # 继续处理下一个笔记
                    logger.info("⏭️  跳过当前笔记，继续处理下一个...")
            
            # 保存汇总数据
            summary_data = {
                'process_info': {
                    'source_json': json_file_path,
                    'total_notes': len(note_urls),
                    'successful_notes': len(successful_notes),
                    'failed_notes': len(failed_notes),
                    'total_comments': total_comments_count,
                    'include_comments': include_comments,
                    'download_media': download_media,
                    'process_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'comment_storage': 'JSONL files (*.jsonl)' if include_comments else 'None'
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

                # 注意：评论数据已保存为JSONL格式，不再自动转换为Excel
                # 如需Excel格式，可手动读取JSONL文件转换
                if include_comments and total_comments_count > 0:
                    logger.info(f'评论数据已保存为JSONL格式（每个笔记一个文件），共 {total_comments_count} 条评论')
                    logger.info(f'JSONL文件位置: {output_dir}/note_*_comments.jsonl')
            
            # 保存处理结果统计
            result_stats = {
                'total_notes': len(note_urls),
                'successful_notes': len(successful_notes),
                'failed_notes': len(failed_notes),
                'success_rate': len(successful_notes) / len(note_urls) * 100 if note_urls else 0,
                'total_comments': total_comments_count,
                'output_directory': output_dir
            }

            logger.success(f'处理完成！成功: {len(successful_notes)}, 失败: {len(failed_notes)}, 评论: {total_comments_count}条')
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