# 小红书数据爬取 Web 界面使用说明

## 🎯 功能概述

这是一个完整的小红书数据爬取Web应用，提供友好的前端界面，支持：

- **关键词搜索**: 输入关键词搜索相关笔记
- **结果展示**: 以表格形式展示搜索结果
- **详细解析**: 获取笔记完整信息（文字、图片、视频、评论）
- **实时进度**: 显示搜索和解析的实时进度
- **数据导出**: 支持JSON格式数据导出

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装Web应用依赖
pip install Flask Flask-CORS

# 或者使用requirements文件
pip install -r requirements_web.txt
```

### 2. 配置Cookie

在项目根目录创建或编辑 `.env` 文件：

```env
COOKIES=your_xiaohongshu_cookies_here
```

**获取Cookie步骤：**
1. 打开浏览器，登录小红书网页版
2. 按F12打开开发者工具
3. 切换到Network标签
4. 刷新页面，找到任意请求
5. 复制Request Headers中的Cookie值

### 3. 启动Web应用

```bash
# 方式1: 使用启动脚本（推荐）
python start_web.py

# 方式2: 直接运行
python web_app.py
```

### 4. 访问界面

打开浏览器访问：`http://localhost:5000`

## 📋 使用流程

### 步骤1: 关键词搜索

1. **输入关键词**: 在搜索框中输入关键词（如：日本料理）
2. **设置数量**: 选择要搜索的笔记数量（1-100）
3. **高级选项**（可选）:
   - 排序方式：综合排序、最新、最多点赞等
   - 笔记类型：不限、视频笔记、普通笔记
   - 时间范围：不限、一天内、一周内、半年内
   - 笔记范围：不限、已看过、未看过、已关注
4. **开始搜索**: 点击"开始搜索"按钮

### 步骤2: 查看搜索结果

搜索完成后，会在表格中显示找到的笔记：
- **基本信息**: 标题、作者、类型
- **互动数据**: 点赞数、评论数、收藏数
- **链接**: 可直接访问原始笔记
- **操作**: 解析按钮

### 步骤3: 解析详细信息

1. **解析所有**: 点击"解析所有笔记"按钮，批量获取详细信息
2. **查看进度**: 实时显示解析进度和状态
3. **查看详情**: 解析完成后，点击"查看详情"查看具体内容

### 步骤4: 查看笔记详情

详情页面包含：
- **基本信息**: 标题、作者、类型、互动数据
- **内容描述**: 笔记的文字内容
- **图片展示**: 所有图片的缩略图（点击查看大图）
- **视频播放**: 视频笔记的播放器
- **评论列表**: 显示评论内容、用户、点赞数等

## 🔧 技术架构

### 后端 (Flask)

- **web_app.py**: Flask主应用，提供API接口
- **APIs设计**:
  - `/api/search`: 搜索笔记
  - `/api/search/status/<task_id>`: 查询搜索状态
  - `/api/parse`: 解析笔记详情
  - `/api/parse/status/<task_id>`: 查询解析状态
  - `/api/note_detail`: 获取单个笔记详情
  - `/api/system_status`: 系统状态检查

### 前端 (HTML/CSS/JavaScript)

- **templates/index.html**: 主页面模板
- **static/css/style.css**: 样式文件
- **static/js/app.js**: JavaScript应用逻辑
- **Bootstrap 5**: UI框架
- **Font Awesome**: 图标库

### 数据流程

```
用户输入关键词 → 后端搜索API → 返回笔记列表 → 
前端表格展示 → 用户点击解析 → 后端解析API → 
获取详细信息 → 前端详情展示
```

## 📁 文件结构

```
├── web_app.py                 # Flask主应用
├── start_web.py               # 启动脚本
├── requirements_web.txt       # Web依赖
├── templates/
│   └── index.html            # 主页面模板
├── static/
│   ├── css/
│   │   └── style.css         # 样式文件
│   └── js/
│       └── app.js            # 前端逻辑
├── search_results/           # 搜索结果JSON文件
├── parse_results_*/          # 解析结果目录
└── WEB_README.md            # 本说明文件
```

## 🎨 界面特性

- **响应式设计**: 支持桌面和移动设备
- **实时状态**: 显示搜索和解析的实时进度
- **优雅界面**: 使用Bootstrap 5现代化设计
- **交互友好**: 清晰的操作流程和状态提示
- **数据可视化**: 直观展示笔记的所有信息

## 🔍 API接口说明

### 搜索相关

```javascript
// 搜索笔记
POST /api/search
{
  "query": "关键词",
  "require_num": 20,
  "sort_type": 0,
  "note_type": 0
}

// 查询搜索状态
GET /api/search/status/{task_id}
```

### 解析相关

```javascript
// 解析笔记
POST /api/parse
{
  "json_file_path": "search_results/xxx.json",
  "include_comments": true,
  "download_media": false
}

// 查询解析状态
GET /api/parse/status/{task_id}
```

### 详情查看

```javascript
// 获取笔记详情
GET /api/note_detail?note_id=xxx&output_dir=xxx
```

## ⚠️ 注意事项

1. **Cookie有效性**: Cookie有时效性，失效后需要重新获取
2. **请求频率**: 避免过高频率请求，防止被限流
3. **数据合规**: 仅用于学习和研究，请遵守相关法律法规
4. **浏览器兼容**: 推荐使用Chrome、Firefox等现代浏览器
5. **网络连接**: 确保网络连接稳定，避免请求中断

## 🛠️ 故障排除

### 常见问题

1. **Cookie无效**
   - 重新获取并更新.env文件中的Cookie
   
2. **搜索无结果**
   - 检查关键词是否正确
   - 确认Cookie是否有效
   
3. **解析失败**
   - 检查网络连接
   - 降低并发解析数量
   
4. **页面无法访问**
   - 确认Flask应用是否正常启动
   - 检查端口5000是否被占用

### 日志查看

应用运行时会在控制台输出详细日志，包括：
- 搜索进度和结果
- 解析进度和状态
- 错误信息和异常

## 🚀 扩展开发

可以基于现有架构扩展更多功能：

1. **用户系统**: 添加用户注册登录
2. **数据分析**: 集成图表展示功能
3. **批量操作**: 支持批量搜索多个关键词
4. **定时任务**: 添加定时爬取功能
5. **数据导出**: 支持Excel、CSV等更多格式

## 📞 支持

如有问题，请：
1. 查看控制台日志
2. 检查网络连接和Cookie配置
3. 参考本文档的故障排除部分