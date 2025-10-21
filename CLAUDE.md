# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个专业的小红书数据采集解决方案，支持笔记爬取、用户信息获取和创作者平台功能。项目提供三种使用方式：
- **命令行模式** ([main.py](main.py)) - 传统爬虫脚本，适合自动化批量处理
- **Web界面模式** ([web_app.py](web_app.py)) - 提供友好的Web管理界面，适合交互式操作
- **Cookie池管理** ([cookie_pool.py](cookie_pool.py)) - 多账号轮换系统，防止限流

核心API模块：
- **小红书PC端API** ([apis/xhs_pc_apis.py](apis/xhs_pc_apis.py)) - 数据采集、搜索、用户信息获取
- **小红书创作者平台API** ([apis/xhs_creator_apis.py](apis/xhs_creator_apis.py)) - 内容上传、作品管理

## 开发环境设置

### 安装依赖
```bash
# Python依赖
pip install -r requirements.txt

# JavaScript依赖（用于加密参数生成）
npm install
```

### 环境配置
在项目根目录创建 `.env` 文件：
```env
COOKIES=your_xiaohongshu_cookies_here
```

**获取Cookie**: 浏览器F12 → Network → 找到任意请求 → 复制Request Headers中的Cookie值

### 运行方式

#### 命令行模式
```bash
python main.py
```

#### Web界面模式（推荐）
```bash
# 启动Web服务
python start_web.py

# 访问 http://localhost:5000
# 提供关键词搜索、结果预览、详细解析等功能
```

#### Cookie池管理（多账号）
```bash
# 启动Cookie池管理界面
python start_json_manager.py

# 访问 http://localhost:5001
# 管理多个Cookie账号，实现轮换和限流控制
```

## 项目架构

### 核心工作流程

项目支持两种工作流程：

**1. 传统单步流程**（[main.py](main.py)）
```
搜索/指定URL → 获取笔记详情 → 下载媒体 → 保存数据
```

**2. 两步法流程**（推荐，[search_to_json.py](search_to_json.py) + [json_to_full_data.py](json_to_full_data.py)）
```
步骤1: 搜索并保存JSON → 步骤2: 解析JSON并获取完整数据
```

两步法的优势：
- 可以先预览搜索结果，筛选后再爬取
- 防止一次性请求过多导致限流
- 支持断点续传，可从JSON继续处理

### 关键类和方法

