# /// script
# dependencies = [
#     "duckdb",
#     "requests",
#     "python-dotenv",
# ]
# ///

import os
import re
import json
import requests
import duckdb
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load local .env
load_dotenv('/Users/ben/Downloads/blank-s9/.env')

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DB_NAME = 'livestream.db'

def get_db():
    return duckdb.connect(database=DB_NAME)

def needs_translation(text):
    if not text:
        return False
    # If contains Chinese characters, skip
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        return False
    # If no alphabetic letters (English, Spanish, etc.), skip
    if not re.search(r'[a-zA-Z]', text):
        return False
    return True

def translate_batch(batch, thread_idx):
    if not batch:
        return {}
    
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    system_prompt = (
        "You are an expert translation assistant. Translate the following list of user comments from a live stream "
        "into natural Chinese. Return a JSON object with a single key 'translations' mapping to a list of "
        "translated strings in the exact same order as the input. Output ONLY the JSON object, no markdown wrappers."
    )
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}
        ],
        "response_format": {"type": "json_object"},
        "stream": False
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            if response.status_code == 200:
                res_json = response.json()
                content = res_json['choices'][0]['message']['content'].strip()
                data = json.loads(content)
                
                translations = []
                if isinstance(data, dict) and 'translations' in data:
                    translations = data['translations']
                elif isinstance(data, list):
                    translations = data
                elif isinstance(data, dict):
                    for val in data.values():
                        if isinstance(val, list):
                            translations = val
                            break
                
                if len(translations) == len(batch):
                    return {orig: trans for orig, trans in zip(batch, translations)}
                else:
                    print(f"[Thread {thread_idx}] Attempt {attempt+1}: Length mismatch ({len(translations)} vs {len(batch)}). Retrying...")
            else:
                print(f"[Thread {thread_idx}] Attempt {attempt+1}: HTTP {response.status_code}. Retrying...")
        except Exception as e:
            print(f"[Thread {thread_idx}] Attempt {attempt+1} failed: {e}")
            
    return {orig: orig for orig in batch}

def main():
    print("Connecting to database...")
    db = get_db()
    
    # Generate comments_report.html using the persistent '翻译内容' column
    print("Generating HTML report...")
    query = """
    SELECT 
        用户ID, 
        strftime(发言时间, '%Y-%m-%d %H:%M:%S') AS datetime, 
        发言内容 AS original, 
        翻译内容 AS translated
    FROM comments
    ORDER BY 用户ID, 发言时间;
    """
    
    rows = db.execute(query).fetchall()
    db.close()
    
    print(f"Total rows fetched: {len(rows)}")
    
    # Group comments by User ID
    user_comments = {}
    for row in rows:
        user_id, time_str, original, translated = row
        if user_id not in user_comments:
            user_comments[user_id] = []
        user_comments[user_id].append({
            "t": time_str,
            "o": original,
            "tr": translated if translated else original # Fallback if null
        })
        
    print(f"Grouped comments by {len(user_comments)} users.")
    
    # Write output to HTML template
    write_html_report(user_comments)

