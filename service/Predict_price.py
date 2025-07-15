import pandas as pd
import re
import aiohttp
import asyncio
import os
import time
import json
from datetime import datetime

# API 設定 - 從環境變數讀取
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("請設定 OPENAI_API_KEY 環境變數")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


# 1. 讀取並處理資料
def process_data():
    # 讀取上一層目錄的 JSON 檔案
    file_path = '../591_rentdata.json'
    df = pd.read_json(file_path)

    # 篩選只要 'url' 和 '屋況說明' 欄位
    df = df[['url', '屋況說明']]

    # 從 url 萃取 house_id
    def extract_house_id(url):
        match = re.search(r'/(\d+)(?:\?|$)', url)
        return int(match.group(1)) if match else None

    df['house_id'] = df['url'].apply(extract_house_id)

    # 刪除原本的 'url' 欄位
    df = df.drop(columns=['url'])

    # 刪除重複資料（依照 'house_id' 與 '屋況說明'）
    df = df.drop_duplicates(subset=['house_id', '屋況說明'])

    return df


# 2. 非同步請求單筆（加強容錯）
async def fetch_prediction(session, house_id, description, max_retries=3):
    prompt = f"""
你是一個租金估算 AI，根據房屋描述輸出預估月租金（數字，單位：元），如果描述不足請回傳 null。
請只回傳整數或 null，不要任何其他文字。
描述：
{description}
""".strip()

    for attempt in range(max_retries):
        try:
            async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=HEADERS,
                    json={
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "你是一個房屋租金預測助手，只回傳數字或 null。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0
                    }
            ) as resp:
                result = await resp.json()

                # 檢查是否遇到速率限制
                if "error" in result:
                    if result["error"].get("code") == "rate_limit_exceeded":
                        wait_time = 2 ** attempt  # 指數退避：2, 4, 8 秒
                        print(
                            f"house_id {house_id} 遇到速率限制，等待 {wait_time} 秒後重試（第 {attempt + 1}/{max_retries} 次）")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"house_id {house_id} API 錯誤: {result['error']}")
                        return None

                # 檢查是否有 choices 欄位
                if "choices" not in result:
                    print(f"house_id {house_id} API 回應格式異常: {result}")
                    return None

                reply = result["choices"][0]["message"]["content"].strip()

                # 驗證回應格式
                if reply.lower() == "null":
                    return None

                # 嘗試轉換為整數
                try:
                    rent_value = int(reply)
                    # 合理性檢查（租金應該在 1000 到 200000 之間）
                    if 1000 <= rent_value <= 200000:
                        return rent_value
                    else:
                        print(f"house_id {house_id} 租金數值異常: {rent_value}，設為 null")
                        return None
                except ValueError:
                    print(f"house_id {house_id} 回應格式錯誤: '{reply}'，重試中...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return None

        except Exception as e:
            print(f"house_id {house_id} 第 {attempt + 1} 次嘗試失敗: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None

    print(f"house_id {house_id} 達到最大重試次數，回傳 null")
    return None


# 3. 主控流程（平衡速度和穩定性）
async def predict_rents(df_batch, concurrency=3):  # 提高到 3 個並發
    results = []
    semaphore = asyncio.Semaphore(concurrency)

    # 設定 SSL 連接器
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        async def sem_task(i, row):
            async with semaphore:
                # 減少延遲時間
                await asyncio.sleep(0.05 * i)
                return await fetch_prediction(session, row['house_id'], row['屋況說明'])

        tasks = [sem_task(i, row) for i, (_, row) in enumerate(df_batch.iterrows())]
        results = await asyncio.gather(*tasks)

    return results


# 4. 主執行程式（加強容錯和進度保存）
def main():
    # 處理資料
    df = process_data()
    print(f"處理後的資料筆數: {len(df)}")

    # 檢查是否有中斷的進度檔案
    progress_file = "progress.json"
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            progress = json.load(f)
        print(f"找到進度檔案，從第 {progress['completed_batches']} 批開始繼續執行")
        start_batch = progress['completed_batches']
        df.loc[df.index < progress['completed_rows'], 'predicted_rent'] = progress['results'][
                                                                          :progress['completed_rows']]
    else:
        start_batch = 0
        df['predicted_rent'] = None

    # 分批處理設定
    batch_size = 50  # 提高批次大小
    total_batches = (len(df) + batch_size - 1) // batch_size

    print(f"總共 {total_batches} 批，每批 {batch_size} 筆")
    print("平衡設定：速度 vs 穩定性，預估時間 60-90 分鐘")
    print("已加強容錯機制：自動重試、進度保存、資料驗證")

    try:
        for batch_idx in range(start_batch, total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(df))
            batch_df = df.iloc[start_idx:end_idx]

            print(
                f"\n處理第 {batch_idx + 1}/{total_batches} 批 (house_id: {batch_df.iloc[0]['house_id']} - {batch_df.iloc[-1]['house_id']})...")
            start_time = time.time()

            # 執行批次預測
            batch_results = asyncio.run(predict_rents(batch_df, concurrency=3))

            # 更新結果
            df.iloc[start_idx:end_idx, df.columns.get_loc('predicted_rent')] = batch_results

            elapsed = time.time() - start_time

            # 計算進度
            completed_rows = end_idx
            progress_pct = completed_rows / len(df) * 100
            avg_time_per_batch = elapsed
            remaining_batches = total_batches - batch_idx - 1
            estimated_remaining = remaining_batches * avg_time_per_batch

            print(f"  完成 {completed_rows}/{len(df)} 筆 ({progress_pct:.1f}%)")
            print(f"  本批耗時 {elapsed:.1f} 秒，預估剩餘時間 {estimated_remaining / 60:.1f} 分鐘")

            # 統計本批結果
            non_null_results = [r for r in batch_results if r is not None]
            print(f"  本批成功預測 {len(non_null_results)}/{len(batch_results)} 筆")
            if non_null_results:
                print(f"  租金範圍: {min(non_null_results):,} - {max(non_null_results):,} 元")

            # 保存進度
            progress = {
                'completed_batches': batch_idx + 1,
                'completed_rows': completed_rows,
                'results': df['predicted_rent'].tolist(),
                'timestamp': datetime.now().isoformat()
            }
            with open(progress_file, 'w') as f:
                json.dump(progress, f)

            # 每 10 批保存一次 CSV 備份
            if (batch_idx + 1) % 10 == 0:
                backup_file = f"rent_predictions_backup_{batch_idx + 1}.csv"
                df.to_csv(backup_file, index=False)
                print(f"  已保存備份: {backup_file}")

            # 批次間等待，避免速率限制
            if batch_idx < total_batches - 1:
                print("  等待 2 秒避免速率限制...")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n程式被中斷，進度已保存，可重新執行繼續處理")
        return df
    except Exception as e:
        print(f"\n\n發生錯誤: {e}")
        print("進度已保存，可重新執行繼續處理")
        return df

    # 完成後清理進度檔案
    if os.path.exists(progress_file):
        os.remove(progress_file)

    # 最終統計
    successful_predictions = df['predicted_rent'].notna().sum()
    print(f"\n完成！成功預測 {successful_predictions}/{len(df)} 筆 ({successful_predictions / len(df) * 100:.1f}%)")

    # 儲存最終結果
    df.to_csv("rent_predictions_final.csv", index=False)
    print("最終結果已儲存至 rent_predictions_final.csv")

    return df


# 執行程式
if __name__ == "__main__":
    result_df = main()
    print(result_df.head())