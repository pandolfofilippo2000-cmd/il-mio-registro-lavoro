import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="Gestione Lavori & Guadagni", layout="wide")

# FUNZIONE PER CONNETTERSI AL DATABASE
def get_connection():
    return sqlite3.connect('registro_lavoro.db', check_same_thread=False)

# FUNZIONE PER FORMATTARE LE ORE (es. 4,30 h)
def format_durata(val):
    if pd.isna(val) or val is None: return "0,00 h"
    ore = int(val)
    minuti = int(round((val - ore) * 60))
    return f"{ore},{minuti:02d} h"

st.title("💰 Il Mio Registro Lavoro")

# --- RECUPERO DATI ---
conn = get_connection()
lavori_df = pd.read_sql_query("SELECT id, nome FROM lavori", conn)

# --- SIDEBAR PER GESTIONE ---
st.sidebar.header("⚙️ Impostazioni")
with st.sidebar.expander("➕ Aggiungi/Gestisci Lavori"):
    nuovo_n = st.text_input("Nuovo lavoro:")
    if st.button("Salva Nuovo"):
        if nuovo_n.strip():
            conn.execute("INSERT INTO lavori (nome) VALUES (?)", (nuovo_n.strip(),))
            conn.commit()
            st.rerun()

# --- AREA DASHBOARD (METRICHE E GRAFICO) ---
st.subheader("📊 Riepilogo Attuale")
stats = pd.read_sql_query("""
    SELECT l.nome as Lavoro, SUM(s.ore) as dec_ore 
    FROM lavori l LEFT JOIN sessioni s ON s.lavoro_id = l.id 
    GROUP BY l.nome
""", conn)

if not stats.empty and stats['dec_ore'].sum() > 0:
    col_m1, col_m2 = st.columns(2)
    for i, row in stats.iterrows():
        nome_lav = row['Lavoro']
        ore_tot = row['dec_ore'] if not pd.isna(row['dec_ore']) else 0
        
        with (col_m1 if i % 2 == 0 else col_m2):
            if "mavriq" in nome_lav.lower():
                netto = (ore_tot * 8.60) * (1 - 0.1167)
                st.metric(label=f"🏗️ {nome_lav}", value=format_durata(ore_tot), delta=f"€ {netto:.2f} Netto")
            else:
                st.metric(label=f"💼 {nome_lav}", value=format_durata(ore_tot), delta="Fisso Mensile")
    
    # IL GRAFICO CHE ERA SPARITO
    st.bar_chart(data=stats.fillna(0), x="Lavoro", y="dec_ore")
else:
    st.info("Nessun dato registrato. Inserisci un turno per vedere il grafico!")

# --- INSERIMENTO DATI ---
st.divider()
c1, c2 = st.columns([1, 2])

with c1:
    st.subheader("📝 Registra Turno")
    if not lavori_df.empty:
        with st.form("form_registro", clear_on_submit=True):
            lav_sel = st.selectbox("Lavoro:", lavori_df['nome'])
            data_sel = st.date_input("Data:", date.today())
            t_in = st.time_input("Inizio:", datetime.strptime("09:00", "%H:%M").time())
            t_fi = st.time_input("Fine:", datetime.strptime("13:00", "%H:%M").time())
            nota = st.text_input("Note:")
            
            if st.form_submit_button("REGISTRA"):
                d_in = datetime.combine(date.today(), t_in)
                d_fi = datetime.combine(date.today(), t_fi)
                ore_dec = (d_fi - d_in).total_seconds() / 3600
                
                if ore_dec > 0:
                    id_l = lavori_df[lavori_df['nome'] == lav_sel]['id'].values[0]
                    conn.execute("INSERT INTO sessioni (lavoro_id, data, ore, descrizione) VALUES (?, ?, ?, ?)",
                                 (int(id_l), data_sel, ore_dec, nota))
                    conn.commit() # <--- QUESTO SALVA I DATI PER SEMPRE
                    st.success("Salvato!")
                    st.rerun()

with c2:
    st.subheader("📅 Ultime Sessioni")
    cron = pd.read_sql_query("""
        SELECT s.data as Data, l.nome as Lavoro, s.ore as dec_ore, s.descrizione as Note
        FROM sessioni s JOIN lavori l ON s.lavoro_id = l.id ORDER BY s.data DESC LIMIT 10
    """, conn)
    if not cron.empty:
        cron['Durata'] = cron['dec_ore'].apply(format_durata)
        st.dataframe(cron[['Data', 'Lavoro', 'Durata', 'Note']], use_container_width=True)

conn.close()