# encoding: utf-8
"""
测试修复后的完整评论获取功能
"""

from json_to_full_data import JsonToFullData
from cookie_pool import CookiePool
from loguru import logger
import os

# 笔记URL（之前只获取了2.6%评论的笔记）
note_url = "https://www.xiaohongshu.com/explore/68d9f63b000000001201deab?app_platform=ios&app_version=9.4&share_from_user_hidden=true&xsec_source=app_share&type=normal&xsec_token=CBrGTCtHs74eKIsj5-x2OyzW9Oh6DE_WMyOWtsC6xpDcM=&author_share=1&xhsshare=WeixinSession&shareRedId=N0o7ODs4STs2NzUyOTgwNjY0OTc5ODhL&apptime=1760745609&share_id=6d98ac057d7d433ca19a2fbb908237c0"

# 输出目录
output_dir = "test_full_comments_output"

# 确保输出目录存在
os.makedirs(output_dir, exist_ok=True)

logger.info("="*60)
logger.info("测试修复后的完整评论获取功能")
logger.info("="*60)

# 初始化Cookie池
logger.info("初始化Cookie池...")
cookie_pool = CookiePool(config_file="cookie_pool_config.json")
logger.info(f"Cookie池中有 {len(cookie_pool.accounts)} 个账号")

# 初始化爬虫（使用Cookie池）
logger.info("初始化爬虫...")
processor = JsonToFullData(cookie_pool=cookie_pool)

# 获取完整笔记信息（包含所有层级的评论）
logger.info(f"开始获取笔记完整信息...")
logger.info(f"笔记URL: {note_url[:80]}...")

success, msg, full_note = processor.get_note_full_info(
    note_url=note_url,
    output_dir=output_dir,
    include_comments=True  # 获取所有层级的评论
)

logger.info("="*60)
if success:
    logger.success("✅ 测试成功！")
    logger.info(f"笔记标题: {full_note.get('title', 'N/A')}")
    logger.info(f"评论总数: {full_note.get('comment_count', 0)} 条（包含所有层级）")
    logger.info(f"数据保存在: {output_dir}/")
    logger.info(f"评论文件: {output_dir}/note_68d9f63b000000001201deab_comments.jsonl")

    # 读取并统计评论
    comments_file = os.path.join(output_dir, "note_68d9f63b000000001201deab_comments.jsonl")
    if os.path.exists(comments_file):
        import json

        total_comments = 0
        total_sub_comments = 0

        with open(comments_file, 'r', encoding='utf-8') as f:
            for line in f:
                comment = json.loads(line)
                total_comments += 1

                # 递归统计子评论
                def count_recursive(c):
                    count = len(c.get('sub_comments', []))
                    for sub in c.get('sub_comments', []):
                        count += count_recursive(sub)
                    return count

                sub_count = count_recursive(comment)
                total_sub_comments += sub_count

        logger.info(f"\n📊 统计结果:")
        logger.info(f"  一级评论: {total_comments} 条")
        logger.info(f"  所有子评论: {total_sub_comments} 条")
        logger.info(f"  总计: {total_comments + total_sub_comments} 条")

        # 与之前的数据对比
        logger.info(f"\n📈 对比之前的结果:")
        logger.info(f"  修复前: 1000条一级 + 331条子评论 = 1331条总评论（2.6%）")
        logger.info(f"  修复后: {total_comments}条一级 + {total_sub_comments}条子评论 = {total_comments + total_sub_comments}条总评论")

        if total_sub_comments > 10000:
            logger.success("🎉 修复成功！成功获取了所有层级的评论！")
        else:
            logger.warning("⚠️  子评论数量似乎仍然不完整，请检查日志")
else:
    logger.error(f"❌ 测试失败: {msg}")

logger.info("="*60)
