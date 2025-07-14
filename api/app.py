import os
from flask import Flask, request, jsonify, redirect
from google.cloud import bigquery
import redis
import json
import hashlib
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": False
    }
})

# 配置
PROJECT_ID = os.getenv('PROJECT_ID', 'adept-turbine-339912')
DATASET_ID = os.getenv('DATASET_ID', 'Cathay_Bank_Demo')
TABLE_ID = os.getenv('TABLE_ID', '591_rentdata')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
CREDENTIAL_PATH = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './cred/iac_sa.json')

# 全域變數
bq_client = None
redis_client = None
_init_lock = threading.Lock()

# 映射表
HOUSE_TYPE_MAPPING = {1: "透天厝", 2: "電梯大樓", 3: "公寓", 4: "別墅", 5: "其他(停車位)"}
POSTER_TYPE_MAPPING = {0: "房東", 1: "房仲", 2: "代理人"}


@app.before_request
def force_https():
    """強制使用 HTTPS（在生產環境中）"""
    if request.headers.get('X-Forwarded-Proto') == 'http':
        return redirect(request.url.replace('http://', 'https://'), code=301)


# 手動添加 CORS headers 作為備用
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'false')
    return response


# 添加 OPTIONS 路由處理預檢請求
@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return '', 200


def get_house_type_id(name):
    return next((id for id, n in HOUSE_TYPE_MAPPING.items() if n == name), None)


def init_clients():
    global bq_client, redis_client
    with _init_lock:
        if bq_client is None:
            bq_client = bigquery.Client.from_service_account_json(CREDENTIAL_PATH, project=PROJECT_ID)
        if redis_client is None and REDIS_URL:
            try:
                redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
                redis_client.ping()
                print("Redis 連接成功")
            except Exception as e:
                print(f"Redis 連接失敗: {e} (API 將在無快取模式下運行)")
                redis_client = None


