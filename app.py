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

st.sidebar.header("🗓️ Filtro Periodo 16-15")
d_inizio = st.sidebar.date_input("Inizio:", ini_def)
d_fine = st.sidebar.date_input("Fine:", fine_def)

# --- RECUPERO DATI ---
lavori_res = supabase.table("lavori").select("*").execute()
lavori_df = pd.DataFrame(lavori_res.data)

st.title("🎧 Dashboard Lavoro Pro")

if not lavori_df.empty:
    # Sessioni REALI
    sessioni_res = supabase.table("sessioni").select("*, lavori(nome)").filter("data", "gte", d_inizio).filter("data", "lte", d_fine).execute()
    df_sess = pd.DataFrame(sessioni_res.data)

    if not df_sess.empty:
        df_sess['nome_lavoro'] = df_sess['lavori'].apply(lambda x: x['nome'])
        df_sess['Data_IT'] = pd.to_datetime(df_sess['data']).dt.strftime('%d/%m/%Y')
        stats = df_sess.groupby('nome_lavoro')['ore_decimali'].sum().reset_index()

        # --- CARD GUADAGNI ---
        cols = st.columns(len(stats))
        for i, row in stats.iterrows():
            n, o = row['nome_lavoro'], row['ore_decimali']
            icona, colore = ("🎧", "#1E88E5") if "mavriq" in n.lower() else ("🤝", "#43A047")
            paga = f"€ {(o * 8.60 * 0.8833):.2f} Netto" if "mavriq" in n.lower() else "Servizio Civile"
            with cols[i]:
                st.markdown(f"<div style='background-color:{colore}15; border-radius:15px; padding:20px; border:2px solid {colore};'><h3 style='margin:0;color:{colore};'>{icona} {n}</h3><h1 style='margin:10px 0;'>{format_durata(o)}</h1><p style='margin:0;font-weight:bold;color:{colore};'>{paga}</p></div>", unsafe_allow_html=True)
        
        # --- GRAFICO RIPRISTINATO ---
        st.write("")
        st.bar_chart(stats, x="nome_lavoro", y="ore_decimali", color="#1E88E5")

    # --- 📅 PIANIFICAZIONE COMPATTA ---
    st.divider()
    st.subheader("🗓️ Pianificazione Settimana")
    
    with st.expander("➕ Programma Turno"):
        with st.form("form_prog"):
            c1, c2 = st.columns(2)
            p_lav = c1.selectbox("Lavoro:", lavori_df['nome'])
            p_data = c2.date_input("Giorno:", today + timedelta(days=1))
            p_t1 = st.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time(), step=900)
            p_t2 = st.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time(), step=900)
            if st.form_submit_button("Aggiungi"):
                p_ore = (datetime.combine(date.today(), p_t2) - datetime.combine(date.today(), p_t1)).total_seconds() / 3600
                p_id_lav = lavori_df[lavori_df['nome'] == p_lav]['id'].values[0]
                supabase.table("programmazione").insert({"lavoro_id": int(p_id_lav), "data": str(p_data), "ora_inizio": p_t1.strftime("%H:%M"), "ora_fine": p_t2.strftime("%H:%M"), "ore_decimali": p_ore}).execute()
                st.rerun()

    prog_res = supabase.table("programmazione").select("*, lavori(nome)").order("data").execute()
    df_prog = pd.DataFrame(prog_res.data)
    
    if not df_prog.empty:
        df_prog['nome_lavoro'] = df_prog['lavori'].apply(lambda x: x['nome'])
        df_prog['Data_IT'] = pd.to_datetime(df_prog['data']).dt.strftime('%d/%m/%Y')
        
        # Visualizzazione a righe compatte
        for d_it in df_prog['Data_IT'].unique():
            giorno_prog = df_prog[df_prog['Data_IT'] == d_it]
            with st.container():
                st.markdown(f"**📅 {d_it}**")
                cols_p = st.columns(len(giorno_prog))
                for idx, row in enumerate(giorno_prog.itertuples()):
                    with cols_p[idx]:
                        st.markdown(f"<small>{row.nome_lavoro}: {row.ora_inizio}-{row.ora_fine}</small>", unsafe_allow_html=True)
                        btn_col1, btn_col2 = st.columns(2)
                        if btn_col1.button("✅", key=f"c_{row.id}"):
                            supabase.table("sessioni").insert({"lavoro_id": row.lavoro_id, "data": str(row.data), "ora_inizio": row.ora_inizio, "ora_fine": row.ora_fine, "ore_decimali": row.ore_decimali}).execute()
                            supabase.table("programmazione").delete().eq("id", row.id).execute()
                            st.rerun()
                        if btn_col2.button("🗑️", key=f"d_{row.id}"):
                            supabase.table("programmazione").delete().eq("id", row.id).execute()
                            st.rerun()
                st.markdown("---")
    else:
        st.info("Nessun turno in programma.")

    # --- MAPPA ORARI REALI ---
    st.subheader("🗺️ Mappa Orari Effettivi")
    if not df_sess.empty:
        df_sess['Dettaglio'] = df_sess['ora_inizio'] + " - " + df_sess['ora_fine']
        mappa = df_sess.pivot_table(index='Data_IT', columns='nome_lavoro', values='Dettaglio', aggfunc=lambda x: ' / '.join(x)).fillna("-")
        st.table(mappa): n_lav.strip()}).execute()
        st.rerun()

