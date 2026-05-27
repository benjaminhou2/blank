// app.js - Livestream Analyzer Frontend Controller

document.addEventListener('DOMContentLoaded', () => {
    // State Variables
    let appState = {
        schema: {},
        presets: [],
        queryResult: { columns: [], rows: [] },
        filteredRows: [],
        currentPage: 1,
        pageSize: 15,
        sortColumn: null,
        sortDirection: 'asc',
        chartInstance: null,
        activePresetId: null
    };

    // DOM Elements
    const elements = {
        sqlEditor: document.getElementById('sql-editor'),
        lineNumbers: document.getElementById('line-numbers'),
        btnRun: document.getElementById('btn-run'),
        btnFormat: document.getElementById('btn-format'),
        btnClear: document.getElementById('btn-clear'),
        schemaContainer: document.getElementById('schema-container'),
        presetsContainer: document.getElementById('presets-container'),
        tableWrapper: document.getElementById('table-wrapper'),
        tableSearch: document.getElementById('table-search'),
        paginationInfo: document.getElementById('pagination-info'),
        errorToast: document.getElementById('error-toast'),
        errorMessage: document.getElementById('error-message'),
        btnCloseToast: document.getElementById('btn-close-toast'),
        resultsMeta: document.getElementById('results-meta'),
        tabBtns: document.querySelectorAll('.tab-btn'),
        tabContents: document.querySelectorAll('.tab-content'),
        chartContainer: document.getElementById('chart-container'),
        chartEmptyState: document.getElementById('chart-empty-state'),
        chartTypeSelect: document.getElementById('chart-type-select'),
        chartXSelect: document.getElementById('chart-x-select'),
        chartYSelect: document.getElementById('chart-y-select'),
        btnUpdateChart: document.getElementById('btn-update-chart'),
        
        // Sidebar tab elements
        sTabBtns: document.querySelectorAll('.s-tab-btn'),
        sTabContents: document.querySelectorAll('.s-tab-content'),
        
        // Chat elements
        chatMessages: document.getElementById('chat-messages'),
        chatInput: document.getElementById('chat-input'),
        btnChatSend: document.getElementById('btn-chat-send'),
        aiActiveIndicator: document.getElementById('ai-active-indicator')
    };

    // Initialize App
    init();

    function init() {
        // Load Schema & Presets
        fetchSchema();
        fetchPresets();

        // Bind Events
        elements.btnRun.addEventListener('click', executeQuery);
        elements.btnClear.addEventListener('click', clearEditor);
        elements.btnFormat.addEventListener('click', formatSQL);
        elements.tableSearch.addEventListener('input', handleTableSearch);
        elements.btnCloseToast.addEventListener('click', hideError);
        elements.btnUpdateChart.addEventListener('click', renderCustomChart);

        // SQL Editor Line Numbers & Keyboard Shortcuts
        elements.sqlEditor.addEventListener('input', updateLineNumbers);
        elements.sqlEditor.addEventListener('scroll', syncEditorScroll);
        elements.sqlEditor.addEventListener('keydown', handleEditorKeys);

        // Sidebar Tabs Switcher
        elements.sTabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetSTab = btn.getAttribute('data-stab');
                switchSidebarTab(targetSTab);
            });
        });

        // Chat Input Events
        elements.chatInput.addEventListener('keydown', handleChatInputKeys);
        elements.btnChatSend.addEventListener('click', sendChatMessage);

        // Tab Switching
        elements.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.getAttribute('data-tab');
                switchTab(targetTab);
            });
        });

        // Initialize ECharts
        initChart();
        
        // Auto-focus Editor
        elements.sqlEditor.focus();
    }

    // --- Sidebar Tabs Switcher ---

    function switchSidebarTab(stabId) {
        elements.sTabBtns.forEach(btn => {
            if (btn.getAttribute('data-stab') === stabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        elements.sTabContents.forEach(content => {
            if (content.id === stabId) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    }

    // --- Database Metadata & Presets Ingestion ---

    async function fetchSchema() {
        try {
            const res = await fetch('/api/schema');
            if (!res.ok) throw new Error('Failed to load schema');
            appState.schema = await res.json();
            renderSchema();
        } catch (err) {
            elements.schemaContainer.innerHTML = `<div class="loading-small" style="color:var(--danger)">加载结构失败: ${err.message}</div>`;
        }
    }

    async function fetchPresets() {
        try {
            const res = await fetch('/api/presets');
            if (!res.ok) throw new Error('Failed to load presets');
            appState.presets = await res.json();
            renderPresets();
        } catch (err) {
            elements.presetsContainer.innerHTML = `<div class="loading-small" style="color:var(--danger)">加载预设失败: ${err.message}</div>`;
        }
    }

    function renderSchema() {
        elements.schemaContainer.innerHTML = '';
        
        Object.entries(appState.schema).forEach(([tableName, columns]) => {
            const tableDiv = document.createElement('div');
            tableDiv.className = 'schema-tableExpanded schema-table'; // expanded by default
            tableDiv.classList.add('expanded');
            
            const headerDiv = document.createElement('div');
            headerDiv.className = 'schema-table-header';
            headerDiv.innerHTML = `
                <span class="table-name"><i class="fas fa-table"></i> ${tableName}</span>
                <span class="arrow"><i class="fas fa-chevron-right"></i></span>
            `;
            
            headerDiv.addEventListener('click', () => {
                tableDiv.classList.toggle('expanded');
            });
            
            const colsDiv = document.createElement('div');
            colsDiv.className = 'schema-table-columns';
            
            columns.forEach(col => {
                const colItem = document.createElement('div');
                colItem.className = 'column-item';
                colItem.innerHTML = `
                    <span class="col-name">${col.name}</span>
                    <span class="col-type">${col.type.toLowerCase()}</span>
                `;
                
                colItem.addEventListener('click', (e) => {
                    e.stopPropagation();
                    insertTextAtCursor(col.name);
                });
                
                colsDiv.appendChild(colItem);
            });
            
            tableDiv.appendChild(headerDiv);
            tableDiv.appendChild(colsDiv);
            elements.schemaContainer.appendChild(tableDiv);
        });
    }

    function renderPresets() {
        elements.presetsContainer.innerHTML = '';
        
        appState.presets.forEach(preset => {
            const card = document.createElement('button');
            card.className = 'preset-card';
            card.innerHTML = `
                <h4>${preset.name}</h4>
                <p>${preset.description}</p>
            `;
            
            card.addEventListener('click', () => {
                elements.sqlEditor.value = preset.sql;
                appState.activePresetId = preset.id;
                elements.aiActiveIndicator.style.display = 'none';
                updateLineNumbers();
                switchTab('tab-table');
                executeQuery();
            });
            
            elements.presetsContainer.appendChild(card);
        });
    }

    // --- SQL Editor Helper Functions ---

    function updateLineNumbers() {
        const text = elements.sqlEditor.value;
        const lines = text.split('\n').length;
        let numbersHtml = '';
        for (let i = 1; i <= lines; i++) {
            numbersHtml += `${i}<br>`;
        }
        elements.lineNumbers.innerHTML = numbersHtml;
    }

    function syncEditorScroll() {
        elements.lineNumbers.scrollTop = elements.sqlEditor.scrollTop;
    }

    function handleEditorKeys(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 4;
            updateLineNumbers();
        }
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            executeQuery();
        }
        if (e.altKey && e.key === 'f') {
            e.preventDefault();
            formatSQL();
        }
    }

    function insertTextAtCursor(text) {
        const editor = elements.sqlEditor;
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const currentVal = editor.value;
        editor.value = currentVal.substring(0, start) + text + currentVal.substring(end);
        editor.selectionStart = editor.selectionEnd = start + text.length;
        editor.focus();
        updateLineNumbers();
    }

    function clearEditor() {
        elements.sqlEditor.value = '';
        elements.sqlEditor.focus();
        appState.activePresetId = null;
        elements.aiActiveIndicator.style.display = 'none';
        updateLineNumbers();
    }

    function formatSQL() {
        let sql = elements.sqlEditor.value;
        if (!sql.trim()) return;
        
        const keywords = [
            'select', 'from', 'where', 'join', 'left', 'right', 'inner', 'outer', 'on',
            'group by', 'order by', 'limit', 'and', 'or', 'as', 'insert', 'update',
            'delete', 'create', 'table', 'drop', 'exists', 'having', 'union', 'all',
            'desc', 'asc', 'nulls', 'first', 'last', 'round', 'sum', 'count', 'avg',
            'min', 'max', 'distinct', 'hour', 'date', 'year', 'month', 'day'
        ];
        
        keywords.sort((a, b) => b.length - a.length);
        
        keywords.forEach(keyword => {
            const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
            sql = sql.replace(regex, keyword.toUpperCase());
        });
        
        elements.sqlEditor.value = sql;
        updateLineNumbers();
    }

    // --- AI Chat Assistant Engine ---

    function handleChatInputKeys(e) {
        // Send message on Enter without shift key
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    }

    async function sendChatMessage() {
        const messageText = elements.chatInput.value.trim();
        if (!messageText) return;

        // Clear input area
        elements.chatInput.value = '';

        // Append user bubble to messages log
        appendChatBubble('user', `<p>${escapeHtml(messageText)}</p>`);
        scrollChatToBottom();

        // Append AI typing spinner bubble
        const typingId = appendTypingIndicator();
        scrollChatToBottom();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: messageText })
            });

            const data = await res.json();
            removeTypingIndicator(typingId);

            if (!res.ok) {
                throw new Error(data.error || 'DeepSeek API error');
            }

            // Construct AI bubble content
            const explanation = data.explanation || '我已为您生成了对应的查询语句。';
            const sql = data.sql || '';
            
            let bubbleHtml = `
                <p>${escapeHtml(explanation)}</p>
                <div class="chat-sql-box">${escapeHtml(sql)}</div>
                <div class="chat-btn-group">
                    <button class="chat-action-btn load-ai-data" data-sql="${encodeURIComponent(sql)}">
                        <i class="fas fa-database"></i> 载入数据并绘图
                    </button>
                </div>
            `;

            // Append AI bubble to messages log
            appendChatBubble('ai', bubbleHtml);
            scrollChatToBottom();

            // Bind click listener for loading AI query results
            bindLoadAiDataListeners(data);

        } catch (err) {
            removeTypingIndicator(typingId);
            appendChatBubble('ai', `<p style="color:var(--danger)"><strong>查询失败：</strong>${escapeHtml(err.message)}</p>`);
            scrollChatToBottom();
            showError(err.message);
        }
    }

    function appendChatBubble(sender, htmlContent) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${sender}`;
        bubble.innerHTML = htmlContent;
        elements.chatMessages.appendChild(bubble);
        return bubble;
    }

    function appendTypingIndicator() {
        const bubble = document.createElement('div');
        const uniqueId = 'typing-' + Date.now();
        bubble.id = uniqueId;
        bubble.className = 'chat-bubble ai';
        bubble.innerHTML = `
            <div class="typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        elements.chatMessages.appendChild(bubble);
        return uniqueId;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollChatToBottom() {
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }

    function bindLoadAiDataListeners(data) {
        // Find all buttons, get the last one (most recent response)
        const buttons = document.querySelectorAll('.load-ai-data');
        if (buttons.length === 0) return;
        
        const lastBtn = buttons[buttons.length - 1];
        lastBtn.addEventListener('click', () => {
            const sql = decodeURIComponent(lastBtn.getAttribute('data-sql'));
            
            // 1. Copy SQL to editor
            elements.sqlEditor.value = sql;
            appState.activePresetId = null;
            elements.aiActiveIndicator.style.display = 'inline-block';
            updateLineNumbers();
            
            // 2. Load the results (already fetched) directly into appState to save request time
            appState.queryResult = {
                columns: data.columns || [],
                rows: data.rows || []
            };
            appState.filteredRows = [...appState.queryResult.rows];
            appState.currentPage = 1;
            appState.sortColumn = null;
            
            elements.resultsMeta.innerHTML = `由 AI 助手查找到 ${appState.filteredRows.length} 条数据 (内存实时载入)`;
            elements.tableSearch.value = '';
            
            // 3. Switch to table view
            switchTab('tab-table');
            
            // 4. Render Table
            renderResultView();
            
            // 5. Update axis selections & chart rendering
            updateChartAxisDropdowns();
            autoChartForAiResult();
        });
    }

    function autoChartForAiResult() {
        const columns = appState.queryResult.columns;
        const rows = appState.queryResult.rows;
        
        if (columns.length < 2 || rows.length === 0) {
            elements.chartEmptyState.style.display = 'flex';
            return;
        }

        // Try to identify best axis fields
        // X axis: Look for date, time, timestamp, or text string columns
        let xIdx = 0;
        let yIdx = 1;
        
        // Find first text or date/time column for X
        for (let i = 0; i < columns.length; i++) {
            const col = columns[i].toLowerCase();
            if (col.includes('时间') || col.includes('日期') || col.includes('id') || col.includes('user') || col.includes('hour') || col.includes('小时')) {
                xIdx = i;
                break;
            }
        }
        
        // Find first numeric column for Y (amount, count, sum)
        for (let i = 0; i < columns.length; i++) {
            if (i === xIdx) continue;
            const col = columns[i].toLowerCase();
            if (col.includes('额') || col.includes('数量') || col.includes('次数') || col.includes('count') || col.includes('sum') || col.includes('usd') || col.includes('avg')) {
                yIdx = i;
                break;
            }
        }

        // Select dropdown elements
        elements.chartXSelect.selectedIndex = xIdx;
        elements.chartYSelect.selectedIndex = yIdx;
        
        // Pick best chart type
        let chartType = 'bar';
        const xCol = columns[xIdx].toLowerCase();
        if (xCol.includes('时间') || xCol.includes('日期') || xCol.includes('小时')) {
            chartType = 'line';
        }
        
        setSelectedValue(elements.chartTypeSelect, chartType);
        
        // Render chart
        renderChart(chartType, columns[xIdx], columns[yIdx], `AI 分析: ${columns[xIdx]} 与 ${columns[yIdx]} 趋势图`);
    }

    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // --- Query Execution ---

    async function executeQuery() {
        const query = elements.sqlEditor.value.trim();
        if (!query) {
            showError('请输入要执行的 SQL 语句。');
            return;
        }

        hideError();
        renderTableLoading();
        
        const startTime = performance.now();
        
        try {
            const res = await fetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.error || 'Query failed');
            }
            
            const endTime = performance.now();
            const elapsed = ((endTime - startTime) / 1000).toFixed(3);
            
            appState.queryResult = {
                columns: data.columns || [],
                rows: data.rows || []
            };
            appState.filteredRows = [...appState.queryResult.rows];
            appState.currentPage = 1;
            appState.sortColumn = null;
            
            elements.resultsMeta.innerHTML = `查找到 ${appState.filteredRows.length} 条数据 (耗时 ${elapsed} 秒)`;
            elements.tableSearch.value = '';
            
            renderResultView();
            updateChartAxisDropdowns();
            autoConfigureChartForPreset();
            
        } catch (err) {
            showError(err.message);
            renderTableError(err.message);
        }
    }

    // --- Tab Controller ---

    function switchTab(tabId) {
        elements.tabBtns.forEach(btn => {
            if (btn.getAttribute('data-tab') === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        elements.tabContents.forEach(content => {
            if (content.id === tabId) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });

        if (tabId === 'tab-chart' && appState.chartInstance) {
            setTimeout(() => {
                appState.chartInstance.resize();
            }, 50);
        }
    }

    // --- Table Ingestion and UI Rendering ---

    function renderTableLoading() {
        elements.tableWrapper.innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>查询执行中，请稍候...</p>
            </div>
        `;
        elements.resultsMeta.innerHTML = '正在加载数据...';
    }

    function renderTableError(msg) {
        elements.tableWrapper.innerHTML = `
            <div class="empty-state" style="color:var(--danger)">
                <span class="empty-icon">❌</span>
                <p>查询执行失败: ${msg}</p>
            </div>
        `;
        elements.resultsMeta.innerHTML = '执行出错';
    }

    function renderResultView() {
        const { columns, rows } = appState.queryResult;
        
        if (columns.length === 0) {
            elements.tableWrapper.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">✓</span>
                    <p>命令已成功执行（无返回行）。</p>
                </div>
            `;
            return;
        }

        if (appState.activePresetId === 'overview' && columns.length >= 4) {
            renderOverviewCards();
            return;
        }

        renderDataTable();
    }

    function renderOverviewCards() {
        const cols = appState.queryResult.columns;
        const row = appState.queryResult.rows[0];
        
        if (!row) {
            renderDataTable();
            return;
        }

        let cardsHtml = '<div class="summary-cards-container">';
        cols.forEach((colName, index) => {
            const val = row[index];
            const displayVal = typeof val === 'number' ? val.toLocaleString() : val;
            cardsHtml += `
                <div class="summary-card glass-panel">
                    <div class="summary-card-val">${displayVal}</div>
                    <div class="summary-card-label">${colName}</div>
                </div>
            `;
        });
        cardsHtml += '</div>';

        elements.tableWrapper.innerHTML = cardsHtml;
        elements.paginationInfo.innerHTML = '概览大屏模式';
    }

    function renderDataTable() {
        const startIdx = (appState.currentPage - 1) * appState.pageSize;
        const endIdx = startIdx + appState.pageSize;
        const pageRows = appState.filteredRows.slice(startIdx, endIdx);
        const { columns } = appState.queryResult;

        if (appState.filteredRows.length === 0) {
            elements.tableWrapper.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🔍</span>
                    <p>没有找到匹配的记录</p>
                </div>
            `;
            updatePaginationControls(0);
            return;
        }

        let tableHtml = '<table class="query-table">';
        
        // Header
        tableHtml += '<thead><tr>';
        columns.forEach((col, index) => {
            let sortIcon = '<i class="fas fa-sort"></i>';
            if (appState.sortColumn === index) {
                sortIcon = appState.sortDirection === 'asc' 
                    ? '<i class="fas fa-sort-up" style="color:var(--primary-light)"></i>' 
                    : '<i class="fas fa-sort-down" style="color:var(--primary-light)"></i>';
            }
            tableHtml += `<th class="th-sort" data-col="${index}">${col} ${sortIcon}</th>`;
        });
        tableHtml += '</tr></thead>';

        // Body
        tableHtml += '<tbody>';
        pageRows.forEach(row => {
            tableHtml += '<tr>';
            row.forEach(cell => {
                let cellDisplay = cell;
                if (cell === null || cell === undefined) {
                    cellDisplay = '<span style="color:var(--text-dim);font-style:italic">null</span>';
                } else if (typeof cell === 'boolean') {
                    cellDisplay = cell ? '是' : '否';
                }
                tableHtml += `<td title="${String(cell || '')}">${cellDisplay}</td>`;
            });
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table>';

        elements.tableWrapper.innerHTML = tableHtml;
        
        document.querySelectorAll('.query-table th').forEach(th => {
            th.addEventListener('click', () => {
                const colIdx = parseInt(th.getAttribute('data-col'), 10);
                sortTable(colIdx);
            });
        });

        updatePaginationControls(appState.filteredRows.length);
    }

    function updatePaginationControls(totalRows) {
        const totalPages = Math.ceil(totalRows / appState.pageSize) || 1;
        const startIdx = totalRows === 0 ? 0 : (appState.currentPage - 1) * appState.pageSize + 1;
        const endIdx = Math.min(appState.currentPage * appState.pageSize, totalRows);

        let paginationHtml = `显示第 ${startIdx} - ${endIdx} 条，共 ${totalRows} 条数据`;
        
        if (totalPages > 1) {
            paginationHtml += `
                <div class="pagination-controls">
                    <button class="page-btn" id="btn-prev-page" ${appState.currentPage === 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>
                    <span style="font-size: 11px; align-self: center; margin: 0 4px;">${appState.currentPage} / ${totalPages}</span>
                    <button class="page-btn" id="btn-next-page" ${appState.currentPage === totalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>
                </div>
            `;
        }

        elements.paginationInfo.innerHTML = paginationHtml;

        const btnPrev = document.getElementById('btn-prev-page');
        const btnNext = document.getElementById('btn-next-page');
        if (btnPrev) btnPrev.addEventListener('click', () => changePage(-1));
        if (btnNext) btnNext.addEventListener('click', () => changePage(1));
    }

    // --- Rest of sorting, pagination & ECharts helper methods ---

    function changePage(direction) {
        appState.currentPage += direction;
        renderDataTable();
    }

    function handleTableSearch() {
        const query = elements.tableSearch.value.trim().toLowerCase();
        
        if (!query) {
            appState.filteredRows = [...appState.queryResult.rows];
        } else {
            appState.filteredRows = appState.queryResult.rows.filter(row => {
                return row.some(cell => String(cell || '').toLowerCase().includes(query));
            });
        }
        
        appState.currentPage = 1;
        renderDataTable();
    }

    function sortTable(colIdx) {
        if (appState.sortColumn === colIdx) {
            appState.sortDirection = appState.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            appState.sortColumn = colIdx;
            appState.sortDirection = 'asc';
        }

        const isAsc = appState.sortDirection === 'asc';
        
        appState.filteredRows.sort((a, b) => {
            const valA = a[colIdx];
            const valB = b[colIdx];

            if (valA === null || valA === undefined) return isAsc ? 1 : -1;
            if (valB === null || valB === undefined) return isAsc ? -1 : 1;

            if (typeof valA === 'number' && typeof valB === 'number') {
                return isAsc ? valA - valB : valB - valA;
            }

            const strA = String(valA);
            const strB = String(valB);
            return isAsc ? strA.localeCompare(strB) : strB.localeCompare(strA);
        });

        appState.currentPage = 1;
        renderDataTable();
    }

    function initChart() {
        if (!elements.chartContainer) return;
        
        appState.chartInstance = echarts.init(elements.chartContainer, 'dark');
        
        window.addEventListener('resize', () => {
            if (appState.chartInstance) appState.chartInstance.resize();
        });
    }

    function updateChartAxisDropdowns() {
        const columns = appState.queryResult.columns;
        
        elements.chartXSelect.innerHTML = '';
        elements.chartYSelect.innerHTML = '';
        
        if (columns.length === 0) return;
        
        columns.forEach(col => {
            const optX = document.createElement('option');
            optX.value = col;
            optX.textContent = col;
            elements.chartXSelect.appendChild(optX);
            
            const optY = document.createElement('option');
            optY.value = col;
            optY.textContent = col;
            elements.chartYSelect.appendChild(optY);
        });

        if (columns.length >= 2) {
            elements.chartYSelect.selectedIndex = 1;
        }
    }

    function autoConfigureChartForPreset() {
        if (!appState.activePresetId) return;
        
        const preset = appState.presets.find(p => p.id === appState.activePresetId);
        if (!preset || !preset.chart_config || preset.chart_config.type === 'card') {
            elements.chartEmptyState.style.display = 'flex';
            return;
        }

        const config = preset.chart_config;
        
        setSelectedValue(elements.chartTypeSelect, config.type === 'bar_line' ? 'bar' : config.type);
        setSelectedValue(elements.chartXSelect, config.xAxis);
        
        if (Array.isArray(config.yAxis)) {
            setSelectedValue(elements.chartYSelect, config.yAxis[0]);
        } else {
            setSelectedValue(elements.chartYSelect, config.yAxis);
        }
        
        renderChart(config.type, config.xAxis, config.yAxis, config.title);
    }

    function setSelectedValue(selectEl, val) {
        for (let i = 0; i < selectEl.options.length; i++) {
            if (selectEl.options[i].value === val) {
                selectEl.selectedIndex = i;
                break;
            }
        }
    }

    function renderCustomChart() {
        const chartType = elements.chartTypeSelect.value;
        const xField = elements.chartXSelect.value;
        const yField = elements.chartYSelect.value;
        
        if (!xField || !yField) {
            showError('生成图表需要同时指定 X 轴和 Y 轴字段。');
            return;
        }
        
        renderChart(chartType, xField, yField, `${xField} 与 ${yField} 关系图表`);
    }

    function renderChart(type, xField, yField, title) {
        if (!appState.chartInstance) return;

        const columns = appState.queryResult.columns;
        const rows = appState.queryResult.rows;

        if (rows.length === 0) {
            elements.chartEmptyState.style.display = 'flex';
            return;
        }

        const xIdx = columns.indexOf(xField);
        const yFields = Array.isArray(yField) ? yField : [yField];
        const yIndices = yFields.map(f => columns.indexOf(f));

        if (xIdx === -1 || yIndices.some(idx => idx === -1)) {
            elements.chartEmptyState.style.display = 'flex';
            return;
        }

        elements.chartEmptyState.style.display = 'none';
        const xData = rows.map(r => r[xIdx]);

        let option = {
            title: {
                text: title,
                left: 'center',
                textStyle: { fontFamily: 'var(--font-outfit)', fontSize: 13, fontWeight: 500 }
            },
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 16, 22, 0.9)',
                borderColor: 'rgba(255,255,255,0.1)',
                textStyle: { color: '#f3f4f6', fontFamily: 'var(--font-outfit)', fontSize: 11 }
            },
            grid: { top: 60, bottom: 50, left: 60, right: 40 },
            legend: {
                data: yFields,
                top: 30,
                textStyle: { fontFamily: 'var(--font-outfit)', fontSize: 10 }
            },
            xAxis: {
                type: 'category',
                data: xData,
                axisLabel: { fontFamily: 'var(--font-outfit)', fontSize: 9 }
            },
            yAxis: {
                type: 'value',
                axisLabel: { fontFamily: 'var(--font-outfit)', fontSize: 9 },
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
            },
            series: []
        };

        if (type === 'pie') {
            const pieData = rows.map(r => ({
                name: String(r[xIdx]),
                value: r[yIndices[0]]
            }));

            option = {
                title: option.title,
                tooltip: { trigger: 'item', formatter: '{a} <br/>{b} : {c} ({d}%)' },
                legend: {
                    type: 'scroll',
                    orient: 'vertical',
                    right: 10,
                    top: 20,
                    bottom: 20,
                    textStyle: { fontFamily: 'var(--font-outfit)', fontSize: 10 }
                },
                series: [
                    {
                        name: yFields[0],
                        type: 'pie',
                        radius: ['40%', '70%'],
                        center: ['40%', '50%'],
                        avoidLabelOverlap: false,
                        itemStyle: { borderRadius: 8, borderColor: '#11121b', borderWidth: 2 },
                        label: { show: false },
                        emphasis: { label: { show: true, fontSize: 12, fontWeight: 'bold' } },
                        data: pieData
                    }
                ]
            };
        } else if (type === 'scatter') {
            const scatterData = rows.map(r => [r[xIdx], r[yIndices[0]]]);
            option.xAxis = { 
                type: typeof xData[0] === 'number' ? 'value' : 'category',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
            };
            option.series = [
                {
                    name: yFields[0],
                    type: 'scatter',
                    symbolSize: 10,
                    itemStyle: { color: 'var(--primary-light)' },
                    data: scatterData
                }
            ];
        } else if (type === 'bar_line') {
            option.yAxis = [
                { type: 'value', name: yFields[0], splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
                { type: 'value', name: yFields[1] || '', splitLine: { show: false } }
            ];
            option.series = [
                {
                    name: yFields[0],
                    type: 'bar',
                    itemStyle: { color: 'rgba(99, 102, 241, 0.7)', borderRadius: [4, 4, 0, 0] },
                    data: rows.map(r => r[yIndices[0]])
                },
                {
                    name: yFields[1],
                    type: 'line',
                    yAxisIndex: 1,
                    smooth: true,
                    itemStyle: { color: 'var(--success)' },
                    data: rows.map(r => r[yIndices[1]])
                }
            ];
        } else {
            yIndices.forEach((yIdx, index) => {
                const fName = yFields[index];
                option.series.push({
                    name: fName,
                    type: type,
                    smooth: type === 'line',
                    itemStyle: type === 'bar' 
                        ? { color: 'rgba(99, 102, 241, 0.7)', borderRadius: [4, 4, 0, 0] }
                        : { color: 'var(--primary-light)' },
                    areaStyle: type === 'line' ? {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(99, 102, 241, 0.3)' },
                            { offset: 1, color: 'rgba(99, 102, 241, 0)' }
                        ])
                    } : undefined,
                    data: rows.map(r => r[yIdx])
                });
            });
        }

        appState.chartInstance.setOption(option, true);
    }

    function showError(msg) {
        elements.errorMessage.textContent = msg;
        elements.errorToast.classList.add('show');
        setTimeout(hideError, 8000);
    }

    function hideError() {
        elements.errorToast.classList.remove('show');
    }
});
