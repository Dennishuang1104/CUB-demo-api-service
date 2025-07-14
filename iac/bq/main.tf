resource "google_project_service" "bigquery_api" {
  service = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "datacatalog_api" {
  service = "datacatalog.googleapis.com"
  disable_on_destroy = false
}

# 建立資料集
resource "google_bigquery_dataset" "cathay_bank_demo" {
  dataset_id  = "Cathay_Bank_Demo"
  location    = var.region
  description = "國泰銀行 Demo - 591 租屋資料"

  labels = {
    environment = "demo"
    project     = "cathay-bank"
  }

  depends_on = [google_project_service.bigquery_api]
}

# Policy Tag 分類法
resource "google_data_catalog_taxonomy" "pii_taxonomy" {
  display_name  = "PII 資料分類"
  description   = "個人識別資訊分類"
  activated_policy_types = ["FINE_GRAINED_ACCESS_CONTROL"]

  depends_on = [google_project_service.datacatalog_api]
}

# 電話號碼 Policy Tag
resource "google_data_catalog_policy_tag" "phone_tag" {
  taxonomy     = google_data_catalog_taxonomy.pii_taxonomy.id
  display_name = "電話號碼"
  description  = "需要加密的電話號碼欄位"
}

# 主要資料表
resource "google_bigquery_table" "rent_data" {
  dataset_id = google_bigquery_dataset.cathay_bank_demo.dataset_id
  table_id   = "591_rentdata"
  description = "591 租屋資料表"

  schema = jsonencode([
    {
      name = "house_id"
      type = "INTEGER"
      mode = "REQUIRED"
      description = "唯一識別碼"
    },
    {
      name = "title"
      type = "STRING"
      mode = "NULLABLE"
      description = "房屋標題"
    },
    {
      name = "url"
      type = "STRING"
      mode = "NULLABLE"
      description = "網頁連結"
    },
    {
      name = "poster_type"
      type = "INTEGER"
      mode = "NULLABLE"
      description = "貼文者代號 0: 房東, 1:房仲, 2:代理人"
    },
    {
      name = "contact_name"
      type = "STRING"
      mode = "NULLABLE"
      description = "聯絡人姓名"
    },
    {
      name = "house_type"
      type = "STRING"
      mode = "NULLABLE"
      description = "房屋類型"
    },
    {
      name = "room_layout"
      type = "STRING"
      mode = "NULLABLE"
      description = "房間配置"
    },
    {
      name = "description"
      type = "STRING"
      mode = "NULLABLE"
      description = "房屋描述"
    },
    {
      name = "phone_number"
      type = "STRING"
      mode = "NULLABLE"
      description = "聯絡電話"
      policyTags = {
        names = [google_data_catalog_policy_tag.phone_tag.name]
      }
    },
    {
      name = "predict_price"
      type = "INTEGER"
      mode = "NULLABLE"
      description = "預測租金"
    },
    {
      name = "gender_requirement"
      type = "STRING"
      mode = "NULLABLE"
      description = "性別要求"
    },
    {
      name = "created_time"
      type = "TIMESTAMP"
      mode = "NULLABLE"
      description = "建立時間"
    }
  ])

  # 時間分區
  time_partitioning {
    type  = "DAY"
    field = "created_time"
  }

  # 聚集
  clustering = ["house_id"]

  depends_on = [
    google_bigquery_dataset.cathay_bank_demo,
    google_data_catalog_policy_tag.phone_tag
  ]
}
