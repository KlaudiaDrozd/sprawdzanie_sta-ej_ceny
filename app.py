import pandas as pd
import streamlit as st
from io import BytesIO
import numpy as np
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

# Ustawienie limitu komórek dla Pandas Styler
pd.set_option("styler.render.max_elements", 3000000)

# Lista kolumn binarnych do sprawdzenia
columns_to_check = [
    'Katalogowa PLN', 'Promocyjna PLN', 'Katalogowa CZK', 'Promocyjna CZK',
    'Katalogowa RON', 'Promocyjna RON', 'Katalogowa BGN', 'Promocyjna BGN',
    'Katalogowa EUR DE', 'Promocyjna EUR DE', 'Katalogowa EUR GR', 'Promocyjna EUR GR',
    'Katalogowa EUR IT', 'Promocyjna EUR IT', 'Katalogowa EUR LT', 'Promocyjna EUR LT',
    'Katalogowa EUR SK', 'Promocyjna EUR SK', 'Katalogowa UAH', 'Promocyjna UAH',
    'Katalogowa HUF', 'Promocyjna HUF', 'Marketplace PL', 'Marketplace CZ',
    'Marketplace RO', 'Kaufland EUR DE', 'Empik PLN', 'Marketplace Amazon DE',
    'Marketplace FR', 'Marketplace IT', 'Marketplace Amazon ES', 'Marketplace HU',
    'Marketplace SK', 'Marketplace SE', 'Marketplace UAH'
]

# Funkcja do wczytywania pliku z pamięcią podręczną
@st.cache_data
def load_file(uploaded_file):
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                return pd.read_csv(uploaded_file, low_memory=False, dtype={'index': str, 'Indeks': str, 'modelcolor': str})
            elif uploaded_file.name.endswith('.xlsx'):
                return pd.read_excel(uploaded_file, engine='openpyxl', dtype={'index': str, 'Indeks': str, 'modelcolor': str})
        except Exception as e:
            st.error(f"Błąd wczytywania pliku {uploaded_file.name}: {str(e)}")
            return None
    return None

# Funkcja do czyszczenia nazw kolumn
def clean_column_names(df):
    df.columns = df.columns.str.strip()
    return df

# Zoptymalizowana funkcja do sprawdzania spójności z pamięcią podręczną
@st.cache_data
def check_consistency(df, columns_to_check):
    relevant_cols = ['modelcolor', 'index', 'Producent', 'Kat 1', 'last_delivery_date'] + columns_to_check
    df_subset = df[relevant_cols].copy()

    grouped = df_subset.groupby('modelcolor')
    total_groups = len(grouped)
    result = []
    progress_step = 0

    for i, (modelcolor, group) in enumerate(grouped):
        for col in columns_to_check:
            values = group[col]
            non_null_values = values[values.isin([0, 1])]
            if non_null_values.nunique() > 1:
                for idx in group.index:
                    value = group.loc[idx, col]
                    if pd.isna(value) or value in [0, 1]:
                        result.append({
                            'modelcolor': modelcolor,
                            'index': group.loc[idx, 'index'],
                            'Producent': group.loc[idx, 'Producent'] if 'Producent' in group.columns else '',
                            'Kat 1': group.loc[idx, 'Kat 1'] if 'Kat 1' in group.columns else '',
                            'last_delivery_date': group.loc[idx, 'last_delivery_date'],
                            'problem_column': col,
                            'problem_value': value,
                            'issue': f"Niespójność w {col} (różne wartości 0/1)"
                        })
                    else:
                        result.append({
                            'modelcolor': modelcolor,
                            'index': group.loc[idx, 'index'],
                            'Producent': group.loc[idx, 'Producent'] if 'Producent' in group.columns else '',
                            'Kat 1': group.loc[idx, 'Kat 1'] if 'Kat 1' in group.columns else '',
                            'last_delivery_date': group.loc[idx, 'last_delivery_date'],
                            'problem_column': col,
                            'problem_value': value,
                            'issue': f"Niepoprawna wartość w {col} (oczekiwano 0 lub 1)"
                        })

        progress_step += 1

    result_df = pd.DataFrame(result)
    if not result_df.empty:
        result_df = result_df.sort_values(by=['modelcolor', 'last_delivery_date'])
    return result_df

# Funkcja do podświetlania tylko problematycznej wartości w Streamlit
def highlight_issues(row):
    styles = [''] * len(row)
    if row['issue']:
        for i, col in enumerate(row.index):
            if col == 'problem_value':
                styles[i] = 'background-color: red'
                break
    return styles

# Funkcja do zapisu pliku Excel z podświetleniem (bez opisów kolumn)
@st.cache_data
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Raport')
        if not df.empty:
            workbook = writer.book
            worksheet = writer.sheets['Raport']
            red_fill = PatternFill(start_color='FF0000', end_color='FF0000', fill_type='solid')

            for row_idx, row_data in df.iterrows():
                if row_data['issue']:
                    for col_idx, col_name in enumerate(df.columns, start=1):
                        if col_name == 'problem_value':
                            worksheet.cell(row=row_idx + 2, column=col_idx).fill = red_fill
                            break

            for col_idx in range(1, len(df.columns) + 1):
                col_letter = get_column_letter(col_idx)
                worksheet.column_dimensions[col_letter].width = 25

    return output.getvalue()

# Tytuł aplikacji
st.title("Sprawdzanie spójności binarnych danych stałych cen")