def write_html_report(user_comments):
    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户直播发言记录及翻译报告</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    <style>
        :root {
            --bg-dark: #0b0c10;
            --panel-bg: rgba(22, 24, 35, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.2);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Outfit', 'Noto Sans SC', sans-serif;
            padding: 24px;
            min-height: 100vh;
            background-image: radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.1) 0px, transparent 50%),
                              radial-gradient(at 100% 100%, rgba(124, 58, 237, 0.06) 0px, transparent 50%);
        }
        .container {
            width: 100%;
            max-width: 100%;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            backdrop-filter: blur(8px);
        }
        h1 { font-size: 20px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
        .controls {
            display: flex;
            gap: 16px;
            align-items: center;
        }
        .search-box {
            position: relative;
            width: 320px;
        }
        .search-box i {
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
        }
        .search-box input {
            width: 100%;
            padding: 10px 12px 10px 36px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: #fff;
            outline: none;
            font-size: 13px;
            transition: all 0.2s ease-in-out;
        }
        .search-box input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }
        .pagination-container {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text-muted);
        }
        .btn-page {
            padding: 6px 12px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            color: #fff;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease-in-out;
        }
        .btn-page:hover:not(:disabled) {
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 8px var(--primary-glow);
        }
        .btn-page:disabled { opacity: 0.3; cursor: not-allowed; }
        
        /* Bottom Pagination panel */
        .footer-controls {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 16px 20px;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            backdrop-filter: blur(8px);
            margin-top: 10px;
        }
        
        /* Users stream container */
        .users-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            width: 100%;
        }
        @media (max-width: 950px) {
            .users-list {
                grid-template-columns: 1fr;
            }
        }
        .user-block {
            border-radius: 12px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            backdrop-filter: blur(8px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out, border-color 0.2s ease-in-out;
        }
        .user-block:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(99, 102, 241, 0.15);
            border-color: rgba(99, 102, 241, 0.3);
        }
        .user-header {
            padding: 14px 20px;
            background: rgba(0, 0, 0, 0.2);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .user-id { font-size: 15px; font-weight: 600; color: #fff; }
        .comment-count { font-size: 11px; background: rgba(99, 102, 241, 0.2); color: var(--primary-light); padding: 2px 8px; border-radius: 20px; border: 1px solid rgba(99, 102, 241, 0.3); }
        
        .comments-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .comments-table th {
            text-align: left;
            padding: 10px 20px;
            background: rgba(0, 0, 0, 0.1);
            color: var(--text-muted);
            font-weight: 500;
            border-bottom: 1px solid var(--border-color);
        }
        .comments-table td {
            padding: 10px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            vertical-align: top;
        }
        .comments-table tr:last-child td { border-bottom: none; }
        .time-col { width: 180px; color: var(--text-muted); font-size: 12px; }
        .orig-col { width: 40%; color: var(--text-muted); }
        .trans-col { width: 40%; color: #fff; font-weight: 400; }
        
        .empty-state {
            padding: 60px;
            text-align: center;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Top controls header -->
        <header>
            <h1><i class="fas fa-comments"></i> 用户发言记录及中文翻译</h1>
            <div class="controls">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="user-search" placeholder="搜索用户ID或发言关键词...">
                </div>
                <div class="pagination-container">
                    <button class="btn-page btn-prev" disabled><i class="fas fa-chevron-left"></i> 上一页</button>
                    <span class="page-num">第 1 / 1 页</span>
                    <button class="btn-page btn-next" disabled>下一页 <i class="fas fa-chevron-right"></i></button>
                </div>
            </div>
        </header>

        <!-- Main list container -->
        <div class="users-list" id="users-list-container">
            <!-- Dynamic blocks load here -->
        </div>
        
        <!-- Bottom pagination footer -->
        <div class="footer-controls">
            <div class="pagination-container">
                <button class="btn-page btn-prev" id="btn-prev-bottom" disabled><i class="fas fa-chevron-left"></i> 上一页</button>
                <span class="page-num" id="page-num-bottom">第 1 / 1 页</span>
                <button class="btn-page btn-next" id="btn-next-bottom" disabled>下一页 <i class="fas fa-chevron-right"></i></button>
            </div>
        </div>
    </div>

    <!-- Embedded Data Injected by Python -->
    <script>
        const commentData = %DATA_JSON%;
    </script>

    <script>
        let currentPage = 1;
        const pageSize = 50; // Render 50 users per page
        let filteredUserIds = Object.keys(commentData);

        const elements = {
            container: document.getElementById('users-list-container'),
            search: document.getElementById('user-search'),
            
            // Top and Bottom pagination controls
            btnsPrev: document.querySelectorAll('.btn-prev'),
            btnsNext: document.querySelectorAll('.btn-next'),
            pagesNum: document.querySelectorAll('.page-num')
        };

        // Generate a deterministic dark pastel background color from User ID string
        function getUserBgColor(userId) {
            let hash = 0;
            for (let i = 0; i < userId.length; i++) {
                hash = userId.charCodeAt(i) + ((hash << 5) - hash);
            }
            const h = Math.abs(hash % 360);
            return `hsla(${h}, 35%, 15%, 0.4)`; // Dark themed pastel overlay
        }

        function renderPage() {
            elements.container.innerHTML = '';
            
            if (filteredUserIds.length === 0) {
                elements.container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-search" style="font-size: 32px; margin-bottom: 12px; display: block; opacity: 0.5;"></i>
                        <p>未找到匹配的用户或发言记录</p>
                    </div>
                `;
                elements.btnsPrev.forEach(btn => btn.disabled = true);
                elements.btnsNext.forEach(btn => btn.disabled = true);
                elements.pagesNum.forEach(el => el.textContent = '第 0 / 0 页');
                return;
            }

            const totalPages = Math.ceil(filteredUserIds.length / pageSize);
            if (currentPage > totalPages) currentPage = totalPages;
            if (currentPage < 1) currentPage = 1;

            const startIdx = (currentPage - 1) * pageSize;
            const endIdx = Math.min(startIdx + pageSize, filteredUserIds.length);
            const pageUserIds = filteredUserIds.slice(startIdx, endIdx);

            pageUserIds.forEach(userId => {
                const comments = commentData[userId];
                // Explicitly sort comments from early to late
                comments.sort((a, b) => a.t.localeCompare(b.t));
                const bgColor = getUserBgColor(userId);
                
                const block = document.createElement('div');
                block.className = 'user-block';
                block.style.backgroundColor = bgColor;
                
                let blockHtml = `
                    <div class="user-header">
                        <span class="user-id"><i class="fas fa-user-circle"></i> ${userId}</span>
                        <span class="comment-count">${comments.length} 条发言</span>
                    </div>
                    <table class="comments-table">
                        <thead>
                            <tr>
                                <th class="time-col">时间</th>
                                <th class="orig-col">原文</th>
                                <th class="trans-col">中文翻译</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                comments.forEach(c => {
                    blockHtml += `
                        <tr>
                            <td class="time-col">${c.t}</td>
                            <td class="orig-col">${escapeHtml(c.o)}</td>
                            <td class="trans-col">${escapeHtml(c.tr)}</td>
                        </tr>
                    `;
                });
                
                blockHtml += `
                        </tbody>
                    </table>
                `;
                
                block.innerHTML = blockHtml;
                elements.container.appendChild(block);
            });

            // Update pagination buttons status
            const paginationText = `第 ${currentPage} / ${totalPages} 页 (共 ${filteredUserIds.length} 个用户)`;
            elements.pagesNum.forEach(el => el.textContent = paginationText);
            
            elements.btnsPrev.forEach(btn => btn.disabled = currentPage === 1);
            elements.btnsNext.forEach(btn => btn.disabled = currentPage === totalPages);
        }

        function handleSearch() {
            const query = elements.search.value.trim().toLowerCase();
            
            if (!query) {
                filteredUserIds = Object.keys(commentData);
            } else {
                filteredUserIds = Object.keys(commentData).filter(userId => {
                    if (userId.toLowerCase().includes(query)) return true;
                    return commentData[userId].some(c => 
                        c.o.toLowerCase().includes(query) || 
                        c.tr.toLowerCase().includes(query)
                    );
                });
            }
            
            currentPage = 1;
            renderPage();
        }

        function escapeHtml(text) {
            if (!text) return '';
            return text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Event listeners
        elements.search.addEventListener('input', handleSearch);
        
        elements.btnsPrev.forEach(btn => {
            btn.addEventListener('click', () => {
                if (currentPage > 1) {
                    currentPage--;
                    renderPage();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });
        
        elements.btnsNext.forEach(btn => {
            btn.addEventListener('click', () => {
                const totalPages = Math.ceil(filteredUserIds.length / pageSize);
                if (currentPage < totalPages) {
                    currentPage++;
                    renderPage();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });

        // Initial Load
        renderPage();
    </script>
</body>
</html>
"""
    json_data = json.dumps(user_comments, ensure_ascii=False)
    output_html = html_template.replace("%DATA_JSON%", json_data)
    
    output_path = '/Users/ben/Downloads/blank-s9/publish/comments_report.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_html)
        
    print(f"HTML report successfully written to: {output_path}")

if __name__ == '__main__':
    main()
