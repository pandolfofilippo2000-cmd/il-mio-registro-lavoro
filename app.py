import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="Il Mio Registro Lavoro", layout="wide")

# FUNZIONE PER CONNETTERSI E CREARE TABELLE SE MANCANO
def get_connection():
    conn = sqlite3.connect('registro_lavoro.db', check_same_thread=False)
    # Crea le tabelle se il database è nuovo (succede sempre su Streamlit Cloud)
    conn.execute('''CREATE TABLE IF NOT EXISTS lavori 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS sessioni 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, lavoro_id INTEGER, 
                     data TEXT, ore REAL, descrizione TEXT,
                     FOREIGN KEY (lavoro_id) REFERENCES lavori (id))''')
    conn.commit()
    return conn

st.title("💰 Il Mio Registro Lavoro")

# Apriamo la connessione in modo sicuro
conn = get_connection()

# Recupero lavori
lavori_df = pd.read_sql_query("SELECT id, nome FROM lavori", conn)

# --- SIDEBAR PER AGGIUNGERE LAVORI ---
st.sidebar.header("⚙️ Impostazioni")
nuovo_n = st.sidebar.text_input("Nuovo lavoro:")
if st.sidebar.button("Salva Lavoro"):
    if nuovo_n.strip():
        conn.execute("INSERT INTO lavori (nome) VALUES (?)", (nuovo_n.strip(),))
        conn.commit()
        st.rerun()

# --- DASHBOARD ---
if not lavori_df.empty:
    stats = pd.read_sql_query("""
        SELECT l.nome as Lavoro, SUM(s.ore) as dec_ore 
        FROM lavori l LEFT JOIN sessioni s ON s.lavoro_id = l.id 
        GROUP BY l.nome
    """, conn)
    
    col_m1, col_m2 = st.columns(2)
    for i, row in stats.iterrows():
        # ... (Logica calcolo paga Mavriq già vista)
        pass

    st.bar_chart(data=stats.fillna(0), x="Lavoro", y="dec_ore")
else:
    st.info("👋 Benvenuto! Aggiungi il tuo primo lavoro nella barra laterale per iniziare.")

# Chiudiamo la connessione alla fine del file
conn.close()