class RentAPI:
    def __init__(self):
        self.table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        self.cache_ttl = 3600

    def _cache_key(self, operation, params):
        return f"rent_api:{hashlib.md5(json.dumps({'op': operation, 'params': params}, sort_keys=True).encode()).hexdigest()}"

    def _get_cache(self, key):
        try:
            return json.loads(redis_client.get(key)) if redis_client and redis_client.get(key) else None
        except:
            return None

    def _set_cache(self, key, data, ttl=None):
        try:
            if redis_client:
                redis_client.setex(key, ttl or self.cache_ttl, json.dumps(data, default=str))
        except:
            pass

    def normalize_and_mask_phone(self, phone):
        """標準化並遮罩手機號碼"""
        if not phone:
            return None

        import re

        # 移除所有非數字字符
        digits_only = re.sub(r'\D', '', str(phone))

        # 根據號碼長度判斷類型並格式化
        if len(digits_only) == 10:
            # 手機號碼 (09XXXXXXXX)
            if digits_only.startswith('09'):
                return f"09****{digits_only[-3:]}"
            # 市話 (04XXXXXXXX)
            else:
                return f"{digits_only[:2]}****{digits_only[-3:]}"
        elif len(digits_only) == 9:
            # 可能是市話沒有區碼
            return f"{digits_only[:2]}***{digits_only[-2:]}"
        elif len(digits_only) == 8:
            # 一般市話
            return f"{digits_only[:2]}****{digits_only[-2:]}"
        else:
            # 其他長度
            return "***"

    def search_properties(self, filters):
        if not bq_client:
            init_clients()

        cache_key = self._cache_key('search', filters)
        cached = self._get_cache(cache_key)
        if cached:
            return {'data': cached, 'from_cache': True}

        # 建構查詢
        conditions = ["1=1"]
        params = {}

        if filters.get('min_price'):
            conditions.append("predict_price >= @min_price")
            params['min_price'] = int(filters['min_price'])
        if filters.get('max_price'):
            conditions.append("predict_price <= @max_price")
            params['max_price'] = int(filters['max_price'])
        if filters.get('house_type_id'):
            house_type_name = HOUSE_TYPE_MAPPING.get(int(filters['house_type_id']))
            if house_type_name:
                conditions.append("house_type = @house_type")
                params['house_type'] = house_type_name
        if filters.get('poster_type_id') is not None:
            conditions.append("poster_type = @poster_type")
            params['poster_type'] = int(filters['poster_type_id'])
        if filters.get('keyword'):
            conditions.append("(title LIKE @keyword OR description LIKE @keyword)")
            params['keyword'] = f"%{filters['keyword']}%"

        params['limit'] = min(int(filters.get('limit', 20)), 100)
        params['offset'] = int(filters.get('offset', 0))

        query = f"""
        SELECT house_id, title, url, poster_type, contact_name, house_type, 
               room_layout, description, phone_number, predict_price, gender_requirement,created_time
        FROM `{self.table_ref}`
        WHERE {' AND '.join(conditions)}
        ORDER BY created_time DESC
        LIMIT @limit OFFSET @offset
        """

        # 執行查詢
        query_params = [
            bigquery.ScalarQueryParameter(k, "INT64" if isinstance(v, int) else "STRING", v)
            for k, v in params.items()
        ]
        job_config = bigquery.QueryJobConfig(query_parameters=query_params, use_query_cache=True)
        results = bq_client.query(query, job_config=job_config).result()

        # 處理結果
        data = []
        for row in results:
            house_type_id = get_house_type_id(row.house_type)
            data.append({
                'house_id': row.house_id,
                'title': row.title,
                'url': row.url,
                'poster_type_id': row.poster_type,
                'poster_type_name': POSTER_TYPE_MAPPING.get(row.poster_type, '未知'),
                'contact_name': row.contact_name,
                'house_type_id': house_type_id,
                'house_type_name': row.house_type,
                'room_layout': row.room_layout,
                'description': row.description,
                'phone_number': self.normalize_and_mask_phone(row.phone_number),
                'predict_price': row.predict_price,
                'gender_requirement': row.gender_requirement,
                'created_time': row.created_time.isoformat() if row.created_time else None
            })

        self._set_cache(cache_key, data)
        return {'data': data, 'from_cache': False}

    def get_statistics(self):
        if not bq_client:
            init_clients()

        cache_key = self._cache_key('stats', {})
        cached = self._get_cache(cache_key)
        if cached:
            return {'data': cached, 'from_cache': True}

        query = f"""
        SELECT 
            COUNT(*) as total_properties,
            COUNTIF(predict_price IS NOT NULL) as properties_with_price,
            COUNTIF(predict_price IS NULL) as properties_without_price,
            ROUND(COUNTIF(predict_price IS NOT NULL) * 100.0 / COUNT(*), 2) as price_coverage_percentage,
            ROUND(AVG(predict_price), 2) as avg_price_of_priced_properties,
            COUNTIF(poster_type = 0) as owner_posts,
            COUNTIF(poster_type = 1) as agent_posts,
            COUNTIF(poster_type = 2) as proxy_posts
        FROM `{self.table_ref}`
        """

        row = next(bq_client.query(query).result())
        stats = {
            'total_properties': row.total_properties,
            'properties_with_price': row.properties_with_price,
            'properties_without_price': row.properties_without_price,
            'price_coverage_percentage': float(row.price_coverage_percentage or 0),
            'avg_price_of_priced_properties': float(
                row.avg_price_of_priced_properties) if row.avg_price_of_priced_properties else None,
            'owner_posts': row.owner_posts,
            'agent_posts': row.agent_posts,
            'proxy_posts': row.proxy_posts
        }

        self._set_cache(cache_key, stats, ttl=1800)
        return {'data': stats, 'from_cache': False}


rent_api = RentAPI()


