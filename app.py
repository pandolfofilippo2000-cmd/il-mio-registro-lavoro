import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Gestione Stipendio Mavriq", layout="wide")

# --- DATABASE SETUP ---
def get_connection():
    conn = sqlite3.connect('registro_lavoro.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS lavori (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sessioni (id INTEGER PRIMARY KEY AUTOINCREMENT, lavoro_id INTEGER, data TEXT, ore REAL)''')
    conn.commit()
    return conn

def format_durata(val):
    if pd.isna(val) or val is None: return "0,00 h"
    ore = int(val)
    minuti = int(round((val - ore) * 60))
    return f"{ore},{minuti:02d} h"

# --- LOGICA PERIODO 16 - 15 ---
def get_periodo_stipendio(oggi):
    # Se oggi è <= 15, il periodo è dal 16 del mese scorso al 15 di questo mese
    if oggi.day <= 15:
        fine = date(oggi.year, oggi.month, 15)
        inizio = (fine.replace(day=1) - timedelta(days=1)).replace(day=16)
    else:
        # Se oggi è > 15, il periodo è dal 16 di questo mese al 15 del prossimo
        inizio = date(oggi.year, oggi.month, 16)
        prossimo_mese = (inizio.replace(day=28) + timedelta(days=5)).replace(day=15)
        fine = prossimo_mese
    return inizio, fine

conn = get_connection()
st.title("💰 Dashboard Mavriq & Co.")

# --- SIDEBAR: BACKUP DATI (MEMORIA) ---
st.sidebar.header("💾 Memoria & Backup")
with st.sidebar.expander("Esporta/Importa Dati"):
    # Esporta
    if st.button("Scarica Backup"):
        df_backup = pd.read_sql_query("SELECT * FROM sessioni", conn)
        st.download_button("Clicca qui per scaricare", df_backup.to_csv(index=False), "backup_lavoro.csv", "text/csv")
    
    # Importa
    file_caricato = st.file_uploader("Carica un backup per ripristinare", type="csv")
    if file_caricato:
        df_import = pd.read_csv(file_caricato)
        df_import.to_sql("sessioni", conn, if_exists="replace", index=False)
        st.success("Dati ripristinati!")

# --- FILTRO PERIODO ---
st.sidebar.divider()
st.sidebar.header("🗓️ Filtro Stipendio")
inizio_default, fine_default = get_periodo_stipendio(date.today())
data_inizio = st.sidebar.date_input("Inizio Periodo:", inizio_default)
data_fine = st.sidebar.date_input("Fine Periodo:", fine_default)

# --- CALCOLO RETRIBUZIONE ---
st.subheader(f"📊 Riepilogo dal {data_inizio.strftime('%d/%m')} al {data_fine.strftime('%d/%m')}")

query = f"""
    SELECT l.nome as Lavoro, SUM(s.ore) as ore_tot
    FROM lavori l 
    LEFT JOIN sessioni s ON s.lavoro_id = l.id 
    WHERE s.data BETWEEN '{data_inizio}' AND '{data_fine}'
    GROUP BY l.nome
"""
stats = pd.read_sql_query(query, conn)

if not stats.empty:
    cols = st.columns(len(stats))
    for i, row in stats.iterrows():
        nome = row['Lavoro']
        ore = row['ore_tot'] if row['ore_tot'] else 0
        
        if "mavriq" in nome.lower():
            # 8,60€ lordi - 11,67% tasse
            netto = (ore * 8.60) * (1 - 0.1167)
            with cols[i]:
                st.metric(label=f"🏗️ {nome}", value=format_durata(ore), delta=f"€ {netto:.2f} Netto")
        else:
            with cols[i]:
                st.metric(label=f"💼 {nome}", value=format_durata(ore), delta="Fisso Mensile")
    
    st.bar_chart(stats, x="Lavoro", y="ore_tot")

# --- INSERIMENTO ---
st.divider()
with st.form("nuovo_turno"):
    lavori_df = pd.read_sql_query("SELECT id, nome FROM lavori", conn)
    scelta = st.selectbox("Lavoro:", lavori_df['nome']) if not lavori_df.empty else st.info("Aggiungi un lavoro nella sidebar")
    col_t1, col_t2 = st.columns(2)
    t_in = col_t1.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time())
    t_fi = col_t2.time_input("Fine:", datetime.strptime("17:00", "%H:%M").time())
    giorno = st.date_input("Giorno:", date.today())
    
    if st.form_submit_button("REGISTRA"):
        if not lavori_df.empty:
            ore = (datetime.combine(date.today(), t_fi) - datetime.combine(date.today(), t_in)).total_seconds() / 3600
            id_l = lavori_df[lavori_df['nome'] == scelta]['id'].values[0]
            conn.execute("INSERT INTO sessioni (lavoro_id, data, ore) VALUES (?, ?, ?)", (int(id_l), giorno, ore))
            conn.commit()
            st.rerun()

# --- GESTIONE LAVORI (SIDEBAR) ---
with st.sidebar.expander("➕ Gestisci Nomi Lavori"):
    nuovo = st.text_input("Nuovo nome:")
    if st.button("Aggiungi"):
        conn.execute("INSERT INTO lavori (nome) VALUES (?)", (nuovo,))
        conn.commit()
        st.rerun()
