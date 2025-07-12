import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os

from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

st.set_page_config(page_title="Парсер Tinko", layout="wide")
st.title("🧰 Парсер сайта tinko.ru — устойчивый режим")


def get_sections():
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
    url = section_url + "?count=96&PAGEN_1=1"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    page_links = soup.select("li.pagination__item > div.pagination__link")
    page_numbers = [int(p.get_text(strip=True)) for p in page_links if p.get_text(strip=True).isdigit()]
    return max(page_numbers) if page_numbers else 1


def parse_section_to_excel(section_name, base_url, writer, sheet_name):
    max_pages = get_max_pages(base_url)
    st.info(f"🔍 {section_name}: найдено {max_pages} страниц")

    status = st.empty()
    progress = st.progress(0, text=f"{section_name} — страница 1 из {max_pages}")

    row_buffer = []
    for page in range(1, max_pages + 1):
        status.text(f"🔄 Парсинг: {section_name}, страница {page}/{max_pages}")
        progress.progress(page / max_pages, text=f"{section_name} — страница {page} из {max_pages}")

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

                row_buffer.append([section_name, code, name, retail, wholesale])

            except Exception as e:
                row_buffer.append([section_name, "—", f"Ошибка: {e}", None, None])

        # ⏱️ Пауза для антиблокировки
        time.sleep(1)

    # 📤 Пишем весь раздел в Excel
    df = pd.DataFrame(row_buffer, columns=["Раздел", "Код", "Название", "Розничная цена (руб)", "Оптовая цена (руб)"])
    df.to_excel(writer, sheet_name=sheet_name, index=False)


# === Интерфейс Streamlit ===
sections = get_sections()
selected_sections = st.multiselect("Выберите разделы для парсинга:", options=list(sections.keys()))

if st.button("🚀 Запустить устойчивый парсинг"):
    if not selected_sections:
        st.warning("Пожалуйста, выберите хотя бы один раздел.")
    else:
        excel_path = "tinko_parsed_result.xlsx"

        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for i, section in enumerate(selected_sections, start=1):
                parse_section_to_excel(section, sections[section], writer, sheet_name=f"Раздел {i}")

        st.success("✅ Парсинг завершён! Данные сохранены в Excel.")
        with open(excel_path, "rb") as f:
            st.download_button("📥 Скачать Excel", data=f, file_name=excel_path, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
