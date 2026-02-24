import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from supabase import create_client, Client

st.set_page_config(page_title="Mavriq Tracker Pro Cloud", layout="wide")

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

st.sidebar.header("🗓️ Filtro Stipendio")
d_inizio = st.sidebar.date_input("Inizio Periodo:", ini_def)
d_fine = st.sidebar.date_input("Fine Periodo:", fine_def)

# --- RECUPERO DATI ---
lavori_res = supabase.table("lavori").select("*").execute()
lavori_df = pd.DataFrame(lavori_res.data)

st.title("💰 Dashboard Mavriq (Memoria Eterna)")

# --- GESTIONE NOMI LAVORI ---
with st.sidebar.expander("➕ Gestisci Lavori"):
    nuovo_lav = st.text_input("Aggiungi lavoro:")
    if st.button("Salva Nome"):
        if nuovo_lav:
            supabase.table("lavori").insert({"nome": nuovo_lav.strip()}).execute()
            st.rerun()

# --- ANALISI ECONOMICA ---
if not lavori_df.empty:
    sessioni_res = supabase.table("sessioni").select("*, lavori(nome)").filter("data", "gte", d_inizio).filter("data", "lte", d_fine).execute()
    df_sess = pd.DataFrame(sessioni_res.data)

    if not df_sess.empty:
        # Calcolo Totali per Lavoro
        df_sess['nome_lavoro'] = df_sess['lavori'].apply(lambda x: x['nome'])
        stats = df_sess.groupby('nome_lavoro')['ore_decimali'].sum().reset_index()
        
        cols = st.columns(len(stats))
        for i, row in stats.iterrows():
            n = row['nome_lavoro']
            o = row['ore_decimali']
            with cols[i]:
                if "mavriq" in n.lower():
                    netto = (o * 8.60) * (1 - 0.1167)
                    st.metric(n, format_durata(o), f"€ {netto:.2f} Netto")
                else:
                    st.metric(n, format_durata(o), "Fisso Mensile")
        
        st.bar_chart(stats, x="nome_lavoro", y="ore_decimali")

        # --- MAPPA DETTAGLIATA ---
        st.divider()
        st.subheader("🗺️ Mappa Dettagliata Orari")
        df_sess['Dettaglio'] = df_sess['ora_inizio'] + " - " + df_sess['ora_fine'] + " (" + df_sess['ore_decimali'].apply(lambda x: f"{x:.2f}h") + ")"
        mappa = df_sess.pivot_table(index='data', columns='nome_lavoro', values='Dettaglio', aggfunc=lambda x: ' / '.join(x)).fillna("-")
        st.dataframe(mappa, use_container_width=True)

        # --- ELIMINAZIONE ---
        with st.expander("🗑️ Elimina Turno Errato"):
            id_del = st.selectbox("ID Turno:", df_sess['id'], format_func=lambda x: f"ID {x} del {df_sess[df_sess['id']==x]['data'].values[0]}")
            if st.button("CONFERMA RIMOZIONE"):
                supabase.table("sessioni").delete().eq("id", id_del).execute()
                st.warning("Turno rimosso per sempre!")
                st.rerun()

# --- INSERIMENTO ---
st.divider()
st.subheader("📝 Registra Turno")
if not lavori_df.empty:
    with st.form("ins_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        lav_scelto = c1.selectbox("Lavoro:", lavori_df['nome'])
        giorno = c2.date_input("Giorno:", date.today())
        t1 = c3.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time())
        t2 = c3.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time())
        
        if st.form_submit_button("REGISTRA"):
            ore = (datetime.combine(date.today(), t2) - datetime.combine(date.today(), t1)).total_seconds() / 3600
            if ore > 0:
                id_lav = lavori_df[lavori_df['nome'] == lav_scelto]['id'].values[0]
                supabase.table("sessioni").insert({
                    "lavoro_id": int(id_lav),
                    "data": str(giorno),
                    "ora_inizio": t1.strftime("%H:%M"),
                    "ora_fine": t2.strftime("%H:%M"),
                    "ore_decimali": ore
                }).execute()
                st.success("Dati salvati nel Cloud!")
                st.rerun()
else:
    st.info("Aggiungi il tuo primo lavoro nella sidebar!")
