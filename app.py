import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Registro Lavoro Pro", layout="wide")

# --- GESTIONE DATABASE ---
def get_connection():
    conn = sqlite3.connect('registro_lavoro.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS lavori 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sessioni 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, lavoro_id INTEGER, 
                     data TEXT, ora_inizio TEXT, ora_fine TEXT, ore_decimali REAL)''')
    conn.commit()
    return conn

def format_durata(val):
    if pd.isna(val) or val is None: return "0,00 h"
    ore = int(val)
    minuti = int(round((val - ore) * 60))
    return f"{ore},{minuti:02d} h"

conn = get_connection()

# --- SIDEBAR: BACKUP E LAVORI ---
st.sidebar.header("📁 Gestione Dati")
with st.sidebar.expander("Esporta/Importa (Memoria)"):
    if st.button("Scarica Backup CSV"):
        df_backup = pd.read_sql_query("SELECT * FROM sessioni", conn)
        st.download_button("Download", df_backup.to_csv(index=False), "backup.csv")
    
    file_caricato = st.file_uploader("Carica Backup", type="csv")
    if file_caricato:
        df_import = pd.read_csv(file_caricato)
        df_import.to_sql("sessioni", conn, if_exists="replace", index=False)
        st.success("Dati Ripristinati!")

with st.sidebar.expander("➕ Gestisci Nomi Lavori"):
    nuovo_lav = st.text_input("Nome Lavoro:")
    if st.button("Aggiungi"):
        if nuovo_lav:
            conn.execute("INSERT INTO lavori (nome) VALUES (?)", (nuovo_lav.strip(),))
            conn.commit()
            st.rerun()

# --- LOGICA DATE (16-15) ---
st.sidebar.divider()
today = date.today()
if today.day <= 15:
    fine_def = date(today.year, today.month, 15)
    ini_def = (fine_def.replace(day=1) - timedelta(days=1)).replace(day=16)
else:
    ini_def = date(today.year, today.month, 16)
    fine_def = (ini_def.replace(day=28) + timedelta(days=5)).replace(day=15)

st.sidebar.header("🗓️ Filtro Periodo")
d_inizio = st.sidebar.date_input("Dal:", ini_def)
d_fine = st.sidebar.date_input("Al:", fine_def)

# --- DASHBOARD ECONOMICA ---
st.title("💰 Riepilogo Stipendio")
query_stats = f"""
    SELECT l.nome as Lavoro, SUM(s.ore_decimali) as tot_ore
    FROM lavori l LEFT JOIN sessioni s ON s.lavoro_id = l.id 
    WHERE s.data BETWEEN '{d_inizio}' AND '{d_fine}' GROUP BY l.nome
"""
stats = pd.read_sql_query(query_stats, conn)

if not stats.empty and stats['tot_ore'].sum() > 0:
    cols = st.columns(len(stats))
    for i, row in stats.iterrows():
        n = row['Lavoro']
        o = row['tot_ore'] if row['tot_ore'] else 0
        with cols[i]:
            if "mavriq" in n.lower():
                netto = (o * 8.60) * (1 - 0.1167)
                st.metric(n, format_durata(o), f"€ {netto:.2f} Netto")
            else:
                st.metric(n, format_durata(o), "Fisso Mensile")
else:
    st.info("Nessun dato in questo periodo.")

# --- LA TUA MAPPA DETTAGLIATA ---
st.divider()
st.subheader("🗺️ Mappa Dettagliata Orari")
query_mappa = f"""
    SELECT s.id, s.data, l.nome as Lavoro, s.ora_inizio, s.ora_fine, s.ore_decimali
    FROM sessioni s JOIN lavori l ON s.lavoro_id = l.id
    WHERE s.data BETWEEN '{d_inizio}' AND '{d_fine}' ORDER BY s.data DESC
"""
df_mappa = pd.read_sql_query(query_mappa, conn)

if not df_mappa.empty:
    df_mappa['Dettaglio'] = df_mappa['ora_inizio'] + " - " + df_mappa['ora_fine'] + " (" + df_mappa['ore_decimali'].apply(lambda x: f"{x:.2f}h") + ")"
    # Creiamo la vista "Mappa" che volevi
    mappa_vista = df_mappa.pivot_table(index='data', columns='Lavoro', values='Dettaglio', aggfunc=lambda x: ' / '.join(x)).fillna("-")
    st.dataframe(mappa_vista, use_container_width=True)
    
    # --- MODALITÀ ELIMINAZIONE ---
    with st.expander("🗑️ Clicca qui per ELIMINARE un orario errato"):
        st.write("Seleziona la riga da rimuovere:")
        selezione = st.selectbox("Turno da eliminare:", df_mappa['id'], 
                                 format_func=lambda x: f"ID {x}: {df_mappa[df_mappa['id']==x]['data'].values[0]} - {df_mappa[df_mappa['id']==x]['Lavoro'].values[0]} ({df_mappa[df_mappa['id']==x]['Dettaglio'].values[0]})")
        if st.button("CONFERMA ELIMINAZIONE"):
            conn.execute(f"DELETE FROM sessioni WHERE id = {selezione}")
            conn.commit()
            st.warning("Turno eliminato con successo!")
            st.rerun()

# --- REGISTRAZIONE ---
st.divider()
st.subheader("📝 Registra Nuovo Turno")
lavori_db = pd.read_sql_query("SELECT * FROM lavori", conn)
if not lavori_db.empty:
    with st.form("ins_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        lav = c1.selectbox("Lavoro:", lavori_db['nome'])
        g = c2.date_input("Giorno:", date.today())
        t1 = c3.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time())
        t2 = c3.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time())
        
        if st.form_submit_button("SALVA TURNO"):
            ore = (datetime.combine(date.today(), t2) - datetime.combine(date.today(), t1)).total_seconds() / 3600
            if ore > 0:
                id_l = lavori_db[lavori_db['nome'] == lav]['id'].values[0]
                conn.execute("INSERT INTO sessioni (lavoro_id, data, ora_inizio, ora_fine, ore_decimali) VALUES (?,?,?,?,?)",
                             (int(id_l), str(g), t1.strftime("%H:%M"), t2.strftime("%H:%M"), ore))
                conn.commit()
                st.success("Salvato!")
                st.rerun()
else:
    st.warning("Aggiungi un lavoro nella sidebar per iniziare.")
