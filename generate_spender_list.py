import os
import json
import duckdb

DB_PATH = 'livestream.db'
OUTPUT_HTML_PATH = 'publish/spender_list.html'

def get_db():
    return duckdb.connect(database=DB_PATH, read_only=True)

def generate_report():
    print("Connecting to database...")
    db = get_db()
    
    # Query: Get the spender list sorted by total tipping amount descending
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
            MAX(CASE WHEN 本场是否关注直播间 = '是' THEN 1 ELSE 0 END) AS ever_followed,
            MIN(关注行为的时间) AS follow_time
        FROM comments
        GROUP BY 用户ID
    ),
    comment_count_info AS (
        SELECT 
            用户ID,
            COUNT(*) AS total_comments
        FROM comments
        GROUP BY 用户ID
    )
    SELECT 
        s.用户ID,
        CASE WHEN f.ever_followed = 1 THEN '是' ELSE '否' END AS is_follower,
        f.follow_time,
        s.total_gift_amount,
        s.first_gift_time,
        COALESCE(c.total_comments, 0) AS total_comments
    FROM spender_info s
    LEFT JOIN follower_info f ON s.用户ID = f.用户ID
    LEFT JOIN comment_count_info c ON s.用户ID = c.用户ID
    ORDER BY s.total_gift_amount DESC, s.first_gift_time ASC;
    """
    
    print("Executing query...")
    rows = db.execute(query).fetchall()
    
    # Get database totals for stats
    total_spenders = len(rows)
    total_tipped_sum = db.execute("SELECT ROUND(SUM(打赏金额_USD), 2) FROM gifts").fetchone()[0]
    high_value_spenders = db.execute("SELECT count(DISTINCT 用户ID) FROM gifts GROUP BY 用户ID HAVING SUM(打赏金额_USD) >= 100").fetchall()
    high_value_count = len(high_value_spenders)
    
    db.close()
    
    # Format rows for JSON
    spender_list = []
    active_spenders_count = 0
    
    for i, row in enumerate(rows):
        user_id, is_follower, follow_time, total_amount, first_tip_time, comment_count = row
        if comment_count > 0:
            active_spenders_count += 1
            
        spender_list.append({
            "index": i + 1,
            "user_id": user_id,
            "is_follower": is_follower,
            "follow_time": str(follow_time) if follow_time else "-",
            "total_gift_amount": float(total_amount),
            "first_gift_time": str(first_tip_time),
            "comment_count": int(comment_count)
        })
        
    print(f"Total Spenders: {total_spenders}")
    print(f"Total Tipped Sum: ${total_tipped_sum}")
    print(f"High Value Spenders (>= $100): {high_value_count}")
    print(f"Active Spenders (who commented): {active_spenders_count}")
    
    json_data = json.dumps(spender_list, ensure_ascii=False)
    
    # Write to HTML template
    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>打赏用户清单排行榜</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    <style>
        :root {
            --bg-dark: #06070c;
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
            max-width: 1300px;
            margin: 0 auto;
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

        /* Table wrapper styling */
        .list-panel {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }
        .table-wrapper {
            overflow-x: auto;
            width: 100%;
        }
        .spender-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }
        .spender-table th {
            padding: 16px 20px;
            background: rgba(0, 0, 0, 0.2);
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            letter-spacing: 0.5px;
        }
        .spender-table td {
            padding: 14px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            vertical-align: middle;
            color: var(--text-main);
        }
        .spender-table tr:hover td {
            background: rgba(255, 255, 255, 0.015);
        }
        .spender-table tr:last-child td { border-bottom: none; }
        
        .rank-col { font-weight: 700; color: var(--primary); width: 80px; }
        .rank-gold { color: #fbbf24; }
        .rank-silver { color: #cbd5e1; }
        .rank-bronze { color: #b45309; }
        
        .user-col { font-weight: 600; color: #fff; display: flex; align-items: center; gap: 8px; }
        .user-col i { opacity: 0.5; color: var(--text-muted); }
        
        .badge {
            font-size: 11.5px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 6px;
            display: inline-block;
            text-align: center;
        }
        .badge.yes {
            background: rgba(168, 85, 247, 0.15);
            color: #d8b4fe;
            border: 1px solid rgba(168, 85, 247, 0.3);
        }
        .badge.no {
            background: rgba(244, 63, 94, 0.1);
            color: #fda4af;
            border: 1px solid rgba(244, 63, 94, 0.25);
        }
        
        .amount-col { font-weight: 700; color: #34d399; font-size: 15px; }
        .time-col { color: var(--text-muted); font-size: 13px; }
        .count-col { font-weight: 600; color: #60a5fa; }
        
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
        
        .empty-state {
            padding: 80px;
            text-align: center;
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
            <h1 id="header-title"><i class="fas fa-trophy"></i> 打赏用户清单排行榜</h1>
            <div class="controls">
                <div class="search-box">
                    <i class="fas fa-search"></i>
                    <input type="text" id="user-search" placeholder="搜索用户ID、关注状态（是/否）...">
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
                <span class="label">高额打赏用户数 (≥ $100)</span>
                <span class="value">{HIGH_VALUE_COUNT}</span>
            </div>
            <div class="stat-card green">
                <span class="label">打赏总金额</span>
                <span class="value">${TOTAL_TIPPED_SUM}</span>
            </div>
            <div class="stat-card">
                <span class="label">活跃打赏人数 (有发言)</span>
                <span class="value">{ACTIVE_SPENDERS}</span>
            </div>
        </div>

        <!-- Main list container -->
        <div class="list-panel">
            <div class="table-wrapper">
                <table class="spender-table">
                    <thead>
                        <tr>
                            <th style="width: 80px;">排行</th>
                            <th>用户 ID</th>
                            <th style="width: 100px;">是否关注</th>
                            <th>关注直播间的时间</th>
                            <th>累计打赏金额 (USD)</th>
                            <th>首次打赏时间</th>
                            <th style="width: 130px;">发言条数</th>
                        </tr>
                    </thead>
                    <tbody id="table-body">
                        <!-- Dynamic rows load here -->
                    </tbody>
                </table>
            </div>
            <div id="empty-state" class="empty-state" style="display:none;">
                <i class="fas fa-search" style="font-size: 36px; margin-bottom: 12px; display: block; opacity: 0.5; color: var(--primary);"></i>
                <p>未找到匹配的打赏用户记录</p>
            </div>
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
        const pageSize = 100; // Render 100 users per page
        let filteredUsers = [...commentData];

        const elements = {
            tbody: document.getElementById('table-body'),
            empty: document.getElementById('empty-state'),
            search: document.getElementById('user-search'),
            btnsPrev: document.querySelectorAll('.btn-prev'),
            btnsNext: document.querySelectorAll('.btn-next'),
            pagesNum: document.querySelectorAll('.page-num')
        };

        const i18n = {
            zh: {
                title_page: '打赏用户清单排行榜',
                title_header: '<i class="fas fa-trophy"></i> 打赏用户清单排行榜',
                search_placeholder: '搜索用户ID、关注状态（是/否）...',
                prev_btn: '<i class="fas fa-chevron-left"></i> 上一页',
                next_btn: '下一页 <i class="fas fa-chevron-right"></i>',
                stat_total_spenders: '打赏用户总数',
                stat_high_value: '高额打赏用户数 (≥ $100)',
                stat_total_gift: '打赏总金额',
                stat_active_spenders: '活跃打赏人数 (有发言)',
                th_rank: '排行',
                th_user: '用户 ID',
                th_is_follower: '是否关注',
                th_follow_time: '关注直播间的时间',
                th_gift_amount: '累计打赏金额 (USD)',
                th_first_gift: '首次打赏时间',
                th_comments: '发言条数',
                badge_yes: '是',
                badge_no: '否',
                comments_suffix: ' 条',
                empty_state: '未找到匹配的打赏用户记录',
                page_info: (current, total, count) => `第 ${current} / ${total} 页 (共 ${count} 个打赏用户)`
            },
            ko: {
                title_page: '후원 사용자 목록 랭킹',
                title_header: '<i class="fas fa-trophy"></i> 후원 사용자 목록 랭킹',
                search_placeholder: '사용자 ID, 팔로우 상태(예/아니오) 검색...',
                prev_btn: '<i class="fas fa-chevron-left"></i> 이전 페이지',
                next_btn: '다음 페이지 <i class="fas fa-chevron-right"></i>',
                stat_total_spenders: '총 후원 사용자 수',
                stat_high_value: '고액 후원 사용자 수 (≥ $100)',
                stat_total_gift: '총 후원 금액',
                stat_active_spenders: '활성 후원자 수 (발언 있음)',
                th_rank: '순위',
                th_user: '사용자 ID',
                th_is_follower: '팔로우 여부',
                th_follow_time: '라이브 스트림 팔로우 시간',
                th_gift_amount: '누적 후원 금액 (USD)',
                th_first_gift: '최초 후원 시간',
                th_comments: '발언 수',
                badge_yes: '예',
                badge_no: '아니오',
                comments_suffix: ' 개',
                empty_state: '일치하는 후원 사용자 기록을 찾을 수 없습니다',
                page_info: (current, total, count) => `${current} / ${total} 페이지 (총 ${count}명 후원 사용자)`
            }
        };

        function getRankClass(rank) {
            if (rank === 1) return 'rank-gold';
            if (rank === 2) return 'rank-silver';
            if (rank === 3) return 'rank-bronze';
            return '';
        }

        function renderPage() {
            elements.tbody.innerHTML = '';
            const lang = localStorage.getItem('pref_lang') || 'zh';
            
            if (filteredUsers.length === 0) {
                elements.empty.innerHTML = `
                    <i class="fas fa-search" style="font-size: 36px; margin-bottom: 12px; display: block; opacity: 0.5; color: var(--primary);"></i>
                    <p>${i18n[lang].empty_state}</p>
                `;
                elements.empty.style.display = 'block';
                elements.btnsPrev.forEach(btn => btn.disabled = true);
                elements.btnsNext.forEach(btn => btn.disabled = true);
                elements.pagesNum.forEach(el => el.textContent = i18n[lang].page_info(0, 0, 0));
                return;
            }
            elements.empty.style.display = 'none';

            const totalPages = Math.ceil(filteredUsers.length / pageSize);
            if (currentPage > totalPages) currentPage = totalPages;
            if (currentPage < 1) currentPage = 1;

            const startIdx = (currentPage - 1) * pageSize;
            const endIdx = Math.min(startIdx + pageSize, filteredUsers.length);
            const pageUsers = filteredUsers.slice(startIdx, endIdx);

            pageUsers.forEach(user => {
                const tr = document.createElement('tr');
                
                const rankClass = getRankClass(user.index);
                const isFollowerTrans = user.is_follower === '是' ? i18n[lang].badge_yes : i18n[lang].badge_no;
                const followClass = user.is_follower === '是' ? 'yes' : 'no';
                
                tr.innerHTML = `
                    <td class="rank-col ${rankClass}">#${user.index}</td>
                    <td>
                        <div class="user-col">
                            <i class="fas fa-user-circle"></i>
                            <span>${user.user_id}</span>
                        </div>
                    </td>
                    <td>
                        <span class="badge ${followClass}">${isFollowerTrans}</span>
                    </td>
                    <td class="time-col">${user.follow_time}</td>
                    <td class="amount-col">$${user.total_gift_amount.toFixed(2)}</td>
                    <td class="time-col">${user.first_gift_time}</td>
                    <td class="count-col">${user.comment_count}${i18n[lang].comments_suffix}</td>
                `;
                elements.tbody.appendChild(tr);
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
                                      user.index.toString() === query ||
                                      ("关注: " + user.is_follower).toLowerCase().includes(query) ||
                                      ((query === "关注" || query === "팔로우" || query === "예") && user.is_follower === "是") ||
                                      ((query === "未关注" || query === "미팔로우" || query === "아니오") && user.is_follower === "否");
                    return matchUser;
                });
            }
            
            currentPage = 1;
            renderPage();
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
                labels[1].textContent = i18n[lang].stat_high_value;
                labels[2].textContent = i18n[lang].stat_total_gift;
                labels[3].textContent = i18n[lang].stat_active_spenders;
            }
            
            // Table headers
            const ths = document.querySelectorAll('.spender-table th');
            if (ths.length >= 7) {
                ths[0].textContent = i18n[lang].th_rank;
                ths[1].textContent = i18n[lang].th_user;
                ths[2].textContent = i18n[lang].th_is_follower;
                ths[3].textContent = i18n[lang].th_follow_time;
                ths[4].textContent = i18n[lang].th_gift_amount;
                ths[5].textContent = i18n[lang].th_first_gift;
                ths[6].textContent = i18n[lang].th_comments;
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
    # Inject stats and data into template
    html = html_template
    html = html.replace("{TOTAL_SPENDERS}", str(total_spenders))
    html = html.replace("{HIGH_VALUE_COUNT}", str(high_value_count))
    html = html.replace("{TOTAL_TIPPED_SUM}", f"{total_tipped_sum:,.2f}")
    html = html.replace("{ACTIVE_SPENDERS}", str(active_spenders_count))
    html = html.replace("%DATA_JSON%", json_data)
    
    # Write output to HTML
    os.makedirs(os.path.dirname(OUTPUT_HTML_PATH), exist_ok=True)
    with open(OUTPUT_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
        
    print(f"HTML spender list successfully written to: {OUTPUT_HTML_PATH}")

if __name__ == '__main__':
    generate_report()
