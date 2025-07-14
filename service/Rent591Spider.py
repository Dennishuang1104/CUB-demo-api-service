import requests
from bs4 import BeautifulSoup
from datetime import datetime


class Rent591Spider:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.session = requests.Session()

    def fetch_rent_info(self, url):
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            return {'error': f'請求失敗，狀態碼：{response.status_code}', 'url': url}

        soup = BeautifulSoup(response.text, 'html.parser')
        try:
            landlord_raw = soup.select_one(
                '#__nuxt > section:nth-child(3) > section.main-wrapper > section.aside > section.contact-card > section > div.contact-info > p > span.name'
            )
            landlord_raw = landlord_raw.text.strip() if landlord_raw else '無法取得'
            if ': ' in landlord_raw:
                identity, name = landlord_raw.split(': ', 1)
            else:
                identity, name = '未知', landlord_raw

            house_type = soup.select_one(
                '#__nuxt > section:nth-child(3) > section.main-wrapper > section.main-content > section.block.info-board > div.pattern > span:nth-child(7)'
            )
            house_type = house_type.text.strip() if house_type else '無法取得'

            layout = soup.select_one(
                '#__nuxt > section:nth-child(3) > section.main-wrapper > section.main-content > section.block.info-board > div.pattern > span:nth-child(1)'
            )
            layout = layout.text.strip() if layout else '無法取得'

            desc = soup.select_one(
                '#__nuxt > section:nth-child(3) > section.main-wrapper > section.main-content > section.block.house-condition > div.house-condition-content > div.article'
            )
            desc = desc.text.strip() if desc else '無法取得'

            phone = soup.select_one(
                '#__nuxt > section:nth-child(3) > section.main-wrapper > section.aside > section.contact-card > div > div > button > span:nth-child(2) > span'
            )
            phone = phone.text.strip() if phone else '無法取得'

            return {
                '身份': identity,
                '姓名': name,
                '型態': house_type,
                '屋子配置': layout,
                '屋況說明': desc,
                '手機': phone
            }

        except Exception as e:
            return {'error': f'資料解析錯誤：{e}', 'url': url}

    def scrape_with_session(self, max_pages=None):
        """
        抓取租屋資料

        Args:
            max_pages (int, optional): 最大抓取頁數，None 表示抓取所有頁面

        Returns:
            list: 抓取到的資料列表
        """
        self.session.get('https://rent.591.com.tw/', headers=self.headers, timeout=15)

        results = []
        page = 1

        while True:
            # 檢查是否達到最大頁數限制
            if max_pages is not None and page > max_pages:
                print(f"✅ 已達到設定的最大頁數限制 ({max_pages} 頁)，停止抓取。")
                break

            print(f"📄 正在處理第 {page} 頁...")
            target_url = f'https://rent.591.com.tw/list?region=8&page={page}'
            response = self.session.get(target_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'lxml')

            links = soup.select('a.link.v-middle')
            if not links:
                print(f"✅ 沒有更多資料，第 {page} 頁為最後一頁。")
                break

            print(f"🔎 找到 {len(links)} 筆房屋連結\n")

            for i, a_tag in enumerate(links):
                href = a_tag.get('href')
                if not href.startswith("http"):
                    href = "https:" + href
                url = href
                title = a_tag.text.strip()

                # 抓詳細頁資料
                detail = self.fetch_rent_info(url)

                data = {
                    '標題': title,
                    'url': url,
                    **detail,
                    '時間': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                print(f"第 {len(results) + 1} 筆: {title}")
                results.append(data)

            page += 1

        print(f"\n📊 總共抓取了 {len(results)} 筆資料")
        return results





