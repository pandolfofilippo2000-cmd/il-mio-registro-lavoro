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
        with st.form("form_prog", clear_on_submit=True):
            st.write("**Programma un nuovo turno futuro**")
            c1, c2 = st.columns(2)
            p_lav = c1.selectbox("Lavoro:", lavori_df['nome'], key="p_lav")
            p_data = c2.date_input("Giorno:", today + timedelta(days=1), format="DD/MM/YYYY")
            p_t1 = c1.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time(), step=900)
            p_t2 = c2.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time(), step=900)
            if st.form_submit_button("AGGIUNGI A PROGRAMMAZIONE"):
                p_ore = (datetime.combine(date.today(), p_t2) - datetime.combine(date.today(), p_t1)).total_seconds() / 3600
                p_id_lav = lavori_df[lavori_df['nome'] == p_lav]['id'].values[0]
                supabase.table("programmazione").insert({
                    "lavoro_id": int(p_id_lav), 
                    "data": str(p_data), 
                    "ora_inizio": p_t1.strftime("%H:%M"), 
                    "ora_fine": p_t2.strftime("%H:%M"), 
                    "ore_decimali": p_ore
                }).execute()
                st.rerun()

        prog_res = supabase.table("programmazione").select("*, lavori(nome)").order("data").execute()
        df_prog = pd.DataFrame(prog_res.data)
        if not df_prog.empty:
            df_prog['Data_IT'] = pd.to_datetime(df_prog['data']).dt.strftime('%d/%m/%Y')
            for r in df_prog.itertuples():
                cp1, cp2, cp3 = st.columns([3, 2, 1])
                cp1.write(f"**{r.Data_IT}** - {r.lavori['nome']}")
                cp2.write(f"🕒 {r.ora_inizio}-{r.ora_fine}")
                if cp3.button("✅", key=f"c_{r.id}"):
                    supabase.table("sessioni").insert({"lavoro_id": r.lavoro_id, "data": str(r.data), "ora_inizio": r.ora_inizio, "ora_fine": r.ora_fine, "ore_decimali": r.ore_decimali}).execute()
                    supabase.table("programmazione").delete().eq("id", r.id).execute()
                    st.rerun()

    # --- 🗺️ REGISTRO EFFETTIVO (TABELLA COMPATTA) ---
    st.subheader("🗺️ Registro Orari Effettivi")
    if not df_sess.empty:
        df_sess['Orario'] = df_sess['ora_inizio'] + " - " + df_sess['ora_fine']
        mappa = df_sess.pivot_table(index='Data_IT', columns='nome_lavoro', values='Orario', aggfunc=lambda x: ' / '.join(x)).fillna("-")
        st.dataframe(mappa, use_container_width=True)
    else:
        st.info("Nessun orario registrato per questo periodo.")

    # --- 📝 REGISTRA TURNO GIÀ FATTO (IL TUO INSERIMENTO MANUALE) ---
    st.divider()
    with st.expander("📝 Registra Turno già fatto (Manuale)"):
        with st.form("diretto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            lav_d = c1.selectbox("Lavoro:", lavori_df['nome'], key="lav_d")
            data_d = c2.date_input("Giorno:", date.today(), format="DD/MM/YYYY", key="data_d")
            t1_d = c1.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time(), step=900, key="t1_d")
            t2_d = c2.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time(), step=900, key="t2_d")
            if st.form_submit_button("REGISTRA"):
                ore_d = (datetime.combine(date.today(), t2_d) - datetime.combine(date.today(), t1_d)).total_seconds() / 3600
                id_l_d = lavori_df[lavori_df['nome'] == lav_d]['id'].values[0]
                supabase.table("sessioni").insert({
                    "lavoro_id": int(id_l_d), 
                    "data": str(data_d), 
                    "ora_inizio": t1_d.strftime("%H:%M"), 
                    "ora_fine": t2_d.strftime("%H:%M"), 
                    "ore_decimali": ore_d
                }).execute()
                st.rerun()

    # --- 🗑️ ELIMINA ERRORI ---
    with st.expander("🗑️ Elimina un errore dal registro"):
        if not df_sess.empty:
            id_del = st.selectbox("Turno da rimuovere:", df_sess['id'], format_func=lambda x: f"{df_sess[df_sess['id']==x]['Data_IT'].values[0]} - {df_sess[df_sess['id']==x]['nome_lavoro'].values[0]}")
            if st.button("ELIMINA"):
                supabase.table("sessioni").delete().eq("id", id_del).execute()
                st.rerun()

with st.sidebar.expander("⚙️ Gestione Lavori"):
    n_lav = st.text_input("Aggiungi lavoro:")
    if st.button("Salva Nome"):
        supabase.table("lavori").insert({"nome": n_lav.strip()}).execute()
        st.rerun()
