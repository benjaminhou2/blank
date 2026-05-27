# /// script
# dependencies = [
#     "flask",
#     "duckdb",
#     "python-dotenv",
#     "requests",
# ]
# ///

import os
import json
import requests
import duckdb
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

# Load local .env file
load_dotenv()

app = Flask(__name__, static_folder='publish', static_url_path='')

DB_NAME = 'livestream.db'
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

def get_db():
    return duckdb.connect(database=DB_NAME, read_only=True)

@app.route('/')
def index():
    return send_from_directory('publish', 'index.html')

@app.route('/api/schema', methods=['GET'])
def get_schema():
    try:
        db = get_db()
        tables_res = db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
        tables = [t[0] for t in tables_res]
        
        schema = {}
        for table in tables:
            cols_res = db.execute(f"PRAGMA table_info('{table}')").fetchall()
            schema[table] = [
                {"name": col[1], "type": col[2]}
                for col in cols_res
            ]
        db.close()
        return jsonify(schema)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/query', methods=['POST'])
def run_query():
    data = request.json or {}
    query_str = data.get('query', '').strip()
    
    if not query_str:
        return jsonify({"error": "Empty query"}), 400
        
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(query_str)
        
        description = cursor.description
        if description is None:
            db.close()
            return jsonify({"columns": [], "rows": [], "message": "Query executed successfully."})
            
        columns = [desc[0] for desc in description]
        rows = cursor.fetchall()
        
        db.close()
        return jsonify({
            "columns": columns,
            "rows": rows
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/presets', methods=['GET'])
def get_presets():
    presets = [
        {
            "id": "overview",
            "name": "📊 全局概览统计 (Overview Summary)",
            "description": "获取直播间数量、打赏金额、弹幕评论总数和总打赏人次等核心指标。",
            "sql": "-- 全局概览统计\nSELECT \n    (SELECT count(*) FROM rooms) AS \"直播间总数\",\n    (SELECT count(DISTINCT 用户ID) FROM comments) AS \"互动用户总数\",\n    (SELECT count(*) FROM comments) AS \"发言弹幕总数\",\n    (SELECT count(*) FROM gifts) AS \"送礼打赏次数\",\n    (SELECT round(sum(打赏金额_USD), 2) FROM gifts) AS \"打赏总金额(USD)\";",
            "chart_config": {
                "type": "card"
            }
        },
        {
            "id": "top_spenders",
            "name": "💰 土豪打赏排行榜 Top 10 (Top Spenders)",
            "description": "按打赏总金额降序排列，列出前 10 名打赏金额最高的用户及其打赏次数。",
            "sql": "-- 土豪打赏排行榜 Top 10\nSELECT \n    用户ID,\n    round(sum(打赏金额_USD), 2) AS \"打赏总额(USD)\",\n    count(*) AS \"打赏次数\",\n    round(avg(打赏金额_USD), 2) AS \"单笔均价(USD)\"\nFROM gifts\nGROUP BY 用户ID\nORDER BY \"打赏总额(USD)\" DESC\nLIMIT 10;",
            "chart_config": {
                "type": "bar",
                "xAxis": "用户ID",
                "yAxis": "打赏总额(USD)",
                "title": "土豪打赏排行榜 Top 10"
            }
        },
        {
            "id": "room_revenue",
            "name": "🎟️ 单场直播收入与弹幕排行 (Room Revenue vs Comments)",
            "description": "查询每场直播的开始时间、打赏总金额与发言总人数，并按收入进行排序。",
            "sql": "-- 单场直播收入与弹幕排行\nSELECT \n    r.直播ID,\n    r.直播开始时间 AS \"开始时间\",\n    (SELECT round(sum(g.打赏金额_USD), 2) FROM gifts g WHERE g.直播ID = r.直播ID) AS \"打赏总额(USD)\",\n    (SELECT count(*) FROM comments c WHERE c.直播ID = r.直播ID) AS \"弹幕数量\",\n    (SELECT count(DISTINCT c.用户ID) FROM comments c WHERE c.直播ID = r.直播ID) AS \"发言人数\"\nFROM rooms r\nORDER BY \"打赏总额(USD)\" DESC NULLS LAST;",
            "chart_config": {
                "type": "bar_line",
                "xAxis": "开始时间",
                "yAxis": ["打赏总额(USD)", "弹幕数量"],
                "title": "单场直播打赏金额与弹幕数对比"
            }
        },
        {
            "id": "hourly_activity",
            "name": "🕒 弹幕与打赏随时间（小时）的分布 (Hourly Activity Distribution)",
            "description": "统计一天中 24 小时内每个小时的弹幕发言量和送礼打赏金额，分析用户活跃时间段。",
            "sql": "-- 24小时段活跃度分析\nSELECT \n    hour(发言时间) AS \"小时\",\n    count(*) AS \"弹幕数量\",\n    (SELECT count(*) FROM gifts WHERE hour(打赏行为的时间) = hour(comments.发言时间)) AS \"打赏次数\",\n    (SELECT round(sum(打赏金额_USD), 2) FROM gifts WHERE hour(打赏行为的时间) = hour(comments.发言时间)) AS \"打赏总额(USD)\"\nFROM comments\nGROUP BY \"小时\"\nORDER BY \"小时\";",
            "chart_config": {
                "type": "line",
                "xAxis": "小时",
                "yAxis": "弹幕数量",
                "title": "24小时活跃度趋势图"
            }
        },
        {
            "id": "comment_loyalty",
            "name": "👥 用户忠诚度与发言关联分析 (Interaction Loyalty Analysis)",
            "description": "分析发言用户中，是否关注直播间、是否打赏直播间的用户比例，探究用户转化率。",
            "sql": "-- 用户转化度分析\nSELECT \n    本场是否关注直播间 AS \"是否关注\",\n    本场是否打赏直播间 AS \"是否打赏\",\n    count(DISTINCT 用户ID) AS \"用户数量\",\n    count(*) AS \"发言次数\"\nFROM comments\nGROUP BY 本场是否关注直播间, 本场是否打赏直播间\nORDER BY \"用户数量\" DESC;",
            "chart_config": {
                "type": "pie",
                "nameField": "是否关注",
                "valueField": "用户数量",
                "title": "发言用户关注状态分布"
            }
        }
    ]
    return jsonify(presets)

@app.route('/api/chat', methods=['POST'])
def run_chat_query():
    data = request.json or {}
    user_message = data.get('message', '').strip()
    
    # Read API Key from request header, fallback to environment
    api_key = request.headers.get('X-Deepseek-API-Key', DEEPSEEK_API_KEY)
    
    if not api_key:
        return jsonify({"error": "DeepSeek API Key is missing. Please set it in .env or provide it in the request."}), 401
        
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    system_prompt = """You are a professional DuckDB SQL translation assistant for a livestream database.
Translate the user's natural language question into a SINGLE, executable DuckDB SQL query.

Database Schema:
1. Table 'rooms':
   - 直播ID (BIGINT): Live session identifier.
   - 直播开始时间 (TIMESTAMP): Live stream start time.
   - 直播结束时间 (TIMESTAMP): Live stream end time.
   - start_time (BIGINT): Unix start epoch timestamp.
   - end_time (BIGINT): Unix end epoch timestamp.

2. Table 'gifts':
   - 日期 (DATE): Date of gift tipping.
   - 用户ID (VARCHAR): Tipping user ID.
   - 打赏行为的时间 (TIMESTAMP): Precise tipping timestamp.
   - 打赏金额_USD (DOUBLE): Tip amount in USD.
   - 直播ID (BIGINT)
   - 直播开始时间 (TIMESTAMP)
   - 直播结束时间 (TIMESTAMP)

3. Table 'comments':
   - 日期 (DATE)
   - 用户ID (VARCHAR): Commenting user ID.
   - 进场时间 (TIMESTAMP): Time when user entered.
   - 发言时间 (TIMESTAMP): Time when comment was sent.
   - 发言内容 (VARCHAR): The comment text.
   - 直播ID (BIGINT)
   - 直播开始时间 (TIMESTAMP)
   - 直播结束时间 (TIMESTAMP)
   - 本场是否关注直播间 (VARCHAR): '是' (Yes) or '否' (No).
   - 关注行为的时间 (TIMESTAMP): Timestamp of follow (NULL if not followed).
   - 本场是否打赏直播间 (VARCHAR): '是' (Yes) or '否' (No).
   - 本场打赏金额_USD (DOUBLE): Total tipping amount in this session.

Rules:
1. Output MUST be a valid JSON object containing exactly two keys:
   - "sql": The raw SQL query string (DO NOT wrap in markdown syntax like ```sql...```).
   - "explanation": A brief, user-friendly explanation in Chinese of how the query works and what it computes.
2. Only write a SELECT query. Do not attempt INSERT, UPDATE, or DELETE.
3. Keep column names exactly as defined in Chinese or English.
4. When performing average or sum of amounts, round to 2 decimal places using ROUND(val, 2).
5. Always use JOIN or subqueries correctly when linking tables by '直播ID' or '用户ID'.
6. Do not include markdown code block characters around the JSON output. Just output the JSON.
"""

    try:
        # Call DeepSeek Chat API
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "response_format": {"type": "json_object"},
            "stream": False
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return jsonify({"error": f"DeepSeek API Error: {response.text}"}), response.status_code
            
        res_data = response.json()
        ai_message = res_data['choices'][0]['message']['content'].strip()
        
        # Parse output JSON
        ai_json = json.loads(ai_message)
        generated_sql = ai_json.get('sql', '').strip()
        explanation = ai_json.get('explanation', '').strip()
        
        if not generated_sql:
            return jsonify({"error": "Model failed to generate SQL."}), 500
            
        # Execute the generated SQL on the database
        db = get_db()
        cursor = db.cursor()
        cursor.execute(generated_sql)
        
        description = cursor.description
        columns = [desc[0] for desc in description] if description else []
        rows = cursor.fetchall()
        db.close()
        
        return jsonify({
            "sql": generated_sql,
            "explanation": explanation,
            "columns": columns,
            "rows": rows
        })
        
    except json.JSONDecodeError:
        # Fallback if model didn't output valid JSON
        return jsonify({"error": "Failed to parse model output. Raw response: " + ai_message}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Livestream Analysis server with DeepSeek API on http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
