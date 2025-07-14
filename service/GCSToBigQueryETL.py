import json
import os
import re
import io
from datetime import datetime
from google.cloud import storage
from google.cloud import bigquery
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GCSToBigQueryETL:
    def __init__(self,
                 project_id="adept-turbine-339912",
                 bucket_name="adept-turbine-339912-rent-data-lake",
                 dataset_id="Cathay_Bank_Demo",
                 table_id="591_rentdata",
                 credential_path="../cred/iac_sa.json"):

        # 設定憑證
        self.credential_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), credential_path)

        # 初始化客戶端
        self.storage_client = storage.Client.from_service_account_json(self.credential_path)
        self.bq_client = bigquery.Client.from_service_account_json(self.credential_path)

        # 設定參數
        self.project_id = project_id
        self.bucket_name = bucket_name
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.table_ref = f"{project_id}.{dataset_id}.{table_id}"

    def get_latest_json_file(self):
        """獲取 GCS 中最新的 JSON 檔案"""
        bucket = self.storage_client.bucket(self.bucket_name)

        # 列出所有符合格式的檔案
        blobs = list(bucket.list_blobs(prefix="raw_data/rent591/"))

        # 篩選出 JSON 檔案並按時間排序
        json_files = []
        for blob in blobs:
            if blob.name.endswith('.json'):
                # 提取檔案名稱中的時間戳
                filename = blob.name.split('/')[-1]
                match = re.match(r'(\d{8})_(\d{4})_rent_data\.json', filename)
                if match:
                    date_str = match.group(1)
                    time_str = match.group(2)
                    # 轉換為 datetime 物件
                    file_datetime = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
                    json_files.append((blob, file_datetime, filename))

        if not json_files:
            logger.error("未找到符合格式的 JSON 檔案")
            return None

        # 按時間排序，取最新的
        latest_file = sorted(json_files, key=lambda x: x[1], reverse=True)[0]
        logger.info(f"找到最新檔案: {latest_file[2]} (時間: {latest_file[1]})")

        return latest_file[0]

    def download_and_parse_json(self, blob):
        """下載並解析 JSON 檔案"""
        try:
            content = blob.download_as_text(encoding='utf-8')
            data = json.loads(content)
            logger.info(f"成功解析 JSON 檔案，共 {len(data)} 筆資料")
            return data
        except Exception as e:
            logger.error(f"解析 JSON 檔案失敗: {e}")
            return None

    def transform_data(self, raw_data):
        """轉換資料格式"""
        transformed_data = []

        for item in raw_data:
            try:
                # 提取 house_id（URL 最後的數字，忽略查詢參數）
                url = item.get('url', '')
                # 修正正則表達式：提取 URL 路徑中的數字，忽略 ? 後的查詢參數
                house_id_match = re.search(r'/(\d+)(?:\?|$)', url)
                house_id = int(house_id_match.group(1)) if house_id_match else None

                if house_id is None:
                    logger.warning(f"無法提取 house_id，跳過此筆資料: {url}")
                    continue

                # 轉換 poster_type
                identity = item.get('身份', '')
                if identity == '仲介':
                    poster_type = 1
                elif identity == '房東' or identity == '屋主':
                    poster_type = 0
                else:
                    poster_type = None

                # 轉換時間格式
                time_str = item.get('時間', '')
                try:
                    created_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                except:
                    created_time = datetime.now()

                # 組裝轉換後的資料
                transformed_item = {
                    'house_id': house_id,
                    'title': item.get('標題', ''),
                    'url': url,
                    'poster_type': poster_type,
                    'contact_name': item.get('姓名', ''),
                    'house_type': item.get('型態', ''),
                    'room_layout': item.get('屋子配置', ''),
                    'description': item.get('屋況說明', ''),
                    'phone_number': item.get('手機', ''),
                    'predict_price': None,  # 先設為 NULL
                    'created_time': created_time.isoformat()  # 轉換為 ISO 字串格式
                }

                transformed_data.append(transformed_item)

            except Exception as e:
                logger.error(f"轉換資料失敗: {e}, 原始資料: {item}")
                continue

        logger.info(f"成功轉換 {len(transformed_data)} 筆資料")
        return transformed_data

    def deduplicate_data(self, data):
        """去除重複資料，保留最新的記錄"""
        if not data:
            return data

        # 建立字典來存儲每個 house_id 的最新記錄
        unique_data = {}

        for item in data:
            house_id = item['house_id']
            created_time = datetime.fromisoformat(item['created_time'])

            # 如果這個 house_id 還沒有記錄，或者當前記錄更新，則保留
            if house_id not in unique_data or created_time > datetime.fromisoformat(
                    unique_data[house_id]['created_time']):
                unique_data[house_id] = item

        # 轉換回列表
        deduplicated_data = list(unique_data.values())

        original_count = len(data)
        final_count = len(deduplicated_data)
        duplicate_count = original_count - final_count

        if duplicate_count > 0:
            logger.info(f"發現並移除 {duplicate_count} 筆重複資料")
            logger.info(f"原始資料: {original_count} 筆，去重後: {final_count} 筆")

        return deduplicated_data

    def load_to_bigquery(self, data):
        """載入資料到 BigQuery（使用 MERGE 策略）"""
        if not data:
            logger.warning("沒有資料可載入")
            return False

        try:
            # 在載入前先去除重複資料
            deduplicated_data = self.deduplicate_data(data)
            return self.upsert_to_bigquery(deduplicated_data)

        except Exception as e:
            logger.error(f"載入 BigQuery 失敗: {e}")
            return False

    def upsert_to_bigquery(self, data):
        """使用 MERGE 語法進行 UPSERT"""
        try:
            # 建立臨時表名稱
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_table_id = f"temp_rent_data_{timestamp}"
            temp_dataset_ref = self.bq_client.dataset(self.dataset_id)
            temp_table_ref = temp_dataset_ref.table(temp_table_id)

            logger.info(f"建立臨時表: {temp_table_id}")

            # 定義臨時表 schema（與主表相同）
            schema = [
                bigquery.SchemaField("house_id", "INTEGER", mode="REQUIRED"),
                bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("poster_type", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("contact_name", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("house_type", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("room_layout", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("phone_number", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("predict_price", "INTEGER", mode="NULLABLE"),
                bigquery.SchemaField("created_time", "TIMESTAMP", mode="NULLABLE"),
            ]

            # 建立臨時表
            temp_table = bigquery.Table(temp_table_ref, schema=schema)
            temp_table = self.bq_client.create_table(temp_table)
            logger.info(f"臨時表建立成功: {temp_table_id}")

            # 載入資料到臨時表
            job_config = bigquery.LoadJobConfig(
                schema=schema,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            )

            # 將資料轉換為 NDJSON 格式
            ndjson_data = "\n".join([json.dumps(row) for row in data])

            load_job = self.bq_client.load_table_from_file(
                io.StringIO(ndjson_data),
                temp_table_ref,
                job_config=job_config
            )

            load_job.result()  # 等待載入完成
            logger.info(f"資料載入臨時表完成，共 {len(data)} 筆")

            # 使用 CTE 在 MERGE 之前再次確保來源資料的唯一性
            merge_query = f"""
            MERGE `{self.table_ref}` AS target
            USING (
                SELECT * FROM (
                    SELECT *,
                           ROW_NUMBER() OVER (
                               PARTITION BY house_id 
                               ORDER BY created_time DESC
                           ) as rn
                    FROM `{self.project_id}.{self.dataset_id}.{temp_table_id}`
                )
                WHERE rn = 1
            ) AS source
            ON target.house_id = source.house_id

            WHEN MATCHED THEN
              UPDATE SET
                title = source.title,
                url = source.url,
                poster_type = source.poster_type,
                contact_name = source.contact_name,
                house_type = source.house_type,
                room_layout = source.room_layout,
                description = source.description,
                phone_number = source.phone_number,
                predict_price = source.predict_price,
                created_time = CASE 
                    WHEN source.created_time > target.created_time 
                    THEN source.created_time 
                    ELSE target.created_time 
                END

            WHEN NOT MATCHED THEN
              INSERT (house_id, title, url, poster_type, contact_name, house_type, 
                      room_layout, description, phone_number, predict_price, created_time)
              VALUES (source.house_id, source.title, source.url, source.poster_type,
                      source.contact_name, source.house_type, source.room_layout,
                      source.description, source.phone_number, source.predict_price,
                      source.created_time)
            """

            logger.info("開始執行 MERGE 操作...")
            merge_job = self.bq_client.query(merge_query)
            merge_result = merge_job.result()

            # 取得 MERGE 統計資訊
            num_dml_affected_rows = merge_job.num_dml_affected_rows
            logger.info(f"MERGE 完成，影響 {num_dml_affected_rows} 筆記錄")

            # 刪除臨時表
            self.bq_client.delete_table(temp_table_ref)
            logger.info(f"臨時表 {temp_table_id} 已刪除")

            logger.info(f"成功 UPSERT {len(data)} 筆資料到 BigQuery")
            return True

        except Exception as e:
            logger.error(f"UPSERT 操作失敗: {e}")
            # 清理臨時表（如果存在）
            try:
                self.bq_client.delete_table(temp_table_ref)
                logger.info("已清理臨時表")
            except:
                pass
            return False

    def run_etl(self):
        """執行完整的 ETL 流程"""
        logger.info("開始執行 ETL 流程")

        # Step 1: 獲取最新檔案
        latest_blob = self.get_latest_json_file()
        if not latest_blob:
            return False

        # Step 2: 下載並解析
        raw_data = self.download_and_parse_json(latest_blob)
        if not raw_data:
            return False

        # Step 3: 轉換資料
        transformed_data = self.transform_data(raw_data)
        if not transformed_data:
            return False

        # Step 4: 載入 BigQuery
        success = self.load_to_bigquery(transformed_data)

        if success:
            logger.info("ETL 流程執行完成！")
            logger.info(f"處理檔案: {latest_blob.name}")
            logger.info(f"載入資料筆數: {len(transformed_data)}")
        else:
            logger.error("ETL 流程執行失敗")

        return success

    def check_data_quality(self):
        """檢查資料品質（避免查詢機敏欄位）"""
        query = f"""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT house_id) as unique_houses,
            COUNT(CASE WHEN title IS NULL OR title = '' THEN 1 END) as missing_title,
            COUNT(CASE WHEN poster_type IS NULL THEN 1 END) as missing_poster_type,
            COUNT(CASE WHEN house_type IS NULL OR house_type = '' THEN 1 END) as missing_house_type,
            MAX(created_time) as latest_record,
            MIN(created_time) as oldest_record
        FROM `{self.table_ref}`
        """

        try:
            query_job = self.bq_client.query(query)
            results = query_job.result()

            for row in results:
                logger.info("=== 資料品質報告 ===")
                logger.info(f"總記錄數: {row.total_records}")
                logger.info(f"唯一房屋數: {row.unique_houses}")
                logger.info(f"缺少標題: {row.missing_title}")
                logger.info(f"缺少發布者類型: {row.missing_poster_type}")
                logger.info(f"缺少房屋類型: {row.missing_house_type}")
                logger.info(f"最新記錄時間: {row.latest_record}")
                logger.info(f"最舊記錄時間: {row.oldest_record}")

        except Exception as e:
            logger.error(f"品質檢查失敗: {e}")


# if __name__ == "__main__":
#     # 執行 ETL
#     etl = GCSToBigQueryETL()
#
#     # 執行 ETL 流程
#     success = etl.run_etl()
#
#     if success:
#         # 檢查資料品質
#         etl.check_data_quality()
#
#         # 顯示一些範例資料（不包含機敏欄位）
#         sample_query = f"""
#         SELECT house_id, title, poster_type, house_type, created_time
#         FROM `{etl.table_ref}`
#         ORDER BY created_time DESC
#         LIMIT 5
#         """
#
#         try:
#             query_job = etl.bq_client.query(sample_query)
#             results = query_job.result()
#
#             print("\n=== 最新 5 筆資料 ===")
#             for row in results:
#                 print(f"ID: {row.house_id}, 標題: {row.title[:30]}..., 類型: {row.poster_type}, 房型: {row.house_type}")
#
#         except Exception as e:
#             logger.error(f"查詢範例資料失敗: {e}")