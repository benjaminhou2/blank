import os
import re
import json
import duckdb

DB_PATH = 'livestream.db'
OUTPUT_HTML_PATH = 'publish/spender_comments_report.html'

def get_db():
    return duckdb.connect(database=DB_PATH, read_only=True)

def is_symbols_and_numbers(text):
    if not text:
        return True
    # If the text has at least one Chinese character or English letter, it is NOT only symbols and numbers.
    if re.search(r'[a-zA-Z\u4e00-\u9fff]', text):
        return False
    return True

def generate_report():
    print("Connecting to database...")
    db = get_db()
    
    # Query: Get comments for users who have at least one record in gifts table.
    # We join with gifts metadata to get their first gift time, total USD, and follow status.
    # SQL query: Join comments with their tipping info, sorted by total tipping amount descending.
    # Grouping comments by user, keeping only those who tipped the room at least once.
    query = """
    WITH spender_info AS (
        SELECT 
            用户ID, 
            MIN(打赏行为的时间) AS first_gift_time,
            ROUND(SUM(打赏金额_USD), 2) AS total_gift_amount
        FROM gifts
        GROUP BY 用户ID
    ),
    follower_info AS (
        SELECT 
            用户ID,
            MAX(CASE WHEN 本场是否关注直播间 = '是' THEN 1 ELSE 0 END) AS ever_followed
        FROM comments
        GROUP BY 用户ID
    )
    SELECT 
        c.用户ID, 
        s.first_gift_time,
        s.total_gift_amount,
        CASE WHEN f.ever_followed = 1 THEN '是' ELSE '否' END AS is_follower,
        c.发言时间, 
        c.发言内容, 
        c.翻译内容
    FROM comments c
    JOIN spender_info s ON c.用户ID = s.用户ID
    LEFT JOIN follower_info f ON c.用户ID = f.用户ID
    ORDER BY s.total_gift_amount DESC, s.first_gift_time ASC, c.用户ID, c.发言时间 ASC;
    """
    
    print("Executing query...")
    rows = db.execute(query).fetchall()
    
    # Get total spenders in the gifts table for stats
    total_spenders = db.execute("SELECT count(DISTINCT 用户ID) FROM gifts").fetchone()[0]
    db.close()
    
    print(f"Total raw comments fetched: {len(rows)}")
    
    # Process and filter comments
    # We maintain order since SQL query is sorted by first_gift_time ASC
    user_map = {}
    ordered_user_ids = []
    
    skipped_comments_count = 0
    kept_comments_count = 0
    
    for user_id, first_gift_time, total_gift_amount, is_follower, msg_time, original, translated in rows:
        text_to_check = translated if translated else original
        
        # Check if the comment is only symbols and numbers
        if is_symbols_and_numbers(text_to_check):
            skipped_comments_count += 1
            continue
            
        kept_comments_count += 1
        
        if user_id not in user_map:
            user_map[user_id] = {
                "user_id": user_id,
                "first_gift_time": str(first_gift_time),
                "total_gift_amount": float(total_gift_amount),
                "is_follower": is_follower,
                "comments": []
            }
            ordered_user_ids.append(user_id)
            
        user_map[user_id]["comments"].append({
            "t": str(msg_time),
            "o": original,
            "tr": translated if translated else original
        })
        
    # Build list of users who have at least one comment after filtering
    spender_data = []
    for user_id in ordered_user_ids:
        user_info = user_map[user_id]
        if user_info["comments"]:
            spender_data.append(user_info)
            
    print(f"Total spenders who commented: {len(user_map)}")
    print(f"Spenders with comments remaining: {len(spender_data)}")
    print(f"Kept comments: {kept_comments_count}, Skipped comments: {skipped_comments_count}")
    
    # Write to HTML template
    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>打赏用户发言及翻译记录报告</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    <style>
        :root {
            --bg-dark: #070810;
            --panel-bg: rgba(18, 20, 32, 0.75);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #f59e0b;
            --primary-glow: rgba(245, 158, 11, 0.2);
            --accent-purple: #a855f7;
            --accent-green: #10b981;
            --accent-blue: #3b82f6;
            --accent-rose: #f43f5e;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Outfit', 'Noto Sans SC', sans-serif;
            padding: 24px;
            min-height: 100vh;
            background-image: radial-gradient(at 0% 0%, rgba(245, 158, 11, 0.12) 0px, transparent 50%),
                              radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.08) 0px, transparent 50%);
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
            border-radius: 16px;
            backdrop-filter: blur(12px);
        }
        h1 { font-size: 22px; font-weight: 600; display: flex; align-items: center; gap: 12px; }
        h1 i { color: var(--primary); }
        .controls {
            display: flex;
            gap: 16px;
            align-items: center;
        }
        .search-box {
            position: relative;
            width: 350px;
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
            padding: 10px 12px 10px 38px;
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: #fff;
            outline: none;
            font-size: 13px;
            transition: all 0.25s ease;
        }
        .search-box input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 12px var(--primary-glow);
        }
        .pagination-container {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: var(--text-muted);
        }
        .btn-page {
            padding: 8px 14px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-color);
            color: #fff;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }
        .btn-page:hover:not(:disabled) {
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
            color: #000;
            font-weight: 600;
        }
        .btn-page:disabled { opacity: 0.25; cursor: not-allowed; color: #fff; font-weight: normal; }
        
        /* Stats row */
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }
        @media (max-width: 800px) {
            .stats-row { grid-template-columns: repeat(2, 1fr); }
        }
        .stat-card {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 16px 20px;
            border-radius: 14px;
            backdrop-filter: blur(12px);
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .stat-card .label { font-size: 13px; color: var(--text-muted); font-weight: 500; }
        .stat-card .value { font-size: 24px; font-weight: 700; color: #fff; }
        .stat-card.primary .value { color: var(--primary); }
        .stat-card.purple .value { color: var(--accent-purple); }
        .stat-card.green .value { color: var(--accent-green); }

        /* Bottom Pagination panel */
        .footer-controls {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 16px 20px;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            backdrop-filter: blur(12px);
            margin-top: 10px;
        }
        
        /* Users stream container */
        .users-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 18px;
            width: 100%;
        }
        @media (max-width: 1050px) {
            .users-list {
                grid-template-columns: 1fr;
            }
        }
        .user-block {
            border-radius: 14px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            backdrop-filter: blur(12px);
            box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
            transition: all 0.25s ease;
        }
        .user-block:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 35px rgba(245, 158, 11, 0.15);
            border-color: rgba(245, 158, 11, 0.3);
        }
        .user-header {
            padding: 14px 20px;
            background: rgba(0, 0, 0, 0.25);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .user-info-left {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .user-id { font-size: 15px; font-weight: 600; color: #fff; }
        .rank-badge {
            font-size: 11px;
            background: rgba(245, 158, 11, 0.18);
            color: #fbbf24;
            padding: 2px 8px;
            border-radius: 12px;
            border: 1px solid rgba(245, 158, 11, 0.3);
            font-weight: 600;
        }
        .user-meta-right {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
            flex-wrap: wrap;
        }
        .follow-status {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 500;
        }
        .follow-status.yes {
            background: rgba(168, 85, 247, 0.15);
            color: #d8b4fe;
            border: 1px solid rgba(168, 85, 247, 0.3);
        }
        .follow-status.no {
            background: rgba(244, 63, 94, 0.1);
            color: #fda4af;
            border: 1px solid rgba(244, 63, 94, 0.25);
        }
        .gift-amount {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            padding: 2px 8px;
            border-radius: 6px;
            border: 1px solid rgba(16, 185, 129, 0.3);
            font-weight: 600;
        }
        .first-gift-time {
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 4px;
        }
        .comment-count { font-size: 11px; background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.3); }
        
        .comments-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .comments-table th {
            text-align: left;
            padding: 10px 20px;
            background: rgba(0, 0, 0, 0.12);
            color: var(--text-muted);
            font-weight: 500;
            border-bottom: 1px solid var(--border-color);
        }
        .comments-table td {
            padding: 11px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            vertical-align: top;
        }
        .comments-table tr:last-child td { border-bottom: none; }
        .time-col { width: 160px; color: var(--text-muted); font-size: 12px; }
        .orig-col { width: 42%; color: var(--text-muted); word-break: break-word; }
        .trans-col { width: 42%; color: #fff; font-weight: 400; word-break: break-word; }
        
        .empty-state {
            grid-column: 1 / -1;
            padding: 80px;
            text-align: center;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            color: var(--text-muted);
        }

        /* Language Switcher Styling */
        .lang-selector-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            background: rgba(18, 20, 32, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 6px 12px;
            backdrop-filter: blur(12px);
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }
        .lang-selector-container i {
            color: var(--text-muted);
            font-size: 14px;
        }
        .lang-selector-container select {
            background: transparent;
            border: none;
            color: var(--text-main);
            font-size: 12.5px;
            font-weight: 500;
            outline: none;
            cursor: pointer;
            font-family: inherit;
        }
        .lang-selector-container select option {
            background: #121420;
            color: var(--text-main);
        }
    </style>
</head>
<body>
    <!-- Float Language Selector -->
    <div class="lang-selector-container">
        <i class="fas fa-globe"></i>
        <select id="lang-select">
            <option value="zh">简体中文</option>
            <option value="ko">한국어</option>
        </select>
    </div>

    <div class="container">
        <!-- Top controls header -->
        <header>
            <h1 id="header-title"><i class="fas fa-donate"></i> 打赏用户发言及翻译记录报告</h1>
            <div class="controls">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="user-search" placeholder="搜索用户ID、打赏顺序、是否关注...">
                </div>
                <div class="pagination-container">
                    <button class="btn-page btn-prev" disabled></button>
                    <span class="page-num"></span>
                    <button class="btn-page btn-next" disabled></button>
                </div>
            </div>
        </header>

        <!-- Stats row -->
        <div class="stats-row">
            <div class="stat-card primary">
                <span class="label">打赏用户总数</span>
                <span class="value">{TOTAL_SPENDERS}</span>
            </div>
            <div class="stat-card purple">
                <span class="label">发言打赏用户数</span>
                <span class="value">{ACTIVE_SPENDERS}</span>
            </div>
            <div class="stat-card green">
                <span class="label">保留发言条数</span>
                <span class="value">{KEPT_COMMENTS}</span>
            </div>
            <div class="stat-card">
                <span class="label">过滤符号/数字条数</span>
                <span class="value">{SKIPPED_COMMENTS}</span>
            </div>
        </div>

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
        let filteredUsers = [...commentData];

        const elements = {
            container: document.getElementById('users-list-container'),
            search: document.getElementById('user-search'),
            btnsPrev: document.querySelectorAll('.btn-prev'),
            btnsNext: document.querySelectorAll('.btn-next'),
            pagesNum: document.querySelectorAll('.page-num')
        };

        const i18n = {
            zh: {
                title_page: '打赏用户发言及翻译记录报告',
                title_header: '<i class="fas fa-donate"></i> 打赏用户发言及翻译记录报告',
                search_placeholder: '搜索用户ID、打赏顺序、是否关注...',
                prev_btn: '<i class="fas fa-chevron-left"></i> 上一页',
                next_btn: '下一页 <i class="fas fa-chevron-right"></i>',
                stat_total_spenders: '打赏用户总数',
                stat_active_spenders: '发言打赏用户数',
                stat_kept_comments: '保留发言条数',
                stat_skipped_comments: '过滤符号/数字条数',
                table_time: '发言时间',
                table_orig: '原文',
                table_trans: '中文翻译',
                empty_state: '未找到匹配的打赏用户或发言记录',
                comments_suffix: '条发言',
                rank_prefix: '打赏排行: #',
                first_tip_prefix: '首次: ',
                follow_status: (status) => `关注: ${status === '是' ? '是' : '否'}`,
                total_tip_prefix: '打赏: ',
                page_info: (current, total, count) => `第 ${current} / ${total} 页 (共 ${count} 个打赏用户)`
            },
            ko: {
                title_page: '후원 사용자 발언 및 번역 기록 보고서',
                title_header: '<i class="fas fa-donate"></i> 후원 사용자 발언 및 번역 기록 보고서',
                search_placeholder: '사용자 ID, 후원 순위, 팔로우 여부 검색...',
                prev_btn: '<i class="fas fa-chevron-left"></i> 이전 페이지',
                next_btn: '다음 페이지 <i class="fas fa-chevron-right"></i>',
                stat_total_spenders: '총 후원 사용자 수',
                stat_active_spenders: '발언한 후원 사용자 수',
                stat_kept_comments: '보존된 발언 수',
                stat_skipped_comments: '필터링된 기호/숫자 수',
                table_time: '발언 시간',
                table_orig: '원문',
                table_trans: '중국어 번역',
                empty_state: '일치하는 후원 사용자 또는 발언 기록을 찾을 수 없습니다',
                comments_suffix: '개 발언',
                rank_prefix: '후원 랭킹: #',
                first_tip_prefix: '최초: ',
                follow_status: (status) => `팔로우: ${status === '是' ? '예' : '아니오'}`,
                total_tip_prefix: '후원: ',
                page_info: (current, total, count) => `${current} / ${total} 페이지 (총 ${count}명 후원 사용자)`
            }
        };

        function getUserBgColor(userId) {
            let hash = 0;
            for (let i = 0; i < userId.length; i++) {
                hash = userId.charCodeAt(i) + ((hash << 5) - hash);
            }
            const h = Math.abs(hash % 360);
            return `hsla(${h}, 35%, 11%, 0.45)`;
        }

        function renderPage() {
            elements.container.innerHTML = '';
            const lang = localStorage.getItem('pref_lang') || 'zh';
            
            if (filteredUsers.length === 0) {
                elements.container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-search" style="font-size: 36px; margin-bottom: 12px; display: block; opacity: 0.5; color: var(--primary);"></i>
                        <p>${i18n[lang].empty_state}</p>
                    </div>
                `;
                elements.btnsPrev.forEach(btn => btn.disabled = true);
                elements.btnsNext.forEach(btn => btn.disabled = true);
                elements.pagesNum.forEach(el => el.textContent = i18n[lang].page_info(0, 0, 0));
                return;
            }

            const totalPages = Math.ceil(filteredUsers.length / pageSize);
            if (currentPage > totalPages) currentPage = totalPages;
            if (currentPage < 1) currentPage = 1;

            const startIdx = (currentPage - 1) * pageSize;
            const endIdx = Math.min(startIdx + pageSize, filteredUsers.length);
            const pageUsers = filteredUsers.slice(startIdx, endIdx);

            pageUsers.forEach(user => {
                const comments = user.comments;
                const bgColor = getUserBgColor(user.user_id);
                const followClass = user.is_follower === '是' ? 'yes' : 'no';
                
                const block = document.createElement('div');
                block.className = 'user-block';
                block.style.backgroundColor = bgColor;
                
                let blockHtml = `
                    <div class="user-header">
                        <div class="user-info-left">
                            <span class="user-id"><i class="fas fa-user-circle"></i> ${user.user_id}</span>
                            <span class="rank-badge">${i18n[lang].rank_prefix}${user.index}</span>
                        </div>
                        <div class="user-meta-right">
                            <span class="follow-status ${followClass}"><i class="fas fa-heart"></i> ${i18n[lang].follow_status(user.is_follower)}</span>
                            <span class="gift-amount"><i class="fas fa-dollar-sign"></i> ${i18n[lang].total_tip_prefix}$${user.total_gift_amount.toFixed(2)}</span>
                            <span class="first-gift-time"><i class="far fa-clock"></i> ${i18n[lang].first_tip_prefix}${user.first_gift_time}</span>
                            <span class="comment-count">${comments.length} ${i18n[lang].comments_suffix}</span>
                        </div>
                    </div>
                    <table class="comments-table">
                        <thead>
                            <tr>
                                <th class="time-col">${i18n[lang].table_time}</th>
                                <th class="orig-col">${i18n[lang].table_orig}</th>
                                <th class="trans-col">${i18n[lang].table_trans}</th>
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

            const paginationText = i18n[lang].page_info(currentPage, totalPages, filteredUsers.length);
            elements.pagesNum.forEach(el => el.textContent = paginationText);
            
            elements.btnsPrev.forEach(btn => btn.disabled = currentPage === 1);
            elements.btnsNext.forEach(btn => btn.disabled = currentPage === totalPages);
        }

        function handleSearch() {
            const query = elements.search.value.trim().toLowerCase();
            const lang = localStorage.getItem('pref_lang') || 'zh';
            
            if (!query) {
                filteredUsers = [...commentData];
            } else {
                filteredUsers = commentData.filter(user => {
                    const matchUser = user.user_id.toLowerCase().includes(query) || 
                                      (i18n[lang].rank_prefix + user.index).toLowerCase().includes(query) ||
                                      user.index.toString() === query ||
                                      (i18n[lang].follow_status(user.is_follower)).toLowerCase().includes(query) ||
                                      ((query === "关注" || query === "팔로우" || query === "예") && user.is_follower === "是") ||
                                      ((query === "未关注" || query === "미팔로우" || query === "아니오") && user.is_follower === "否");
                    if (matchUser) return true;
                    
                    return user.comments.some(c => 
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

        function updateLanguage(lang) {
            document.title = i18n[lang].title_page;
            document.getElementById('header-title').innerHTML = i18n[lang].title_header;
            elements.search.setAttribute('placeholder', i18n[lang].search_placeholder);
            elements.btnsPrev.forEach(btn => btn.innerHTML = i18n[lang].prev_btn);
            elements.btnsNext.forEach(btn => btn.innerHTML = i18n[lang].next_btn);
            
            // Stats labels
            const labels = document.querySelectorAll('.stat-card .label');
            if (labels.length >= 4) {
                labels[0].textContent = i18n[lang].stat_total_spenders;
                labels[1].textContent = i18n[lang].stat_active_spenders;
                labels[2].textContent = i18n[lang].stat_kept_comments;
                labels[3].textContent = i18n[lang].stat_skipped_comments;
            }
            
            localStorage.setItem('pref_lang', lang);
            renderPage();
        }

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
                const totalPages = Math.ceil(filteredUsers.length / pageSize);
                if (currentPage < totalPages) {
                    currentPage++;
                    renderPage();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        });

        // Setup dropdown
        const savedLang = localStorage.getItem('pref_lang') || 'zh';
        const langSelect = document.getElementById('lang-select');
        langSelect.value = savedLang;
        updateLanguage(savedLang);

        langSelect.addEventListener('change', (e) => {
            updateLanguage(e.target.value);
            window.dispatchEvent(new Event('storage'));
        });

        // Listen for language change in other tabs
        window.addEventListener('storage', () => {
            const currentLang = localStorage.getItem('pref_lang') || 'zh';
            if (langSelect.value !== currentLang) {
                langSelect.value = currentLang;
                updateLanguage(currentLang);
            }
        });

        renderPage();
    </script>
</body>
</html>
"""
    # Add index rank based on first tipping order
    for i, user_info in enumerate(spender_data):
        user_info["index"] = i + 1
        
    json_data = json.dumps(spender_data, ensure_ascii=False)
    
    # Inject values into HTML template
    html = html_template
    html = html.replace("{TOTAL_SPENDERS}", str(total_spenders))
    html = html.replace("{ACTIVE_FOLLOWERS}", str(len(spender_data))) # backwards compatibility if any
    html = html.replace("{ACTIVE_SPENDERS}", str(len(spender_data)))
    html = html.replace("{KEPT_COMMENTS}", str(kept_comments_count))
    html = html.replace("{SKIPPED_COMMENTS}", str(skipped_comments_count))
    html = html.replace("%DATA_JSON%", json_data)
    
    # Create target directory and write file
    os.makedirs(os.path.dirname(OUTPUT_HTML_PATH), exist_ok=True)
    with open(OUTPUT_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
        
    print(f"HTML report successfully written to: {OUTPUT_HTML_PATH}")

if __name__ == '__main__':
    generate_report()
