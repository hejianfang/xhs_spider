// 小红书数据爬取工具 - 前端应用逻辑

class XHSSpiderApp {
    constructor() {
        this.currentSearchTaskId = null;
        this.currentParseTaskId = null;
        this.searchResults = [];
        this.parseResults = null;
        this.noteDetailsCache = new Map(); // 笔记详情缓存
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.checkSystemStatus();
        
        // 定期检查系统状态
        setInterval(() => {
            this.checkSystemStatus();
        }, 30000); // 30秒检查一次
    }
    
    bindEvents() {
        // 搜索表单提交
        document.getElementById('searchForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSearch();
        });
        
        // 解析所有笔记按钮
        document.getElementById('parseAllBtn').addEventListener('click', () => {
            this.handleParseAll();
        });
        
        // 导出数据按钮
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.handleExport();
        });
    }
    
    async checkSystemStatus() {
        try {
            const response = await fetch('/api/system_status');
            const data = await response.json();
            
            if (data.success) {
                const statusElement = document.getElementById('systemStatus');
                const status = data.status;
                
                if (status.cookies_available) {
                    statusElement.innerHTML = '<i class="fa fa-circle text-success me-1"></i>系统正常';
                } else {
                    statusElement.innerHTML = '<i class="fa fa-circle text-warning me-1"></i>Cookie未配置';
                }
            }
        } catch (error) {
            console.error('检查系统状态失败:', error);
            document.getElementById('systemStatus').innerHTML = '<i class="fa fa-circle text-danger me-1"></i>系统异常';
        }
    }
    
    async handleSearch() {
        const query = document.getElementById('query').value.trim();
        const requireNum = parseInt(document.getElementById('requireNum').value);
        
        if (!query) {
            this.showAlert('请输入搜索关键词', 'warning');
            return;
        }
        
        if (requireNum <= 0 || requireNum > 100) {
            this.showAlert('搜索数量必须在1-100之间', 'warning');
            return;
        }
        
        // 禁用搜索按钮
        const searchBtn = document.getElementById('searchBtn');
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="fa fa-spinner fa-spin me-2"></i>搜索中...';
        
        // 显示搜索状态
        this.showSearchStatus('正在搜索笔记...', 'info');
        
        // 构建请求数据
        const requestData = {
            query: query,
            require_num: requireNum,
            sort_type: document.getElementById('sortType').value,
            note_type: document.getElementById('noteType').value,
            note_time: document.getElementById('noteTime').value,
            note_range: document.getElementById('noteRange').value,
            pos_distance: 0
        };
        
        try {
            // 发起搜索请求
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentSearchTaskId = data.task_id;
                this.pollSearchStatus();
            } else {
                this.showSearchStatus(data.message, 'danger');
                this.resetSearchButton();
            }
        } catch (error) {
            console.error('搜索请求失败:', error);
            this.showSearchStatus('搜索请求失败', 'danger');
            this.resetSearchButton();
        }
    }
    
    async pollSearchStatus() {
        if (!this.currentSearchTaskId) return;
        
        try {
            const response = await fetch(`/api/search/status/${this.currentSearchTaskId}`);
            const data = await response.json();
            
            if (data.success) {
                const task = data.task;
                
                if (task.status === 'running') {
                    this.showSearchStatus(task.message, 'info');
                    setTimeout(() => this.pollSearchStatus(), 2000); // 2秒后再次检查
                } else if (task.status === 'completed') {
                    this.showSearchStatus(task.message, 'success');
                    this.searchResults = task.result.notes;
                    this.displaySearchResults();
                    this.resetSearchButton();
                } else if (task.status === 'failed') {
                    this.showSearchStatus(task.message, 'danger');
                    this.resetSearchButton();
                }
            }
        } catch (error) {
            console.error('查询搜索状态失败:', error);
            this.showSearchStatus('查询状态失败', 'danger');
            this.resetSearchButton();
        }
    }
    
    displaySearchResults() {
        const resultsSection = document.getElementById('resultsSection');
        const tableBody = document.getElementById('resultsTableBody');
        
        // 清空表格
        tableBody.innerHTML = '';
        
        if (this.searchResults.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="10" class="text-center">暂无搜索结果</td></tr>';
            resultsSection.style.display = 'block';
            return;
        }
        
        // 填充表格数据
        this.searchResults.forEach((note, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${index + 1}</td>
                <td>
                    <div class="text-truncate" style="max-width: 150px;" title="${note.title}">
                        ${note.title || '无标题'}
                    </div>
                </td>
                <td>
                    <div class="text-truncate" style="max-width: 100px;" title="${note.user_nickname}">
                        ${note.user_nickname || '未知'}
                    </div>
                </td>
                <td>
                    <span class="badge ${note.note_type === 'video' ? 'note-type-video' : 'note-type-image'} note-type-badge">
                        ${note.note_type === 'video' ? '视频' : '图集'}
                    </span>
                </td>
                <td>
                    <i class="fa fa-heart text-danger me-1"></i>
                    ${this.formatNumber(note.interact_info.liked_count)}
                </td>
                <td>
                    <i class="fa fa-comment text-primary me-1"></i>
                    ${this.formatNumber(note.interact_info.comment_count)}
                </td>
                <td>
                    <i class="fa fa-star text-warning me-1"></i>
                    ${this.formatNumber(note.interact_info.collected_count)}
                </td>
                <td>${this.formatDate(note.search_time)}</td>
                <td>
                    <a href="${note.note_url}" target="_blank" class="note-link">
                        <i class="fa fa-external-link me-1"></i>查看原文
                    </a>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="app.parseNote('${note.note_id}', '${note.note_url}')">
                        <i class="fa fa-cog me-1"></i>解析
                    </button>
                </td>
            `;
            tableBody.appendChild(row);
        });
        
        // 显示结果区域
        resultsSection.style.display = 'block';
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    async parseNote(noteId, noteUrl) {
        try {
            // 显示加载状态
            this.showAlert('正在解析笔记详情...', 'info');
            
            // 获取笔记完整信息
            const success = await this.getSingleNoteDetail(noteUrl);
            if (success) {
                this.showAlert('笔记解析成功', 'success');
            } else {
                this.showAlert('笔记解析失败', 'error');
            }
        } catch (error) {
            console.error('解析笔记失败:', error);
            this.showAlert('解析笔记失败', 'error');
        }
    }
    
    async getSingleNoteDetail(noteUrl) {
        try {
            // 先检查缓存
            if (this.noteDetailsCache.has(noteUrl)) {
                console.log('从缓存中获取笔记详情:', noteUrl);
                const cachedDetail = this.noteDetailsCache.get(noteUrl);
                this.showNoteDetailDirect(cachedDetail);
                return true;
            }
            
            console.log('从服务器获取笔记详情:', noteUrl);
            
            // 显示全局loading
            this.showGlobalLoading('正在连接服务器...');
            
            // 更新loading文本
            setTimeout(() => {
                this.updateGlobalLoadingText('正在解析笔记内容...');
            }, 500);
            
            setTimeout(() => {
                this.updateGlobalLoadingText('正在获取评论数据...');
            }, 1500);
            
            // 调用后端API获取单个笔记详情
            const response = await fetch('/api/single_note_detail', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    note_url: noteUrl,
                    include_comments: true
                })
            });
            
            this.updateGlobalLoadingText('正在处理数据...');
            const data = await response.json();
            
            if (data.success) {
                // 将结果存入缓存
                this.noteDetailsCache.set(noteUrl, data.note_detail);
                
                // 隐藏全局loading
                this.hideGlobalLoading();
                
                // 直接显示详情模态框
                this.showNoteDetailDirect(data.note_detail);
                return true;
            } else {
                console.error('获取笔记详情失败:', data.message);
                // 隐藏loading并显示错误
                this.hideGlobalLoading();
                this.showAlert('获取笔记详情失败: ' + data.message, 'error');
                return false;
            }
        } catch (error) {
            console.error('请求笔记详情失败:', error);
            // 隐藏loading并显示错误
            this.hideGlobalLoading();
            this.showAlert('请求笔记详情失败: ' + error.message, 'error');
            return false;
        }
    }
    
    async handleParseAll() {
        if (!this.searchResults || this.searchResults.length === 0) {
            this.showAlert('请先搜索笔记', 'warning');
            return;
        }
        
        if (!this.currentSearchTaskId) {
            this.showAlert('无法获取搜索结果文件', 'error');
            return;
        }
        
        // 获取搜索任务的JSON文件路径
        try {
            const response = await fetch(`/api/search/status/${this.currentSearchTaskId}`);
            const data = await response.json();
            
            if (!data.success || !data.task.result) {
                this.showAlert('无法获取搜索结果文件路径', 'error');
                return;
            }
            
            const jsonFilePath = data.task.result.json_file;
            if (!jsonFilePath) {
                this.showAlert('搜索结果文件路径无效', 'error');
                return;
            }
            
            // 开始解析任务
            await this.startParseTask(jsonFilePath);
            
        } catch (error) {
            console.error('获取搜索结果失败:', error);
            this.showAlert('获取搜索结果失败', 'error');
        }
    }
    
    async startParseTask(jsonFilePath) {
        try {
            // 发起解析请求
            const response = await fetch('/api/parse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    json_file_path: jsonFilePath,
                    include_comments: true,
                    download_media: false, // Web界面中不下载媒体文件
                    save_format: 'json'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentParseTaskId = data.task_id;
                
                // 显示解析进度模态框
                const modal = new bootstrap.Modal(document.getElementById('parseProgressModal'));
                modal.show();
                
                // 开始轮询解析状态
                this.pollParseStatus(modal);
            } else {
                this.showAlert(data.message, 'error');
            }
            
        } catch (error) {
            console.error('启动解析任务失败:', error);
            this.showAlert('启动解析任务失败', 'error');
        }
    }
    
    async pollParseStatus(modal) {
        if (!this.currentParseTaskId) return;
        
        try {
            const response = await fetch(`/api/parse/status/${this.currentParseTaskId}`);
            const data = await response.json();
            
            if (data.success) {
                const task = data.task;
                
                if (task.status === 'running') {
                    this.updateParseProgress(task.progress || 0, task.message);
                    setTimeout(() => this.pollParseStatus(modal), 2000); // 2秒后再次检查
                } else if (task.status === 'completed') {
                    this.updateParseProgress(100, task.message);
                    this.parseResults = task.result;
                    
                    setTimeout(() => {
                        modal.hide();
                        this.showAlert('所有笔记解析完成', 'success');
                        this.updateResultsTable(); // 更新表格显示解析按钮
                    }, 1000);
                } else if (task.status === 'failed') {
                    modal.hide();
                    this.showAlert(task.message, 'error');
                }
            }
        } catch (error) {
            console.error('查询解析状态失败:', error);
            modal.hide();
            this.showAlert('查询解析状态失败', 'error');
        }
    }
    
    updateResultsTable() {
        // 如果解析完成，更新表格中的解析按钮为查看详情按钮
        if (this.parseResults && this.parseResults.output_directory) {
            const tableBody = document.getElementById('resultsTableBody');
            const rows = tableBody.querySelectorAll('tr');
            
            rows.forEach((row, index) => {
                if (index < this.searchResults.length) {
                    const note = this.searchResults[index];
                    const actionCell = row.querySelector('td:last-child');
                    actionCell.innerHTML = `
                        <button class="btn btn-sm btn-success" onclick="app.showNoteDetail('${note.note_id}', '${this.parseResults.output_directory}')">
                            <i class="fa fa-eye me-1"></i>查看详情
                        </button>
                    `;
                }
            });
        }
    }
    
    updateParseProgress(progress, message) {
        const progressBar = document.getElementById('parseProgressBar');
        const progressText = document.getElementById('parseProgressText');
        
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${Math.round(progress)}%`;
        progressText.textContent = message;
    }
    
    handleExport() {
        if (!this.searchResults || this.searchResults.length === 0) {
            this.showAlert('没有可导出的数据', 'warning');
            return;
        }
        
        // 导出为JSON文件
        const dataStr = JSON.stringify(this.searchResults, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `xhs_search_results_${new Date().getTime()}.json`;
        link.click();
        
        this.showAlert('数据导出成功', 'success');
    }
    
    showSearchStatus(message, type) {
        const statusRow = document.getElementById('searchStatusRow');
        const statusAlert = document.getElementById('searchStatus');
        const statusText = document.getElementById('searchStatusText');
        const spinner = document.getElementById('searchSpinner');
        
        statusAlert.className = `alert alert-${type}`;
        statusText.textContent = message;
        
        if (type === 'info') {
            spinner.style.display = 'block';
        } else {
            spinner.style.display = 'none';
        }
        
        statusRow.style.display = 'block';
        
        // 如果是成功或失败消息，3秒后自动隐藏
        if (type === 'success' || type === 'danger') {
            setTimeout(() => {
                statusRow.style.display = 'none';
            }, 3000);
        }
    }
    
    resetSearchButton() {
        const searchBtn = document.getElementById('searchBtn');
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="fa fa-search me-2"></i>开始搜索';
    }
    
    showAlert(message, type) {
        // 创建临时提示框
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // 插入到页面顶部
        document.querySelector('.container').insertBefore(alertDiv, document.querySelector('.container').firstChild);
        
        // 3秒后自动移除
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 3000);
    }
    
    formatNumber(num) {
        if (!num) return '0';
        if (num >= 10000) {
            return (num / 10000).toFixed(1) + 'w';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'k';
        }
        return num.toString();
    }
    
    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    async showNoteDetail(noteId, outputDir) {
        const modal = new bootstrap.Modal(document.getElementById('noteDetailModal'));
        const content = document.getElementById('noteDetailContent');
        
        // 显示加载状态
        content.innerHTML = `
            <div class="text-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">加载中...</span>
                </div>
                <p class="mt-2">正在加载笔记详情...</p>
            </div>
        `;
        
        modal.show();
        
        try {
            const response = await fetch(`/api/note_detail?note_id=${noteId}&output_dir=${encodeURIComponent(outputDir)}`);
            const data = await response.json();
            
            if (data.success) {
                this.renderNoteDetail(data.note_detail);
            } else {
                content.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fa fa-exclamation-triangle me-2"></i>
                        加载失败: ${data.message}
                    </div>
                `;
            }
        } catch (error) {
            console.error('加载笔记详情失败:', error);
            content.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fa fa-exclamation-triangle me-2"></i>
                    加载失败: 网络错误
                </div>
            `;
        }
    }
    
    showNoteDetailDirect(noteDetail) {
        const modal = new bootstrap.Modal(document.getElementById('noteDetailModal'));
        const content = document.getElementById('noteDetailContent');
        
        // 渲染仿小红书界面
        this.renderXhsStyleDetail(noteDetail);
        modal.show();
    }
    
    renderXhsStyleDetail(noteDetail) {
        const content = document.getElementById('noteDetailContent');
        
        // 构建仿小红书风格的详情页面
        const html = `
            <div class="xhs-detail-container">
                <!-- 左侧媒体区域 -->
                <div class="xhs-media-section">
                    <div class="xhs-media-container" id="xhsMediaContainer">
                        ${this.renderMediaContent(noteDetail)}
                    </div>
                    ${this.renderMediaNavigator(noteDetail)}
                </div>
                
                <!-- 右侧信息区域 -->
                <div class="xhs-info-section">
                    <!-- 用户信息 -->
                    <div class="xhs-user-info">
                        <img src="${noteDetail.avatar ? `/api/proxy_image?url=${encodeURIComponent(noteDetail.avatar)}` : '/static/images/default-avatar.png'}" 
                             alt="用户头像" class="xhs-user-avatar" 
                             onerror="this.src='/static/images/default-avatar.png'">
                        <div class="xhs-user-details">
                            <h6>${noteDetail.nickname || '未知用户'}</h6>
                            <div class="text-muted">创作者</div>
                        </div>
                    </div>
                    
                    <!-- 内容区域 -->
                    <div class="xhs-content-area">
                        <!-- 笔记内容 -->
                        <div class="xhs-note-content">
                            <div class="xhs-note-title">${noteDetail.title || '无标题'}</div>
                            <div class="xhs-note-desc">${noteDetail.desc || '暂无描述'}</div>
                        </div>
                        
                        <!-- 互动数据 -->
                        <div class="xhs-interact-stats">
                            <div class="xhs-stat-item">
                                <i class="fa fa-heart xhs-stat-icon like"></i>
                                <span>${this.formatNumber(noteDetail.liked_count || 0)}</span>
                            </div>
                            <div class="xhs-stat-item">
                                <i class="fa fa-star xhs-stat-icon collect"></i>
                                <span>${this.formatNumber(noteDetail.collected_count || 0)}</span>
                            </div>
                            <div class="xhs-stat-item">
                                <i class="fa fa-comment xhs-stat-icon comment"></i>
                                <span>${this.formatNumber(noteDetail.comment_count || 0)}</span>
                            </div>
                        </div>
                        
                        <!-- 评论区域 -->
                        <div class="xhs-comments-section">
                            <div class="xhs-comments-header">
                                <strong>评论 ${noteDetail.comments ? noteDetail.comments.length : 0}</strong>
                            </div>
                            <div class="xhs-comments-list">
                                ${this.renderCommentsList(noteDetail.comments || [])}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        content.innerHTML = html;
        
        // 初始化媒体切换功能
        this.initMediaSwitcher(noteDetail);
    }
    
    renderMediaContent(noteDetail) {
        console.log('渲染媒体内容，笔记数据:', noteDetail);
        
        // 尝试多种视频URL格式
        const videoUrl = noteDetail.video_addr || noteDetail.video_url || 
                        (noteDetail.video && noteDetail.video.url) ||
                        (noteDetail.video_info && noteDetail.video_info.url);
        
        if (videoUrl) {
            console.log('找到视频URL:', videoUrl);
            return `
                <video class="xhs-main-video" controls autoplay muted>
                    <source src="${videoUrl}" type="video/mp4">
                    您的浏览器不支持视频播放。
                </video>
            `;
        }
        
        // 获取图片列表
        const imageList = this.getImageList(noteDetail);
        console.log('获取到的图片列表:', imageList);
        
        if (imageList && imageList.length > 0) {
            const firstImage = imageList[0];
            const proxiedImageUrl = `/api/proxy_image?url=${encodeURIComponent(firstImage)}`;
            console.log('显示第一张图片:', firstImage);
            console.log('代理图片URL:', proxiedImageUrl);
            return `
                <img src="${proxiedImageUrl}" 
                     alt="笔记图片" 
                     class="xhs-main-image" 
                     id="xhsMainImage"
                     data-original-url="${firstImage}"
                     onerror="console.error('图片加载失败:', this.src); this.style.display='none'; this.nextElementSibling.style.display='block';">
                <div class="xhs-loading" style="display: none;">
                    <i class="fa fa-image" style="font-size: 3rem; color: #ccc;"></i>
                    <p class="mt-2">图片加载失败</p>
                </div>
            `;
        }
        
        // 尝试封面图片
        const coverUrl = noteDetail.cover_url || 
                        (noteDetail.cover && noteDetail.cover.url) ||
                        noteDetail.avatar;
        
        if (coverUrl) {
            const proxiedCoverUrl = `/api/proxy_image?url=${encodeURIComponent(coverUrl)}`;
            console.log('使用封面图片:', coverUrl);
            console.log('代理封面URL:', proxiedCoverUrl);
            return `
                <img src="${proxiedCoverUrl}" 
                     alt="笔记封面" 
                     class="xhs-main-image"
                     data-original-url="${coverUrl}"
                     onerror="console.error('封面图片加载失败:', this.src); this.style.display='none'; this.nextElementSibling.style.display='block';">
                <div class="xhs-loading" style="display: none;">
                    <i class="fa fa-image" style="font-size: 3rem; color: #ccc;"></i>
                    <p class="mt-2">图片加载失败</p>
                </div>
            `;
        }
        
        // 默认占位符
        console.log('没有找到任何媒体内容');
        return `
            <div class="xhs-loading">
                <i class="fa fa-image" style="font-size: 3rem; color: #ccc;"></i>
                <p class="mt-2">暂无媒体内容</p>
            </div>
        `;
    }
    
    renderMediaNavigator(noteDetail) {
        // 获取图片列表
        let imageList = this.getImageList(noteDetail);
        
        if (!imageList || imageList.length <= 1) {
            return '';
        }
        
        return `
            <!-- 图片导航器 -->
            <div class="xhs-image-navigator" id="xhsImageNavigator">
                ${imageList.map((_, index) => `
                    <div class="xhs-nav-dot ${index === 0 ? 'active' : ''}" 
                         onclick="app.switchImage(${index})"></div>
                `).join('')}
            </div>
            
            <!-- 切换按钮 -->
            <button class="xhs-nav-btn prev" onclick="app.switchImage('prev')">
                <i class="fa fa-chevron-left"></i>
            </button>
            <button class="xhs-nav-btn next" onclick="app.switchImage('next')">
                <i class="fa fa-chevron-right"></i>
            </button>
        `;
    }
    
    // 提取图片列表的统一方法
    getImageList(noteDetail) {
        if (noteDetail.image_list && Array.isArray(noteDetail.image_list) && noteDetail.image_list.length > 0) {
            return noteDetail.image_list;
        } else if (noteDetail.images && Array.isArray(noteDetail.images) && noteDetail.images.length > 0) {
            return noteDetail.images.map(img => {
                if (typeof img === 'string') return img;
                return img.url || img.src || img.live_photo || img;
            }).filter(url => url);
        } else if (noteDetail.image_info && noteDetail.image_info.image_list) {
            return noteDetail.image_info.image_list.map(img => img.url || img);
        }
        return null;
    }
    
    renderCommentsList(comments) {
        if (!comments || comments.length === 0) {
            return `
                <div class="text-center p-4">
                    <i class="fa fa-comment-o" style="font-size: 2rem; color: #ccc;"></i>
                    <p class="mt-2 text-muted">暂无评论</p>
                </div>
            `;
        }
        
        console.log('渲染评论列表，评论数量:', comments.length);
        
        // 对评论进行分组：一级评论和回复
        let organizedComments;
        try {
            organizedComments = this.organizeComments(comments);
            console.log('评论分组成功，组数:', organizedComments.length);
        } catch (error) {
            console.error('评论分组失败，使用简单模式:', error);
            // 备用方案：每个评论都作为独立组
            organizedComments = comments.map(comment => ({
                comment: comment,
                replies: []
            }));
        }
        
        if (!organizedComments || organizedComments.length === 0) {
            console.warn('分组后评论为空，使用原始评论');
            organizedComments = comments.map(comment => ({
                comment: comment,
                replies: []
            }));
        }
        
        return organizedComments.map(commentGroup => {
            const mainComment = commentGroup.comment;
            const replies = commentGroup.replies;
            
            return `
                <div class="xhs-comment-group">
                    <!-- 一级评论 -->
                    <div class="xhs-comment-item xhs-main-comment">
                        <img src="${mainComment.avatar || '/static/images/default-avatar.png'}" 
                             alt="用户头像" class="xhs-comment-avatar"
                             onerror="this.src='/static/images/default-avatar.png'">
                        <div class="xhs-comment-content">
                            <div class="xhs-comment-user">${mainComment.nickname || '匿名用户'}</div>
                            <div class="xhs-comment-text">${mainComment.content || ''}</div>
                            <div class="xhs-comment-meta">
                                <div class="xhs-comment-like">
                                    <i class="fa fa-heart-o"></i>
                                    <span>${this.formatNumber(mainComment.like_count || 0)}</span>
                                </div>
                                <div class="xhs-comment-time">${this.formatDate(mainComment.upload_time)}</div>
                                ${mainComment.ip_location ? `<div class="xhs-comment-location">${mainComment.ip_location}</div>` : ''}
                                ${replies.length > 0 ? `<div class="xhs-replies-count">${replies.length}条回复</div>` : ''}
                            </div>
                        </div>
                    </div>
                    
                    <!-- 二级回复 -->
                    ${replies.length > 0 ? `
                        <div class="xhs-replies-container">
                            ${replies.map(reply => `
                                <div class="xhs-comment-item xhs-reply-comment">
                                    <img src="${reply.avatar || '/static/images/default-avatar.png'}" 
                                         alt="用户头像" class="xhs-comment-avatar xhs-reply-avatar"
                                         onerror="this.src='/static/images/default-avatar.png'">
                                    <div class="xhs-comment-content">
                                        <div class="xhs-comment-user">
                                            ${reply.nickname || '匿名用户'}
                                            ${reply.at_user_nickname ? `<span class="xhs-reply-to">回复 @${reply.at_user_nickname}</span>` : ''}
                                        </div>
                                        <div class="xhs-comment-text">${reply.content || ''}</div>
                                        <div class="xhs-comment-meta">
                                            <div class="xhs-comment-like">
                                                <i class="fa fa-heart-o"></i>
                                                <span>${this.formatNumber(reply.like_count || 0)}</span>
                                            </div>
                                            <div class="xhs-comment-time">${this.formatDate(reply.upload_time)}</div>
                                            ${reply.ip_location ? `<div class="xhs-comment-location">${reply.ip_location}</div>` : ''}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
    }
    
    // 组织评论数据，将回复归类到对应的一级评论下
    organizeComments(comments) {
        if (!comments || comments.length === 0) {
            return [];
        }
        
        console.log('开始组织评论，总数:', comments.length, comments);
        
        // 先尝试智能分组，这样更通用
        return this.smartGroupComments(comments);
    }
    
    // 智能分组评论（当没有明确层次关系时使用）
    smartGroupComments(comments) {
        const groups = [];
        let currentGroup = null;
        
        console.log('智能分组评论，评论数量:', comments.length);
        
        comments.forEach((comment, index) => {
            console.log(`处理评论 ${index}:`, comment.nickname, comment.content?.substring(0, 30));
            
            // 判断是否应该作为回复
            const shouldBeReply = this.shouldBeReply(comment, comments, index);
            console.log(`评论 ${index} 是否为回复:`, shouldBeReply);
            
            if (shouldBeReply && currentGroup && currentGroup.replies.length < 5) {
                // 限制每个组最多5个回复，避免过度分组
                currentGroup.replies.push(comment);
                console.log(`添加到回复列表，当前回复数:`, currentGroup.replies.length);
            } else {
                // 创建新的一级评论组
                currentGroup = {
                    comment: comment,
                    replies: []
                };
                groups.push(currentGroup);
                console.log(`创建新评论组，总组数:`, groups.length);
            }
        });
        
        console.log('分组完成，总组数:', groups.length);
        return groups;
    }
    
    // 判断评论是否应该作为回复
    shouldBeReply(comment, allComments, index) {
        // 如果明确有 at_user_nickname，通常是回复
        if (comment.at_user_nickname && comment.at_user_nickname !== comment.nickname) {
            console.log('发现@用户，判断为回复:', comment.at_user_nickname);
            return true;
        }
        
        // 如果评论内容以 "@用户名" 开头，通常是回复
        if (comment.content && comment.content.match(/^@[\u4e00-\u9fa5\w]+/)) {
            console.log('内容以@开头，判断为回复');
            return true;
        }
        
        // 如果是连续的短评论，可能是对话 (放宽条件)
        if (index > 0 && comment.content && comment.content.length < 30) {
            const prevComment = allComments[index - 1];
            if (prevComment && prevComment.content && prevComment.content.length < 50) {
                console.log('短评论对话，判断为回复');
                return true;
            }
        }
        
        return false;
    }
    
    initMediaSwitcher(noteDetail) {
        const imageList = this.getImageList(noteDetail);
        
        if (!imageList || imageList.length <= 1) {
            return;
        }
        
        this.currentImageIndex = 0;
        this.imageList = imageList;
        console.log('初始化图片切换器，图片数量:', imageList.length);
    }
    
    switchImage(direction) {
        if (!this.imageList || this.imageList.length <= 1) return;
        
        const totalImages = this.imageList.length;
        
        if (direction === 'prev') {
            this.currentImageIndex = (this.currentImageIndex - 1 + totalImages) % totalImages;
        } else if (direction === 'next') {
            this.currentImageIndex = (this.currentImageIndex + 1) % totalImages;
        } else if (typeof direction === 'number') {
            this.currentImageIndex = direction;
        }
        
        // 更新主图片
        const mainImage = document.getElementById('xhsMainImage');
        if (mainImage) {
            const originalUrl = this.imageList[this.currentImageIndex];
            const proxiedUrl = `/api/proxy_image?url=${encodeURIComponent(originalUrl)}`;
            mainImage.src = proxiedUrl;
            mainImage.setAttribute('data-original-url', originalUrl);
        }
        
        // 更新导航点
        const dots = document.querySelectorAll('.xhs-nav-dot');
        dots.forEach((dot, index) => {
            dot.classList.toggle('active', index === this.currentImageIndex);
        });
    }
    
    renderNoteDetail(noteDetail) {
        // 保留原有的详情渲染方法作为备用
        this.renderXhsStyleDetail(noteDetail);
    }

    // 显示全局loading
    showGlobalLoading(message = '正在加载...') {
        const overlay = document.getElementById('globalLoadingOverlay');
        const textElement = document.getElementById('globalLoadingText');
        
        if (textElement) {
            textElement.textContent = message;
        }
        
        if (overlay) {
            overlay.style.display = 'flex';
            // 添加淡入动画
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.style.transition = 'opacity 0.3s ease';
                overlay.style.opacity = '1';
            }, 10);
        }
    }

    // 隐藏全局loading
    hideGlobalLoading() {
        const overlay = document.getElementById('globalLoadingOverlay');
        
        if (overlay) {
            overlay.style.transition = 'opacity 0.3s ease';
            overlay.style.opacity = '0';
            
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 300);
        }
    }

    // 更新全局loading文本
    updateGlobalLoadingText(message) {
        const textElement = document.getElementById('globalLoadingText');
        if (textElement) {
            textElement.textContent = message;
        }
    }
}

// 初始化应用
const app = new XHSSpiderApp();