**Data_Spider类** ([main.py:9](main.py#L9))
- `spider_note(note_url, cookies_str, include_comments=True)` - 爬取单个笔记
- `spider_some_note(notes, cookies_str, save_choice, include_comments=True)` - 批量爬取
- `spider_user_all_note(user_url, cookies_str, include_comments=True)` - 爬取用户所有笔记
- `spider_some_search_note(query, require_num, sort_type_choice=0, include_comments=True)` - 搜索并爬取

**XHS_Apis类** ([apis/xhs_pc_apis.py:13](apis/xhs_pc_apis.py#L13))
- `get_note_info(note_url, cookies_str)` - 获取笔记详情
- `get_note_all_comment(note_url, cookies_str)` - 获取所有评论
- `search_some_note(query, require_num, cookies_str, sort_type_choice)` - 搜索笔记
- `get_user_all_note(user_url, cookies_str)` - 获取用户笔记列表

**SearchToJson类** ([search_to_json.py:16](search_to_json.py#L16))
- `search_notes_to_json(query, require_num, cookies_str, output_file)` - 搜索并保存JSON
- `batch_search_to_json(queries, require_num, cookies_str)` - 批量搜索多个关键词

**JsonToFullData类** ([json_to_full_data.py:16](json_to_full_data.py#L16))
- `parse_json_file(json_file_path)` - 解析JSON文件提取URL列表
- `process_json_to_full_data(json_file_path, cookies_str, include_comments, download_media)` - 完整数据爬取

**CookiePool类** ([cookie_pool.py](cookie_pool.py))
- `add_cookie(cookie_str, name, remark)` - 添加Cookie账号
- `get_available_cookie()` - 获取可用的Cookie（自动轮换）
- `mark_success(cookie_id)` / `mark_failure(cookie_id)` - 标记成功/失败

### 工具函数层

**[xhs_utils/xhs_util.py](xhs_utils/xhs_util.py)** - 小红书专用工具
- `generate_request_params(cookies_str, api, data)` - 生成请求参数（含加密签名）
- `generate_x_b3_traceid()` - 生成追踪ID
- `generate_xs_xs_common(a1, api, data)` - 生成xs和xs_common参数

**[xhs_utils/data_util.py](xhs_utils/data_util.py)** - 数据处理工具
- `handle_note_info(note_info)` - 处理笔记信息为结构化数据
- `handle_comment_info(comment)` - 处理评论信息
- `download_note(note_info, base_path)` - 下载笔记媒体文件（去水印）
- `save_to_xlsx(data_list, file_path, data_type='note')` - 保存为Excel

**[xhs_utils/common_util.py](xhs_utils/common_util.py)** - 基础工具
- `init()` - 初始化环境（读取.env，创建目录结构）

### 数据存储结构

```
datas/
├── media_datas/              # 媒体文件存储
│   └── {用户名}_{用户ID}/
│       └── {标题}_{笔记ID}/
│           ├── info.json     # 笔记完整信息（JSON格式）
│           ├── comments.json # 评论数据（如果启用）
│           ├── detail.txt    # 笔记详情文本
│           ├── image_0.jpg   # 图片文件（无水印）
│           └── video.mp4     # 视频文件（无水印）
└── excel_datas/              # Excel格式数据
    ├── {文件名}.xlsx         # 笔记数据汇总
    └── {文件名}_comments.xlsx # 评论数据汇总

search_results/               # 搜索结果JSON
└── search_{关键词}_{时间戳}.json

parsed_*/                     # 解析后的完整数据
├── summary_all_notes.json    # 所有笔记汇总
├── note_{ID}_full.json       # 单个笔记完整JSON
├── notes_data.xlsx           # 笔记Excel
├── comments_data.xlsx        # 评论Excel
└── media_files/              # 媒体文件
```

## 关键技术点

### Cookie认证机制
- 所有API请求依赖有效的Cookie进行认证
- Cookie从浏览器获取，有时效性（通常几天到几周）
- 支持多Cookie轮换（使用Cookie池功能）

### 请求参数加密
核心在 [xhs_utils/xhs_util.py:78](xhs_utils/xhs_util.py#L78) 的 `generate_headers()`:
- 使用PyExecJS调用JavaScript生成加密参数
- 生成 `x-s`, `x-t`, `x-s-common` 等必要字段
- JavaScript加密文件: [static/xhs_xs_xsc_56.js](static/xhs_xs_xsc_56.js)

### 评论数据获取
- 支持递归获取所有层级的评论（一级评论 + 二级回复）
- 评论数据字段：评论ID、用户信息、内容、点赞数、时间、IP归属地
- 可通过 `include_comments=False` 跳过评论获取以提升速度
- 保存格式：独立Excel文件 + 每个笔记目录下的JSON文件

### 搜索功能配置
在 `search_some_note()` 方法中支持的参数：
- `sort_type_choice`: 0=综合排序, 1=最新, 2=最多点赞, 3=最多评论, 4=最多收藏
- `note_type`: 0=不限, 1=视频笔记, 2=普通笔记
- `note_time`: 0=不限, 1=一天内, 2=一周内, 3=半年内
- `note_range`: 0=不限, 1=已看过, 2=未看过, 3=已关注
- `pos_distance`: 0=不限, 1=同城, 2=附近（需配合geo参数）

### Cookie池机制（防限流）
[cookie_pool.py](cookie_pool.py) 实现了智能Cookie管理：
- **账号管理**: 添加、删除、启用/禁用多个Cookie账号
- **自动轮换**: 根据使用次数和时间间隔自动切换账号
- **限流控制**: 每个账号设置最小请求间隔和每日限额
- **健康监控**: 追踪成功率、错误次数，自动禁用异常账号
- **冷却机制**: 失败后自动进入冷却期

配置文件: [cookie_pool_config.json](cookie_pool_config.json)

## 使用示例

### 命令行模式

#### 爬取指定笔记（包含评论）
```python
from main import Data_Spider
from xhs_utils.common_util import init

cookies_str, base_path = init()
spider = Data_Spider()

notes = [
    'https://www.xiaohongshu.com/explore/xxx?xsec_token=xxx',
    'https://www.xiaohongshu.com/explore/yyy?xsec_token=yyy'
]

# 包含评论，保存所有格式（media + excel）
spider.spider_some_note(
    notes,
    cookies_str,
    base_path,
    save_choice='all',
    excel_name='test_notes',
    include_comments=True
)
```

#### 搜索并爬取笔记
```python
spider.spider_some_search_note(
    query="日本料理",
    require_num=20,
    cookies_str=cookies_str,
    base_path=base_path,
    save_choice='all',
    excel_name='search_japanese_food',
    sort_type_choice=0,      # 综合排序
    note_type=0,             # 不限类型
    include_comments=True
)
```

#### 爬取用户所有笔记
```python
user_url = 'https://www.xiaohongshu.com/user/profile/xxx?xsec_token=xxx'
spider.spider_user_all_note(
    user_url,
    cookies_str,
    base_path,
    save_choice='all',
    excel_name='user_all_notes',
    include_comments=True
)
```

### 两步法模式（推荐）

#### 步骤1: 搜索并保存JSON
```python
from search_to_json import SearchToJson

searcher = SearchToJson()
success, msg, notes = searcher.search_notes_to_json(
    query="美妆",
    require_num=50,
    cookies_str=cookies_str,
    output_file="search_results/makeup_20250109.json",
    sort_type_choice=1  # 按最新排序
)
```

#### 步骤2: 解析JSON获取完整数据
```python
from json_to_full_data import JsonToFullData

parser = JsonToFullData()
success, msg, stats = parser.process_json_to_full_data(
    json_file_path="search_results/makeup_20250109.json",
    cookies_str=cookies_str,
    output_dir="parsed_makeup_20250109",
    include_comments=True,    # 获取评论
    download_media=True,      # 下载图片和视频
    save_format='all'         # 保存所有格式
)
```

### 使用Cookie池

#### 初始化Cookie池
```python
from cookie_pool import CookiePool

pool = CookiePool(config_file="cookie_pool_config.json")

# 添加多个Cookie账号
pool.add_cookie("cookie_string_1", "账号1", "主账号")
pool.add_cookie("cookie_string_2", "账号2", "备用账号")

# 保存配置
pool.save_config()
```

#### 使用Cookie池爬取
```python
# 获取可用Cookie（自动轮换）
success, cookie_str = pool.get_available_cookie()

if success:
    # 使用Cookie进行爬取
    spider.spider_note(note_url, cookie_str)

    # 标记成功（更新统计）
    pool.mark_success(cookie_str)
else:
    print("没有可用的Cookie账号")
```

## Web界面使用

### 启动Web应用
```bash
python start_web.py
```

访问 `http://localhost:5000`，主要功能：
- **关键词搜索**: 输入关键词，设置数量和筛选条件
- **结果预览**: 表格展示搜索结果（标题、作者、互动数据）
- **批量解析**: 一键解析所有搜索结果
- **详情查看**: 查看笔记完整内容（图片、视频、评论）
- **数据导出**: 下载JSON和Excel格式数据

Web架构说明:
- 后端: Flask ([web_app.py](web_app.py))
- 前端: Bootstrap 5 + JavaScript ([templates/index.html](templates/index.html))
- API接口: RESTful设计，支持异步任务
- 详细文档: [WEB_README.md](WEB_README.md)

### Cookie池Web管理
```bash
python start_json_manager.py
```

访问 `http://localhost:5001`，功能包括：
- 添加/删除/编辑Cookie账号
- 查看每个账号的使用统计
- 启用/禁用特定账号
- 实时监控账号健康状态

## 常见问题

### Cookie失效
**症状**: 请求返回401/403错误或"需要登录"
**解决**: 重新从浏览器获取Cookie并更新`.env`文件

### 请求限流
**症状**: 频繁返回空数据或错误
**解决**:
1. 降低请求频率（添加延时）
2. 使用Cookie池进行多账号轮换
3. 检查是否触发每日限额

### 评论获取失败
**症状**: 笔记数据正常但评论为空
**解决**:
1. 检查Cookie是否有效
2. 确认笔记确实有评论
3. 笔记可能限制评论可见性

### 媒体文件下载失败
**症状**: Excel有数据但图片/视频未下载
**解决**:
1. 检查网络连接
2. 确认 `save_choice='all'` 或 `'media'`
3. 检查磁盘空间

### JavaScript执行错误
**症状**: "execjs._exceptions.ProgramError"
**解决**:
1. 确保已安装Node.js
2. 运行 `npm install` 安装依赖
3. 检查 [static/xhs_xs_xsc_56.js](static/xhs_xs_xsc_56.js) 文件是否存在

## 注意事项

- **Cookie时效性**: Cookie会过期，建议定期更新或使用Cookie池
- **请求频率**: 避免过高频率，建议使用Cookie池的限流控制
- **URL时效**: 搜索结果中的 `xsec_token` 参数会过期，建议及时使用
- **代理支持**: 所有API方法都支持 `proxies` 参数传入代理配置
- **合规使用**: 本项目仅供学习研究，请遵守相关法律法规
- **数据量控制**: 批量爬取时建议分批次处理，避免一次性请求过多

## 依赖说明

### Python核心依赖
- `requests` - HTTP请求库
- `PyExecJS` - JavaScript执行引擎（用于参数加密）
- `loguru` - 日志记录
- `python-dotenv` - 环境变量管理
- `retry` - 重试机制
- `openpyxl` - Excel文件处理

### Web相关依赖（可选）
- `Flask` - Web框架
- `Flask-CORS` - 跨域支持

### JavaScript依赖
- `jsdom` - DOM操作（Node.js浏览器模拟）

## 参考文档

- 项目README: [README.md](README.md)
- Web使用文档: [WEB_README.md](WEB_README.md)
- API文档: 查看 [apis/xhs_pc_apis.py](apis/xhs_pc_apis.py) 中的方法注释
