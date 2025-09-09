# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个专业的小红书数据采集解决方案，支持笔记爬取、用户信息获取和创作者平台功能。项目分为两个主要模块：
- **小红书PC端API** (`apis/xhs_pc_apis.py`) - 用于数据采集、搜索、用户信息获取
- **小红书创作者平台API** (`apis/xhs_creator_apis.py`) - 用于内容上传、作品管理

## 开发环境设置

### 安装依赖
```bash
pip install -r requirements.txt
npm install
```

### 环境配置
项目依赖 `.env` 文件配置 Cookie：
```
COOKIES=your_xiaohongshu_cookies_here
```

### 运行项目
```bash
python main.py
```

### Docker 部署
```bash
docker build -t spider-xhs .
docker run -p 5000:5000 spider-xhs
```

## 项目架构

### 核心组件

1. **main.py** - 主入口文件，包含 `Data_Spider` 类
   - `spider_note()` - 爬取单个笔记（支持评论数据）
   - `spider_some_note()` - 批量爬取笔记（支持评论数据）
   - `spider_user_all_note()` - 爬取用户所有笔记（支持评论数据）
   - `spider_some_search_note()` - 搜索并爬取笔记（支持评论数据）

2. **apis/** - API 接口层
   - `xhs_pc_apis.py` - 小红书PC端完整API集合（获取笔记详情、用户信息、搜索、评论等）
   - `xhs_creator_apis.py` - 创作者平台API（登录、上传、管理作品）

3. **xhs_utils/** - 工具函数层
   - `common_util.py` - 基础工具（环境初始化、路径管理）
   - `data_util.py` - 数据处理（笔记信息处理、评论信息处理、下载、Excel保存）
   - `xhs_util.py` - 小红书专用工具（请求参数生成、加密等）
   - `cookie_util.py` - Cookie处理工具
   - `xhs_creator_util.py` - 创作者相关工具

### 数据存储结构
```
datas/
├── media_datas/              # 图片和视频文件
│   └── 用户名_用户ID/
│       └── 标题_笔记ID/
│           ├── info.json     # 笔记完整信息
│           ├── comments.json # 评论数据（如果启用）
│           ├── detail.txt    # 笔记详情文本
│           ├── image_0.jpg   # 图片文件
│           └── video.mp4     # 视频文件
└── excel_datas/              # Excel格式的结构化数据
    ├── 文件名.xlsx           # 笔记数据
    └── 文件名_comments.xlsx  # 评论数据（单独文件）
```

## 关键技术点

### Cookie 认证机制
- 项目基于小红书Cookie进行认证
- Cookie需要从登录状态的浏览器获取
- 所有API调用都需要有效的Cookie字符串

### 请求参数生成
- 使用 `generate_request_params()` 生成符合小红书API要求的请求头和参数
- 包含 x-b3-traceid、加密签名等必要字段

### 数据处理流程
1. 通过API获取原始数据
2. 使用 `handle_note_info()` 处理笔记信息
3. 使用 `get_note_all_comment()` 获取评论数据（可选）
4. 使用 `handle_comment_info()` 处理评论信息
5. 支持多种保存格式：`'all'`、`'media'`、`'excel'`
6. 媒体文件自动去水印下载
7. 评论数据自动保存为独立Excel和JSON文件

### 评论数据功能
- **获取范围**: 获取笔记的所有一级评论和二级回复
- **数据字段**: 评论ID、用户信息、评论内容、点赞数、发布时间、IP归属地等
- **保存格式**: 
  - Excel: `{文件名}_comments.xlsx`
  - JSON: 每个笔记目录下的 `comments.json`
- **性能考虑**: 可通过 `include_comments=False` 跳过评论获取以提升速度

### 搜索功能配置
搜索API支持多维度筛选：
- `sort_type_choice`: 0=综合排序, 1=最新, 2=最多点赞, 3=最多评论, 4=最多收藏
- `note_type`: 0=不限, 1=视频笔记, 2=普通笔记  
- `note_time`: 0=不限, 1=一天内, 2=一周内, 3=半年内
- `note_range`: 0=不限, 1=已看过, 2=未看过, 3=已关注
- `pos_distance`: 0=不限, 1=同城, 2=附近（需配合geo参数）

## 使用示例

### 爬取指定笔记（包含评论）
```python
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init

cookies_str, base_path = init()
data_spider = Data_Spider()

# 包含评论数据的笔记爬取
notes = ['https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx']
data_spider.spider_some_note(notes, cookies_str, base_path, 'all', 'test_with_comments', include_comments=True)

# 不包含评论的快速爬取
data_spider.spider_some_note(notes, cookies_str, base_path, 'all', 'test_no_comments', include_comments=False)
```

### 用户所有笔记（包含评论）
```python
user_url = 'https://www.xiaohongshu.com/user/profile/xxx?xsec_token=xxx'
# 默认包含评论数据
data_spider.spider_user_all_note(user_url, cookies_str, base_path, 'all', include_comments=True)
```

### 关键词搜索（包含评论）
```python
data_spider.spider_some_search_note(
    query="关键词", 
    require_num=10, 
    cookies_str=cookies_str, 
    base_path=base_path, 
    save_choice='all',
    sort_type_choice=0,
    note_type=0,
    include_comments=True  # 是否包含评论数据
)
```

### 评论数据结构示例
```json
{
  "note_id": "笔记ID",
  "note_url": "笔记链接", 
  "comment_id": "评论ID",
  "user_id": "评论用户ID",
  "nickname": "用户昵称",
  "content": "评论内容",
  "like_count": 点赞数,
  "upload_time": "发布时间",
  "ip_location": "IP归属地",
  "pictures": ["评论图片URL列表"]
}
```

## 依赖说明

### Python依赖
- `requests` - HTTP请求
- `PyExecJS` - JavaScript执行（用于参数加密）
- `loguru` - 日志记录
- `python-dotenv` - 环境变量管理
- `retry` - 重试机制
- `openpyxl` - Excel文件处理

### JavaScript依赖  
- `jsdom` - DOM操作（Node.js环境下的浏览器模拟）

## 注意事项

- Cookie有时效性，需要定期更新
- 请求频率过高可能被限流，建议添加适当延时
- URL中的 `xsec_token` 参数会过期，需要及时使用
- 代理配置通过 `proxies` 参数传入（可选）
- 项目仅供学习交流使用，请遵守相关法律法规

## 两步法数据爬取功能

### 新增模块

项目新增了两个核心模块实现分步数据爬取：

1. **search_to_json.py** - 关键词搜索并保存JSON
   - `SearchToJson` 类：搜索指定关键词的笔记
   - `search_notes_to_json()` - 搜索笔记并保存为JSON格式
   - `batch_search_to_json()` - 批量搜索多个关键词
   - 输出目录：`search_results/`

2. **json_to_full_data.py** - JSON解析和完整信息爬取
   - `JsonToFullData` 类：处理JSON文件并获取完整笔记信息
   - `process_json_to_full_data()` - 解析JSON并爬取完整数据
   - `batch_process_json_files()` - 批量处理多个JSON文件
   - 支持下载图片、视频、获取评论数据

3. **two_step_spider_demo.py** - 统一工作流程演示
   - `TwoStepSpider` 类：整合两步法工作流程
   - `complete_spider_workflow()` - 完整的两步法流程
   - `batch_spider_workflow()` - 批量处理工作流程

### 使用优势

- **分步处理**：先搜索获取笔记列表，筛选后再详细爬取
- **灵活控制**：可以控制每一步的参数和范围
- **防止限流**：避免一次性请求过多数据
- **数据结构清晰**：JSON格式便于后续处理和分析
- **支持断点续传**：可以从JSON文件继续处理

### 使用示例

```python
# 两步法完整流程
from two_step_spider_demo import TwoStepSpider
from xhs_utils.common_util import init

cookies_str, base_path = init()
spider = TwoStepSpider()

# 单个关键词完整流程
success, msg, stats = spider.complete_spider_workflow(
    query="日本料理",
    require_num=20,
    cookies_str=cookies_str,
    include_comments=True,
    download_media=True,
    save_format='all'
)
```

### 数据保存结构

```
spider_work_{关键词}_{时间戳}/
├── search_{关键词}_{时间戳}.json    # 第一步：搜索结果JSON
└── full_data/                        # 第二步：完整数据
    ├── summary_all_notes.json        # 所有笔记汇总JSON
    ├── notes_data.xlsx               # 笔记数据Excel
    ├── comments_data.xlsx            # 评论数据Excel
    ├── note_{ID}_full.json           # 单个笔记完整JSON
    └── media_files/                  # 媒体文件目录
        ├── {用户名}_{用户ID}/
        │   └── {标题}_{笔记ID}/
        │       ├── info.json
        │       ├── comments.json
        │       ├── image_0.jpg
        │       └── video.mp4
```