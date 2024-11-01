import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import warnings
import time
import random
from pyairtable import Table, Base


# Streamlit 앱 제목과 설명
st.title("아마존 상품 가져오기")
st.write("상품 정보를 추출하여 에어 테이블에 저장하기 위해 아마존 상품 링크를 넣으세요.")

# Amazon URL 입력 받는 텍스트 박스
amazon_input = st.text_input("아마존 상품 URL")

# 에어테이블 API 설정 (필요한 경우 자신의 API 키와 URL로 변경)
AIRTABLE_API_KEY = "YOUR_AIRTABLE_API_KEY"
AIRTABLE_URL = "https://api.airtable.com/v0/app9LqHdsBpu2g0I9/tblJoe6QFIoEye2V1"
HEADERS = {'Authorization': f'Bearer {AIRTABLE_API_KEY}'}

def amazon_crawling(amazon_url):

    def extract_original_image_link(image_link):
        # 이미지 링크에서 '_'로 시작하는 부분부터 마지막 '_'가 나오는 부분까지를 찾아 제거합니다.
        index_start = image_link.find("_")
        index_end = image_link.rfind("_")
        if index_start != -1 and index_end != -1:
            original_image_link = image_link[:index_start-1] + image_link[index_end+1:]
            original_image_link = original_image_link.replace("/images/I/", "/images/I/")
            return original_image_link
        else:
            return None

    options = Options()  # Selenium 옵션 객체 생성

    random_sec = random.uniform(2,4)

    options.add_argument("--disable-blink-features=AutomationControlled") # 자동화 감지 안되게 하는 방법
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("detach", True) # 창 안꺼지게 하는 방법
    options.add_argument("lang=en-US,en")
    options.add_argument("--headless") # 백그라운드에서 셀레니움 실행
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36") # 일반 브라우저로 보이게 하는 방법

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) #셀레니움 최신 버전에서는 자동으로 webdriver 설치 후 반영
    driver.get(amazon_url)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") # 셀레니움 디텍션 스크립트 비활성화
    
    # 이미지와 상세 정보 추출
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'li.a-spacing-small.item.imageThumbnail.a-declarative'))
    )
    sub_images = driver.find_elements(By.CSS_SELECTOR, 'li.a-spacing-small.item.imageThumbnail.a-declarative')
    image_urls = []
    actions = ActionChains(driver)

    i=0

    for img in sub_images:
        actions.move_to_element(img).perform()
        time.sleep(1)  # 마우스를 올린 후 약간 대기
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        hovered_img = soup.select_one(f'li.image.item.itemNo{i}.maintain-height.selected img')
        if hovered_img:
            img_url = hovered_img.get('src')
            if img_url:
                image_urls.append(img_url)
        i+=1

    image_links = []

    # 추출한 오리지널 이미지 URL image_links에 추가
    for url in image_urls:
        original_url = extract_original_image_link(url)
        image_links.append(original_url)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    product_title_element = soup.find("span", id="productTitle")
    product_price_element = soup.select("[class='a-price aok-align-center reinventPricePriceToPayMargin priceToPay'] .a-price-whole")  # CSS 선택자를 사용하여 가격 요소를 찾음

    product_price = None


    if product_title_element:
        product_title = product_title_element.get_text().strip()
        if product_price_element:
            product_price = product_price_element[0].get_text().strip()  # select() 메서드는 리스트 형태로 결과를 반환하므로 첫 번째 요소를 선택해야 함
            st.write("상품 제목:", product_title)
            st.write("상품 가격:", product_price)
        else:
            st.write("상품 가격을 찾을 수 없습니다.")
    else:
        st.write("상품 제목을 찾을 수 없습니다.")


    
    # 상세 설명 크롤링
    ul_element = soup.find('ul', class_='a-unordered-list a-vertical a-spacing-mini')

    texts = []

    # 모든 li 텍스트 추출
    if ul_element:
        items = ul_element.find_all('li')
        for item in items:
            texts.append(item.get_text(strip=True))  # 각 항목의 텍스트를 리스트에 추가
        detail_contents = "\n".join(texts)  # 리스트를 문자열로 결합 (여기서는 줄바꿈으로 구분)
        st.write(detail_contents)  # 결과 출력
    else:
        detail_contents = None
        st.write("상세 설명을 찾을 수 없습니다.")


    # 상세 정보 크롤링
    table = soup.find('table', id='productDetails_techSpec_section_1')

    product_details_list = []  # 결과를 저장할 리스트 초기화

    # 모든 th와 td 텍스트 추출
    if table:
        items = table.find_all('tr')
        
        for item in items:
            th = item.find('th')
            td = item.find('td')
            
            if th and td:
                key = th.get_text(strip=True)
                value = td.get_text(strip=True)
                product_details_list.append(f"{key}: {value}")  # 리스트에 추가

        # 결과 출력
        for detail in product_details_list:
            st.write(detail)
    else:
        st.write("상세 정보를 찾을 수 없습니다.")

    
    



    driver.quit()



    #---------------- 에어테이블 등록 --------------------------------------

    headers = {'Authorization': f'Bearer {"patzjhrtul7b9Odmf.4b0ba9db9d1068d747ef88037e0defd0214fcd40d2264c250bd16345a7935730"}'}
    price_url = 'https://api.airtable.com/v0/app9LqHdsBpu2g0I9/tblJoe6QFIoEye2V1'

    Local_shipping_price = 0
    product_price_num = int(product_price.replace(',', ''))
    image_urls_text = ",".join(image_links)
    # 리스트를 문자열로 변환 (여기서는 줄바꿈으로 구분)
    details_string = "\n".join(product_details_list)

    price_param = {
    "records": [
        {
        "fields": {
            "상품명": product_title,
            "가격": product_price_num,
            "현지 배송비": Local_shipping_price,
            "아마존 Url": amazon_input,
            "이미지 Url": image_urls_text,
            "상세 설명": detail_contents,
            "상세 정보": details_string
        }
        }
    ]
    }


    price_res = requests.post(url=price_url, headers=headers, json=price_param)
    price_res_data = price_res.json()

    if price_res.status_code == 200:
        return f"상품 '{product_title}', 가격 '{product_price}'이 성공적으로 에어테이블에 저장되었습니다."
    else:
        return f"저장에 실패했습니다. Response: {price_res.json()}"

# 실행 버튼
if st.button("정보 추출 및 저장"):
    if amazon_input:
        with st.spinner("정보 추출중..."):
            result_message = amazon_crawling(amazon_input)
            st.success(result_message)
    else:
        st.error("Please enter a valid Amazon URL.")
