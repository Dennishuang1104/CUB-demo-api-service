from service.Rent591Spider import Rent591Spider
from service.GCSToBigQueryETL import GCSToBigQueryETL
import json
import os
from datetime import datetime
from google.cloud import storage


def save_to_gcs(data, bucket_name="adept-turbine-339912-rent-data-lake"):
    """精簡版：只上傳 JSON 格式到 GCS，檔案名稱包含小時分鐘"""
    if not data:
        return

    # 設定服務帳戶憑證路徑
    credential_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cred", "iac_sa.json")

    # 初始化 GCS client
    client = storage.Client.from_service_account_json(credential_path)
    bucket = client.bucket(bucket_name)

    # 檔案名稱顆粒度到分鐘：YYYYMMDD_HHMM
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"raw_data/rent591/{timestamp}_rent_data.json"

    blob = bucket.blob(filename)
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type='application/json'
    )

    print(f"✅ 已上傳 {len(data)} 筆資料到: gs://{bucket_name}/{filename}")


if __name__ == "__main__":
    spider = Rent591Spider()
    test_results = spider.scrape_with_session()

    # 上傳到 GCS（只上傳一次）
    save_to_gcs(test_results)

    # 執行資料流
    etl = GCSToBigQueryETL()
    success = etl.run_etl()