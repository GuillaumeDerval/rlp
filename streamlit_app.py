"""
Public domain.
Original author: Guillaume Derval.
Source for elec.csv and gaz.csv: Synergrid (2022).
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import altair as alt

@st.cache
def load_data():
    elec = pd.read_csv("elec.csv", parse_dates=["date"]).set_index(["GRD", "date"])
    gaz = pd.read_csv("gaz.csv", parse_dates=["date"]).set_index(["date"])
    return elec, gaz

elec, gaz = load_data()

st.title("🇧🇪 Estimer votre consommation mensuelle sur base de deux index")

OPTION_ELEC = "Electricité"
OPTION_GAZ = "Gaz"
option = st.selectbox(
     'Pour quelle énergie faire la simulation?',
     (
         #'Selectionnez une énergie',
         OPTION_ELEC, OPTION_GAZ
     )
)

if option in [OPTION_ELEC, OPTION_GAZ]:
    if option == "Gaz":
        unit = st.radio('Indiquez l\'unité de comptage de votre compteur', ("kWh", "m3"))
    else:
        unit = "kWh"

    if option == OPTION_ELEC:
        st.warning("Ce calculateur fait l'hypothèse que vous n'avez pas de panneaux photovoltaiques.")

    col1, col2 = st.columns(2)
    first_index_date = col1.date_input("Date du premier index", value=date.today()-timedelta(days=180))
    first_index_value = col1.number_input(f'Valeur du premier index ({unit})', step=10, value=2447, key="findex")
    second_index_date = col2.date_input("Date du second index", value=date.today())
    second_index_value = col2.number_input(f'Valeur du second index ({unit})', step=10, value=4495, key="sindex")

    if first_index_date >= second_index_date:
        st.error("Dates des index incorrectes.")
        st.stop()
    if first_index_value >= second_index_value:
        st.error("Index incorrects.")
        st.stop()

    if option == OPTION_ELEC:
        kwh = second_index_value-first_index_value
        st.info(f"Au total {(second_index_date-first_index_date).days} jours, {kwh:.2f} kWh")
    else:
        if unit == "kWh":
            kwh = second_index_value-first_index_value
            m3 = kwh/10.1888
        else:
            m3 = second_index_value-first_index_value
            kwh = m3*10.1888
        st.info(f"Au total {(second_index_date - first_index_date).days} jours, {kwh:.2f} kWh, {m3:.2f} m3")

    if option == OPTION_ELEC:
        GRD = st.selectbox("Indiquez votre gestionnaire de réseau de distribution", ["Je ne sais pas (basé sur ORES - Namur)"] + list(elec.index.levels[0]))

    first_year = first_index_date.year
    last_year = second_index_date.year

    def intersect_range_with_year(begin, end, year):
        begin_y = date(year, 1, 1)
        end_y = date(year, 12, 31)

        if begin < begin_y:
            range_start = begin_y
        else:
            range_start = begin

        if end > end_y:
            range_end = end_y
        else:
            range_end = end

        return range_start, range_end

    ranges = [(year, intersect_range_with_year(first_index_date, second_index_date, year)) for year in range(first_year, last_year+1)]

    if option == OPTION_ELEC:
        if GRD not in elec.index.levels[0]:
            GRD = "ORES (Namur)"
        df = elec.loc[GRD,:]
    else:
        df = gaz

    # Let's count how many times each data point in the 2022 RLP series is used
    # to represent the time range between the two indexes.

    df = df.copy()
    df['c'] = 0
    for _, (begin, end) in ranges:
        rbegin = begin.replace(year=2022)
        rend = end.replace(year=2022)
        df.loc[(rbegin <= df.index.date) & (df.index.date <= rend), "c"] += 1

    ratio_year = (df.value * df.c).sum()

    st.title("Consommation estimée")


    if option == OPTION_ELEC:
        st.info(f"Votre consommation annuelle est donc estimée à  {kwh/ratio_year:.2f} kWh")
    else:
        st.info(f"Votre consommation annuelle est donc estimée à {kwh/ratio_year:.2f} kWh = {m3/ratio_year:.2f} m3")

    st.header("Détails du calcul")
    st.markdown(f"""Votre consommation annuelle d'électricité ou de gaz n'est pas lisse. On consomme plus l'hiver.
    Les fournisseurs d'énergie fournissant généralement des prix mensuels ou trimestriels, il est nécessaire pour eux de répartir votre index (généralement annuel).
    """)
    st.markdown(f"""Votre index représente {ratio_year * 100:.2f}% de votre consommation annuelle estimée sur base des 
    [courbes RLP-2022 fournies par Synergrid](http://www.synergrid.be/index.cfm?PageID=20957#). La tranche de l'année 
    recouverte par votre consommation est représentée sur le graphique suivant:
    """)

    # Let's count how many times each data point in the 2022 RLP series is used
    # to represent the time range between the two indexes.
    dates = sorted({date(2022, 1, 1), date(2023, 1, 1), first_index_date.replace(year=2022), second_index_date.replace(year=2022)+timedelta(days=1)})
    rects = [[dates[i], dates[i+1], 0] for i in range(len(dates)-1)]

    cur_rect_idx = 0
    cur_year = first_index_date.year
    while True:
        cur_time = rects[cur_rect_idx][0].replace(year=cur_year)
        if cur_time > second_index_date:
            break
        if cur_time >= first_index_date:
            rects[cur_rect_idx][2] += 1

        cur_rect_idx += 1
        if cur_rect_idx >= len(rects):
            cur_rect_idx = 0
            cur_year += 1

    rects = pd.DataFrame([x for x in rects if x[2] > 0], columns=["start", "end", "count"])

    c1 = alt.Chart(df.reset_index()).mark_line().encode(
        x=alt.X('date:T', title="Date"),
        y=alt.Y('value:Q', title="Consommation (ratio du total)")
    )

    c2 = alt.Chart(rects).mark_rect(opacity=0.4).encode(
        x='start:T',
        x2='end:T',
        color=alt.Color('count:N', title="# dans l'index")
    )
    st.altair_chart(c2+c1, use_container_width=True)

    st.markdown("""Les différents fournisseurs utilisent ces mêmes courbes pour calculer votre répartition mensuelle 
    (ou trimestrielle) de consommation. Voici vos consommations mensuelles estimées, en kWh:""")

    df["conso"] = df["value"] * kwh/ratio_year
    df["conso_eff"] = df["value"] * kwh/ratio_year * df["c"]
    df_month = df.groupby([pd.Grouper(freq='M', level='date')]).sum()

    c = alt.Chart(df_month.reset_index()).mark_bar().encode(
        x=alt.X('month(date):O', title="Date"),
        y=alt.Y('conso:Q', title="Consommation (kWh)"),
        tooltip=['month(date):O', alt.Tooltip('conso:Q',format=".2f")]
    ).interactive()
    st.altair_chart(c, use_container_width=True)

    st.info("A venir: historique des prix par fournisseur, prévision des factures.")
    st.markdown("[Le code source (pas très beau) de cette application est public sur GitHub.](https://github.com/GuillaumeDerval/rlp)")