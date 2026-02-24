import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from supabase import create_client, Client

st.set_page_config(page_title="Mavriq & Volontariato Tracker", layout="wide")

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
    sessioni_res = supabase.table("sessioni").select("*, lavori(nome)").filter("data", "gte", d_inizio).filter("data", "lte", d_fine).execute()
    df_sess = pd.DataFrame(sessioni_res.data)

    if not df_sess.empty:
        df_sess['nome_lavoro'] = df_sess['lavori'].apply(lambda x: x['nome'])
        df_sess['Data_IT'] = pd.to_datetime(df_sess['data']).dt.strftime('%d/%m/%Y')
        stats = df_sess.groupby('nome_lavoro')['ore_decimali'].sum().reset_index()

        # --- CARD STILIZZATE ---
        cols = st.columns(len(stats))
        for i, row in stats.iterrows():
            n = row['nome_lavoro']
            o = row['ore_decimali']
            
            # Icone e Colori dinamici
            if "mavriq" in n.lower():
                icona, colore = "🎧", "#1E88E5"
                paga = f"€ {(o * 8.60 * 0.8833):.2f} Netto"
            else:
                icona, colore = "🤝", "#43A047"
                paga = "Servizio Civile"

            with cols[i]:
                st.markdown(f"""
                    <div style="background-color: {colore}15; border-radius: 15px; padding: 20px; border: 2px solid {colore};">
                        <h3 style="margin: 0; color: {colore};">{icona} {n}</h3>
                        <h1 style="margin: 10px 0; font-size: 2.5rem;">{format_durata(o)}</h1>
                        <p style="margin: 0; font-weight: bold; color: {colore};">{paga}</p>
                    </div>
                """, unsafe_allow_html=True)

        # --- OBIETTIVO 100 ORE MAVRIQ ---
        mav_ore = stats[stats['nome_lavoro'].str.contains("mavriq", case=False)]['ore_decimali'].sum() if any(stats['nome_lavoro'].str.contains("mavriq", case=False)) else 0
        st.divider()
        st.subheader("🎯 Obiettivo Mensile Mavriq (100h)")
        progresso = min(mav_ore / 100, 1.0)
        st.progress(progresso)
        st.write(f"Hai completato **{mav_ore:.1f}** ore su 100. Forza! 🔥" if mav_ore < 100 else "🎯 Obiettivo Raggiunto! Grandissimo!")

        # --- REPORT PER NOTE ---
        st.divider()
        with st.expander("📝 Genera Report per Note"):
            report_text = f"REOCONTO LAVORO ({d_inizio.strftime('%d/%m')} - {d_fine.strftime('%d/%m')})\n"
            for _, r in stats.iterrows():
                report_text += f"- {r['nome_lavoro']}: {format_durata(r['ore_decimali'])}\n"
            st.code(report_text, language="text")
            st.info("Copia il testo sopra e incollalo nelle tue Note dell'iPhone.")

        # --- MAPPA DETTAGLIATA ---
        st.subheader("🗺️ Mappa Orari")
        df_sess['Dettaglio'] = df_sess['ora_inizio'] + " - " + df_sess['ora_fine']
        mappa = df_sess.pivot_table(index='Data_IT', columns='nome_lavoro', values='Dettaglio', aggfunc=lambda x: ' / '.join(x)).fillna("-")
        st.table(mappa) # Usiamo table per visualizzazione mobile più chiara

        # --- ELIMINAZIONE ---
        with st.expander("🗑️ Gestione Errori"):
            id_del = st.selectbox("ID Turno da eliminare:", df_sess['id'], format_func=lambda x: f"ID {x} - {df_sess[df_sess['id']==x]['Data_IT'].values[0]}")
            if st.button("Elimina"):
                supabase.table("sessioni").delete().eq("id", id_del).execute()
                st.rerun()

# --- INSERIMENTO ---
st.divider()
st.subheader("📝 Registra Turno")
if not lavori_df.empty:
    with st.form("ins_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        lav_scelto = c1.selectbox("Lavoro:", lavori_df['nome'])
        giorno = c2.date_input("Giorno:", date.today())
        t1 = st.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time(), step=900)
        t2 = st.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time(), step=900)
        if st.form_submit_button("REGISTRA"):
            ore = (datetime.combine(date.today(), t2) - datetime.combine(date.today(), t1)).total_seconds() / 3600
            if ore > 0:
                id_lav = lavori_df[lavori_df['nome'] == lav_scelto]['id'].values[0]
                supabase.table("sessioni").insert({"lavoro_id": int(id_lav), "data": str(giorno), "ora_inizio": t1.strftime("%H:%M"), "ora_fine": t2.strftime("%H:%M"), "ore_decimali": ore}).execute()
                st.success("Salvato!")
                st.rerun()

# --- SIDEBAR GESTIONE NOMI ---
with st.sidebar.expander("⚙️ Gestisci Nomi Lavori"):
    nuovo_lav = st.text_input("Aggiungi:")
    if st.button("Salva"):
        if nuovo_lav:
            supabase.table("lavori").insert({"nome": nuovo_lav.strip()}).execute()
            st.rerun()