@app.route('/api/properties', methods=['GET'])
def search_properties():
    try:
        filters = {k: v for k, v in request.args.items() if v}
        result = rent_api.search_properties(filters)
        return jsonify({
            'success': True,
            'data': result['data'],
            'count': len(result['data']),
            'from_cache': result['from_cache']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    try:
        result = rent_api.get_statistics()
        return jsonify({
            'success': True,
            'data': result['data'],
            'from_cache': result['from_cache']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/house-types', methods=['GET'])
def get_house_types():
    return jsonify({
        'success': True,
        'data': [{'id': id, 'name': name} for id, name in HOUSE_TYPE_MAPPING.items()]
    })


@app.route('/api/poster-types', methods=['GET'])
def get_poster_types():
    return jsonify({
        'success': True,
        'data': [{'id': id, 'name': name} for id, name in POSTER_TYPE_MAPPING.items()]
    })


@app.route('/health', methods=['GET'])
def health_check():
    try:
        if not bq_client:
            init_clients()

        bq_status = "ok" if bq_client else "error"

        # Redis 狀態檢查
        redis_status = "not_configured"
        if redis_client:
            try:
                redis_client.ping()
                redis_status = "ok"
            except:
                redis_status = "error"

        # 只有 BigQuery 是必須的
        overall_status = "healthy" if bq_status == "ok" else "unhealthy"
        status_code = 200 if overall_status == "healthy" else 500

        return jsonify({
            'status': overall_status,
            'services': {
                'bigquery': bq_status,
                'redis': redis_status
            },
            'note': 'Redis is optional for caching. API works without it.'
        }), status_code
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/docs', methods=['GET'])
def api_docs():
    """返回 Swagger UI HTML 頁面"""
    try:
        # 讀取同目錄下的 swagger.html 檔案
        with open('swagger.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({'error': 'API documentation not found'}), 404


@app.route('/api/swagger.json', methods=['GET'])
def swagger_spec():
    """返回 Swagger JSON 規格"""
    # 確保使用 HTTPS
    base_url = request.url_root.replace('http://', 'https://')

    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Cathay Rent Data API",
            "version": "2.0.0",
            "description": "591 房屋租賃資料查詢 API"
        },
        "servers": [{"url": base_url.rstrip('/'), "description": "Production server"}],
        "schemes": ["https"],
        "paths": {
            "/api/properties": {
                "get": {
                    "summary": "搜尋房屋物件",
                    "description": "根據多種條件搜尋房屋物件",
                    "parameters": [
                        {
                            "name": "house_type_id",
                            "in": "query",
                            "description": "房屋類型 ID (1=透天厝, 2=電梯大樓, 3=公寓, 4=別墅, 5=其他)",
                            "schema": {"type": "integer", "enum": [1, 2, 3, 4, 5]}
                        },
                        {
                            "name": "poster_type_id",
                            "in": "query",
                            "description": "發布者類型 ID (0=房東, 1=房仲, 2=代理人)",
                            "schema": {"type": "integer", "enum": [0, 1, 2]}
                        },
                        {
                            "name": "min_price",
                            "in": "query",
                            "description": "最低價格",
                            "schema": {"type": "integer", "example": 15000}
                        },
                        {
                            "name": "max_price",
                            "in": "query",
                            "description": "最高價格",
                            "schema": {"type": "integer", "example": 40000}
                        },
                        {
                            "name": "keyword",
                            "in": "query",
                            "description": "關鍵字搜尋",
                            "schema": {"type": "string", "example": "烏日"}
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "每頁筆數 (最大100)",
                            "schema": {"type": "integer", "default": 20, "maximum": 100, "example": 10}
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "description": "起始位置",
                            "schema": {"type": "integer", "default": 0, "example": 0}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "搜尋成功",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "success": True,
                                        "data": [
                                            {
                                                "house_id": "19288361",
                                                "title": "烏日☘️高鐵特區▫兩房平車▫傢俱可談",
                                                "poster_type_name": "房仲",
                                                "house_type_name": "電梯大樓",
                                                "predict_price": 25000
                                            }
                                        ],
                                        "count": 1,
                                        "from_cache": False
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/statistics": {
                "get": {
                    "summary": "取得統計資料",
                    "description": "取得整體房屋物件統計資料，包含價格覆蓋率分析",
                    "responses": {
                        "200": {
                            "description": "統計資料",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "success": True,
                                        "data": {
                                            "total_properties": 1500,
                                            "properties_with_price": 450,
                                            "price_coverage_percentage": 30.0,
                                            "avg_price_of_priced_properties": 28500.75
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/house-types": {
                "get": {
                    "summary": "取得房屋類型列表",
                    "description": "取得所有房屋類型 ID 和名稱對應表",
                    "responses": {
                        "200": {
                            "description": "房屋類型列表"
                        }
                    }
                }
            },
            "/api/poster-types": {
                "get": {
                    "summary": "取得發布者類型列表",
                    "description": "取得所有發布者類型 ID 和名稱對應表",
                    "responses": {
                        "200": {
                            "description": "發布者類型列表"
                        }
                    }
                }
            },
            "/health": {
                "get": {
                    "summary": "健康檢查",
                    "description": "檢查 API 服務和相關依賴的健康狀態",
                    "responses": {
                        "200": {
                            "description": "服務健康"
                        }
                    }
                }
            }
        }
    }
    return jsonify(spec)


@app.route('/', methods=['GET'])
def root():
    # 確保文件 URL 使用 HTTPS
    doc_url = request.url_root.replace('http://', 'https://') + 'api/docs'

    return jsonify({
        'service': 'Cathay Rent Data API',
        'version': '2.0.0',
        'documentation': doc_url,
        'endpoints': ['/api/properties', '/api/statistics', '/api/house-types', '/api/poster-types', '/health'],
        'house_types': HOUSE_TYPE_MAPPING,
        'poster_types': POSTER_TYPE_MAPPING
    })


if __name__ == '__main__':
    init_clients()
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=os.environ.get('DEBUG', 'False').lower() == 'true', host='0.0.0.0', port=port)