# Wczytanie plików
uploaded_file1 = st.file_uploader("Wybierz plik z bazą danych", type=["csv", "xlsx"])
uploaded_file2 = st.file_uploader("Wybierz plik ze stałymi cenami", type=["csv", "xlsx"])

if uploaded_file1 is not None and uploaded_file2 is not None:
    # Wczytanie i czyszczenie danych
    with st.spinner("Wczytywanie danych..."):
        df_base = load_file(uploaded_file1)
        df_prices = load_file(uploaded_file2)

    if df_base is None or df_prices is None:
        st.error("Nie udało się wczytać jednego z plików. Sprawdź format lub zawartość.")
    else:
        df_base = clean_column_names(df_base)
        df_prices = clean_column_names(df_prices)

        # Sprawdzanie wymaganych kolumn
        required_base_cols = ['index', 'modelcolor', 'last_delivery_date']
        required_price_cols = ['Indeks', 'Producent', 'Kat 1'] + columns_to_check

        missing_base_cols = [col for col in required_base_cols if col not in df_base.columns]
        missing_price_cols = [col for col in required_price_cols if col not in df_prices.columns]

        if missing_base_cols or missing_price_cols:
            st.error(f"Brakujące kolumny w pliku z bazą: {missing_base_cols}, w pliku z cenami: {missing_price_cols}")
        else:
            # Normalizacja nazw kolumn
            df_prices = df_prices.rename(columns={'Indeks': 'index'})

            # Filtrowanie po modelcolor z wyszukiwaniem
            unique_modelcolors = df_base['modelcolor'].unique()
            st.subheader("Filtrowanie po modelcolor")
            modelcolor_search = st.text_input("Wyszukaj modelcolor (wpisz fragment, aby zawęzić listę):", "")
            if modelcolor_search:
                filtered_modelcolors = [mc for mc in unique_modelcolors if modelcolor_search.lower() in str(mc).lower()]
            else:
                filtered_modelcolors = unique_modelcolors
            selected_modelcolors = st.multiselect("Wybierz modelcolor do analizy (zostaw puste, aby analizować wszystkie)", 
                                                options=filtered_modelcolors, 
                                                default=[])

            # Filtrowanie po Producent z wyszukiwaniem
            unique_producents = df_prices['Producent'].unique()
            st.subheader("Filtrowanie po Producent")
            producent_search = st.text_input("Wyszukaj Producent (wpisz fragment, aby zawęzić listę):", "")
            if producent_search:
                filtered_producents = [p for p in unique_producents if producent_search.lower() in str(p).lower()]
            else:
                filtered_producents = unique_producents
            selected_producents = st.multiselect("Wybierz Producent do analizy (zostaw puste, aby analizować wszystkich)", 
                                                options=filtered_producents, 
                                                default=[])

            # Łączenie danych z pamięcią podręczną
            @st.cache_data
            def merge_data(df_base, df_prices, selected_modelcolors, selected_producents):
                merged_df = pd.merge(df_base[['index', 'modelcolor', 'last_delivery_date']],
                                    df_prices[['index', 'Producent', 'Kat 1'] + columns_to_check],
                                    how='left',
                                    on='index')
                if selected_modelcolors:
                    merged_df = merged_df[merged_df['modelcolor'].isin(selected_modelcolors)]
                if selected_producents:
                    merged_df = merged_df[merged_df['Producent'].isin(selected_producents)]
                return merged_df

            # Łączenie danych
            with st.spinner("Łączenie danych..."):
                merged_df = merge_data(df_base, df_prices, selected_modelcolors, selected_producents)

            # Diagnostyka: Wyświetlenie danych po złączeniu dla wybranego modelcolor
            if selected_modelcolors:
                st.subheader("Dane po złączeniu dla wybranego modelcolor (diagnostyka)")
                for modelcolor in selected_modelcolors:
                    st.write(f"**modelcolor = {modelcolor}**")
                    modelcolor_data = merged_df[merged_df['modelcolor'] == modelcolor][['index', 'Producent', 'Kat 1', 'last_delivery_date'] + columns_to_check]
                    st.dataframe(modelcolor_data)

            # Sprawdzanie spójności z paskiem postępu
            st.write("Sprawdzanie spójności binarnych danych stałych cen...")
            progress_bar = st.progress(0)
            issues_df = check_consistency(merged_df, columns_to_check)
            progress_bar.progress(1.0)

            # Wybór liczby wierszy do wyświetlenia
            st.subheader("Ustawienia wyświetlania")
            max_rows = len(issues_df) if not issues_df.empty else 0
            display_rows = st.slider("Wybierz liczbę wierszy do wyświetlenia",
                                    min_value=1, max_value=max_rows, value=min(100, max_rows), step=10) if max_rows > 0 else 1

            if issues_df.empty:
                st.success("Wszystkie binarne dane stałych cen są spójne w obrębie modelcolor!")
            else:
                st.warning(f"Znaleziono {len(issues_df)} niespójności lub niepoprawnych wartości w binarnych danych stałych cen:")
                
                # Wyświetlanie raportu z podświetleniem
                styled_issues = issues_df.head(display_rows).style.apply(highlight_issues, axis=1)
                st.dataframe(styled_issues)

                # Pobieranie pliku z raportem
                excel_data = to_excel(issues_df)
                st.download_button(
                    label="Pobierz raport z problemami (Excel)",
                    data=excel_data,
                    file_name="issues_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
else:
    st.info("Proszę załadować oba pliki, aby kontynuować.")