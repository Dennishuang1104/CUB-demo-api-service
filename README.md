# Cathay Bank 591 Rent Data API Service

## 專案概述

這是一個基於 Flask 的房屋租賃資料查詢 API 服務，整合了 591 房屋網的資料爬取、ETL 處理和 BigQuery 資料倉儲功能。提供完整的房屋搜尋、統計分析和資料管理功能。

### 主要功能

- **🔍 智能搜尋**：支援多條件組合搜尋（房屋類型、價格範圍、發布者類型、關鍵字等）
- **📊 資料統計**：提供完整的市場統計分析，包含價格覆蓋率、發布者分析等
- **🔒 隱私保護**：手機號碼智能遮罩處理，保護個人隱私資訊
- **⚡ 高效能**：Redis 快取機制 + BigQuery 最佳化，提供毫秒級回應
- **🕷️ 自動爬取**：定期從 591 房屋網爬取最新資料
- **🔄 ETL 處理**：資料清洗、去重、標準化處理

## 系統架構

```
CathayBank_Exam/
├── .venv/                  # Python 虛擬環境
├── api/                    # API 應用層
│   ├── app.py             # Flask API 主程式
│   ├── swagger.html       # API 文件界面
│   ├── build.sh           # 建置腳本
│   ├── deploy.sh          # 部署腳本
│   ├── Dockerfile         # 容器化配置
│   └── requirements.txt   # Python 依賴包
├── iac/                    # 基礎設施即代碼 (Infrastructure as Code)
│   ├── bq/                # BigQuery 相關配置
│   ├── gc/                # Google Cloud VM 相關配置
│   └── gcs/               # Google Cloud Storage 相關配置
│       ├── .terraform/    # Terraform 狀態文件
│       ├── main.tf        # Terraform 主配置
│       ├── output.tf      # 輸出配置
│       ├── provider.tf    # Provider 配置
│       ├── terraform.tfstate # Terraform 狀態
│       ├── terraform.tfvars  # Terraform 變數
│       └── variables.tf   # 變數定義
├── service/               # 核心服務層
│   ├── GCSToBigQueryETL.py   # GCS 到 BigQuery ETL 處理
│   └── Rent591Spider.py      # 591 爬蟲程式
├── .gitignore             # Git 忽略檔案
├── main.py                # 🎯 服務主入口 (根目錄)
└── requirements.txt       # Python 根目錄依賴包
```

## 🔄 資料流程

1. **資料爬取**：`service/Rent591Spider.py` 從 591 房屋網爬取租屋資料
2. **資料存儲**：爬取的原始資料儲存至 Google Cloud Storage (GCS)
3. **ETL 處理**：`service/GCSToBigQueryETL.py` 進行資料清洗、去重、標準化
4. **資料入庫**：處理後的資料寫入 BigQuery 資料倉儲
5. **API 服務**：`api/app.py` 提供 RESTful API 供前端查詢使用
6. **快取優化**：Redis 快取熱門查詢結果，提升回應速度

## 快速開始

### 🌐 直接使用線上服務

線上服務地址：`https://rent-api-352693858328.asia-east1.run.app`

**快速測試：**
```bash
# 測試 API 連接
curl "https://rent-api-352693858328.asia-east1.run.app/health"

# 搜尋前 5 筆房屋資料
curl "https://rent-api-352693858328.asia-east1.run.app/api/properties?limit=5"
```

**或直接在瀏覽器中訪問：**
- 📚 [API 文件](https://rent-api-352693858328.asia-east1.run.app/api/docs)
- 🏠 [房屋列表](https://rent-api-352693858328.asia-east1.run.app/api/properties?limit=5)
- 📊 [統計資料](https://rent-api-352693858328.asia-east1.run.app/api/statistics)

### 本地開發環境設置

- Python 3.10+
- Google Cloud Platform 帳戶

**安裝步驟：**

1. **克隆專案**
   ```bash
   git clone <repository-url>
   cd CathayBank_Exam
   ```

2. **設置虛擬環境**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # 或
   .venv\Scripts\activate     # Windows
   ```

3. **安裝依賴**
   ```bash
   cd api
   pip install -r requirements.txt
   ```

4. **設置 GCP 認證**
   ```bash
   # 將 GCP 服務帳戶金鑰放置到 api/cred/ 目錄
   export GOOGLE_APPLICATION_CREDENTIALS=./cred/iac_sa.json
   ```

5. **設置環境變數**
   ```bash
   export PROJECT_ID=your-gcp-project-id
   export DATASET_ID=your-bigquery-dataset
   export TABLE_ID=your-bigquery-table
   export REDIS_URL=redis://localhost:6379  # 選用
   ```

6. **啟動服務**
   ```bash
   python app.py
   ```

### Cloud Run 部署 (推薦)

此專案已成功部署至 Google Cloud Run：

**🌐 線上服務地址：** `https://rent-api-352693858328.asia-east1.run.app`

**部署步驟：**

1. **建置 Docker 映像檔**
   ```bash
   cd api
   source build.sh
   ```

2. **部署到 Cloud Run**
   ```bash
   source deploy.sh
   ```

### 環境變數

| 變數名稱 | 說明 | 預設值 | 必要性 |
|---------|------|--------|--------|
| `PROJECT_ID` | GCP 專案 ID | `adept-turbine-339912` | 必要 |
| `DATASET_ID` | BigQuery 資料集 ID | `Cathay_Bank_Demo` | 必要 |
| `TABLE_ID` | BigQuery 資料表 ID | `591_rentdata` | 必要 |
| `REDIS_URL` | Redis 連接 URL | `redis://localhost:6379` | 選用 |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP 認證檔案路徑 | `./cred/iac_sa.json` | 必要 |
| `DEBUG` | 除錯模式 | `False` | 選用 |
| `PORT` | 服務埠號 | `8080` | 選用 |


## 📝 變更日誌

### v2.0.0 (2025-07-15)
- 新增智能手機號碼遮罩功能
- 優化 BigQuery 查詢效能
- 完善 Swagger API 文件
- 增強錯誤處理機制

### v1.0.0 (2025-07-13)
- 爬蟲和 ETL 管道建立