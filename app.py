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

        # --- CARD GUADAGNI ---
        cols = st.columns(len(stats))
        for i, row in stats.iterrows():
            n, o = row['nome_lavoro'], row['ore_decimali']
            icona, colore = ("🎧", "#1E88E5") if "mavriq" in n.lower() else ("🤝", "#43A047")
            paga = f"€ {(o * 8.60 * 0.8833):.2f} Netto" if "mavriq" in n.lower() else "Servizio Civile"
            with cols[i]:
                st.markdown(f"""
                    <div style='background-color:{colore}15; border-radius:15px; padding:15px; border:2px solid {colore}; text-align:center;'>
                        <h3 style='margin:0;color:{colore};'>{icona} {n}</h3>
                        <h2 style='margin:5px 0;'>{format_durata(o)}</h2>
                        <p style='margin:0;font-size:0.9rem;'>{paga}</p>
                    </div>
                """, unsafe_allow_html=True)
        
        st.write("")
        st.bar_chart(stats, x="nome_lavoro", y="ore_decimali")

    # --- 📅 PIANIFICAZIONE COMPATTA ---
    st.divider()
    st.subheader("🗓️ Pianificazione Settimana")
    with st.expander("➕ Programma Turno"):
        with st.form("form_prog", clear_on_submit=True):
            p_lav = st.selectbox("Lavoro:", lavori_df['nome'])
            p_data = st.date_input("Giorno:", today + timedelta(days=1), format="DD/MM/YYYY")
            c1, c2 = st.columns(2)
            p_t1 = c1.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time(), step=900)
            p_t2 = c2.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time(), step=900)
            if st.form_submit_button("Aggiungi"):
                p_ore = (datetime.combine(date.today(), p_t2) - datetime.combine(date.today(), p_t1)).total_seconds() / 3600
                p_id_lav = lavori_df[lavori_df['nome'] == p_lav]['id'].values[0]
                supabase.table("programmazione").insert({"lavoro_id": int(p_id_lav), "data": str(p_data), "ora_inizio": p_t1.strftime("%H:%M"), "ora_fine": p_t2.strftime("%H:%M"), "ore_decimali": p_ore}).execute()
                st.rerun()

    prog_res = supabase.table("programmazione").select("*, lavori(nome)").order("data").execute()
    df_prog = pd.DataFrame(prog_res.data)
    if not df_prog.empty:
        df_prog['Data_IT'] = pd.to_datetime(df_prog['data']).dt.strftime('%d/%m/%Y')
        for d_it in df_prog['Data_IT'].unique():
            turni = df_prog[df_prog['Data_IT'] == d_it]
            st.markdown(f"**{d_it}**")
            c_prog = st.columns(len(turni))
            for idx, r in enumerate(turni.itertuples()):
                with c_prog[idx]:
                    st.caption(f"{r.lavori['nome']}")
                    st.code(f"{r.ora_inizio}-{r.ora_fine}")
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.button("✅", key=f"c_{r.id}"):
                        supabase.table("sessioni").insert({"lavoro_id": r.lavoro_id, "data": str(r.data), "ora_inizio": r.ora_inizio, "ora_fine": r.ora_fine, "ore_decimali": r.ore_decimali}).execute()
                        supabase.table("programmazione").delete().eq("id", r.id).execute()
                        st.rerun()
                    if c_btn2.button("🗑️", key=f"dp_{r.id}"):
                        supabase.table("programmazione").delete().eq("id", r.id).execute()
                        st.rerun()

    # --- 🗺️ MAPPA ORARI EFFETTIVI STILIZZATA ---
    st.divider()
    st.subheader("🗺️ Registro Orari Effettivi")
    if not df_sess.empty:
        for d_it in df_sess['Data_IT'].unique():
            giorno_eff = df_sess[df_sess['Data_IT'] == d_it]
            with st.container():
                st.markdown(f"<div style='margin-bottom:5px;'><b>{d_it}</b></div>", unsafe_allow_html=True)
                cols_eff = st.columns(len(giorno_eff))
                for idx, r in enumerate(giorno_eff.itertuples()):
                    colore = "#1E88E5" if "mavriq" in r.nome_lavoro.lower() else "#43A047"
                    with cols_eff[idx]:
                        st.markdown(f"""
                            <div style='border-left: 4px solid {colore}; padding-left: 10px; background-color: #f0f2f6; border-radius: 5px; padding: 5px;'>
                                <span style='font-size:0.8rem; color:{colore}; font-weight:bold;'>{r.nome_lavoro}</span><br>
                                <span style='font-size:0.9rem;'>🕒 {r.ora_inizio} - {r.ora_fine}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        if st.button("Elimina", key=f"del_eff_{r.id}", type="secondary"):
                            supabase.table("sessioni").delete().eq("id", r.id).execute()
                            st.rerun()
                st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)
    else:
        st.info("Ancora nessun turno registrato in questo periodo.")

with st.sidebar.expander("⚙️ Gestione"):
    if st.button("Pulisci Pianificazione"):
        supabase.table("programmazione").delete().neq("id", 0).execute()
        st.rerun()
