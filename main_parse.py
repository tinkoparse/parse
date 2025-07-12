import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

st.set_page_config(page_title="Парсер Tinko", layout="wide")
st.title("🧰 Парсер сайта tinko.ru")


def get_sections() -> dict:
    """Парсит категории с https://www.tinko.ru/catalog/"""
    url = "https://www.tinko.ru/catalog/"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    sections = {}
    links = soup.select("div.section-title a.section-title__link")
    for link in links:
        name = link.get_text(strip=True)
        href = link["href"]
        full_url = "https://www.tinko.ru" + href
        sections[name] = full_url

    return sections


def get_max_pages(section_url: str) -> int:
    """Определяет количество страниц в разделе"""
    debug = {}
    url = section_url + "?count=96&PAGEN_1=1"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    page_links = soup.select("li.pagination__item > div.pagination__link")
    debug["pagination_blocks_found"] = len(page_links)

    page_numbers = []
    for link in page_links:
        text = link.get_text(strip=True)
        if text.isdigit():
            page_numbers.append(int(text))

    max_page = max(page_numbers) if page_numbers else 1
    debug["max_page"] = max_page

    with st.expander(f"🛠️ Отладка пагинации: {section_url}", expanded=False):
        for k, v in debug.items():
            st.write(f"**{k}**: {v}")

    return max_page


def parse_section(section_name: str, base_url: str) -> pd.DataFrame:
    data = []
    max_pages = get_max_pages(base_url)
    st.info(f"🔍 {section_name}: найдено {max_pages} страниц")

    status = st.empty()
    progress_bar = st.progress(0, text=f"{section_name}: страница 1 из {max_pages}")

    for page in range(1, max_pages + 1):
        status.text(f"🔄 Парсинг раздела: **{section_name}**, страница {page} из {max_pages}")
        progress_bar.progress(page / max_pages, text=f"{section_name}: страница {page} из {max_pages}")

        url = f"{base_url}?count=96&PAGEN_1={page}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        products = soup.find_all("div", class_="catalog-product")

        for product in products:
            try:
                name = product.find("p", class_="catalog-product__title").get_text(strip=True)
                code = product.find("span", class_="property-name", string="Код:")
                code = code.find_next_sibling("span").get_text(strip=True) if code else "—"

                price_spans = product.select("div.catalog-product__price-block-value span[itemprop='price']")
                retail = float(price_spans[0]["content"]) if len(price_spans) > 0 else None
                wholesale = float(price_spans[1]["content"]) if len(price_spans) > 1 else None

                data.append({
                    "Раздел": section_name,
                    "Код": code,
                    "Название": name,
                    "Розничная цена (руб)": retail,
                    "Оптовая цена (руб)": wholesale
                })
            except Exception as e:
                print(f"Ошибка: {e}")

    status.text(f"✅ Готово: {section_name} полностью обработан")
    progress_bar.empty()
    return pd.DataFrame(data)


# Получаем разделы с сайта
sections = get_sections()
selected_sections = st.multiselect("Выберите разделы для парсинга:", options=list(sections.keys()))

if st.button("🚀 Начать парсинг"):
    if not selected_sections:
        st.warning("Пожалуйста, выберите хотя бы один раздел.")
    else:
        full_data = pd.DataFrame()
        for sec in selected_sections:
            df = parse_section(sec, sections[sec])
            full_data = pd.concat([full_data, df], ignore_index=True)

        st.success("✅ Парсинг завершён! Ниже — результат:")
        st.dataframe(full_data)

        # Сохраняем в Excel
        excel_file = "tinko_parsed_data.xlsx"
        full_data.to_excel(excel_file, index=False)
        with open(excel_file, "rb") as f:
            st.download_button(
                "📥 Скачать Excel",
                data=f,
                file_name=excel_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
