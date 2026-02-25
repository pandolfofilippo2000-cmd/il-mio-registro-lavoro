import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from supabase import create_client, Client

st.set_page_config(page_title="Mavriq Tracker Pro", layout="wide")

# --- CONNESSIONE SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

def format_durata(val):
    if pd.isna(val) or val is None: return "0,00 h"
    ore = int(val)
    minuti = int(round((val - ore) * 60))
    return f"{ore},{minuti:02d} h"

# --- LOGICA PERIODO 16 - 15 ---
today = date.today()
if today.day <= 15:
    fine_def = date(today.year, today.month, 15)
    ini_def = (fine_def.replace(day=1) - timedelta(days=1)).replace(day=16)
else:
    ini_def = date(today.year, today.month, 16)
    fine_def = (ini_def.replace(day=28) + timedelta(days=5)).replace(day=15)

st.sidebar.header("🗓️ Filtro Periodo")
d_inizio = st.sidebar.date_input("Inizio:", ini_def, format="DD/MM/YYYY")
d_fine = st.sidebar.date_input("Fine:", fine_def, format="DD/MM/YYYY")

# --- RECUPERO DATI ---
lavori_res = supabase.table("lavori").select("*").execute()
lavori_df = pd.DataFrame(lavori_res.data)

st.title("🎧 Dashboard Lavoro Pro")

if not lavori_df.empty:
    # Sessioni REALI
    sessioni_res = supabase.table("sessioni").select("*, lavori(nome)").filter("data", "gte", d_inizio).filter("data", "lte", d_fine).order("data").execute()
    df_sess = pd.DataFrame(sessioni_res.data)

    if not df_sess.empty:
        df_sess['nome_lavoro'] = df_sess['lavori'].apply(lambda x: x['nome'])
        df_sess['Data_IT'] = pd.to_datetime(df_sess['data']).dt.strftime('%d/%m/%Y')
        stats = df_sess.groupby('nome_lavoro')['ore_decimali'].sum().reset_index()

        # --- CARD GUADAGNI COMPATTE ---
        cols = st.columns(len(stats))
        for i, row in stats.iterrows():
            n, o = row['nome_lavoro'], row['ore_decimali']
            colore = "#1E88E5" if "mavriq" in n.lower() else "#43A047"
            with cols[i]:
                st.markdown(f"""
                    <div style='border-bottom: 3px solid {colore}; padding: 10px; background-color: #1e1e1e; border-radius: 10px;'>
                        <span style='color:{colore}; font-weight:bold;'>{n.upper()}</span><br>
                        <span style='font-size:1.5rem;'>{format_durata(o)}</span><br>
                        <span style='font-size:0.8rem;'>{'€ ' + str(round(o*8.60*0.8833, 2)) if "mavriq" in n.lower() else "Servizio Civile"}</span>
                    </div>
                """, unsafe_allow_html=True)

    # --- 📅 PIANIFICAZIONE ---
    st.divider()
    with st.expander("📅 Pianificazione Settimana"):
        # Form inserimento programmazione
        with st.form("form_prog", clear_on_submit=True):
            st.write("**Aggiungi turno da pianificare**")
            c1, c2 = st.columns(2)
            p_lav = c1.selectbox("Lavoro:", lavori_df['nome'], key="p_lav")
            p_data = c2.date_input("Giorno:", today + timedelta(days=1), format="DD/MM/YYYY")
            p_t1 = c1.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time(), step=900)
            p_t2 = c2.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time(), step=900)
            if st.form_submit_button("AGGIUNGI A PROGRAMMAZIONE"):
                p_ore = (datetime.combine(date.today(), p_t2) - datetime.combine(date.today(), p_t1)).total_seconds() / 3600
                p_id_lav = lavori_df[lavori_df['nome'] == p_lav]['id'].values[0]
                supabase.table("programmazione").insert({"lavoro_id": int(p_id_lav), "data": str(p_data), "ora_inizio": p_t1.strftime("%H:%M"),
