import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import urllib.parse
import os

# Configurazione Pagina
st.set_page_config(
    page_title="Gestione Cene Proloco",
    page_icon="🍷",
    layout="centered"
)

# Connessione a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# 🔄 CARICAMENTO DINAMICO CONFIGURAZIONE
# ==========================================
@st.cache_data(ttl=0)  # ttl=0 garantisce che ogni modifica su Sheets sia subito recepita
def load_config():
    # Legge il foglio CONFIG senza intestazione per gestire la struttura mista
    df_raw = conn.read(worksheet="CONFIG", header=None, ttl=0)
    
    # 1. Parsing delle prime righe (Chiave-Valore)
    config_dict = {}
    for idx in range(min(8, len(df_raw))):
        key = str(df_raw.iloc[idx, 0]).strip()
        val = df_raw.iloc[idx, 1]
        config_dict[key] = val

    # Estrazione parametri con valori di default di sicurezza
    nome_evento = str(config_dict.get("Nome Evento", "CENA IN BIANCO"))
    prezzo_adulto = float(config_dict.get("Prezzo adulto", 60))
    prezzo_bambino = float(config_dict.get("Prezzo bambino", 25))
    caparra_adulto = float(config_dict.get("Caparra per persona adulta", 30))
    caparra_bambino = float(config_dict.get("Caparra per persona bambino", 15))
    
    # Gestione formattazione data
    raw_data_evento = config_dict.get("Data evento", "06/08/2026")
    if isinstance(raw_data_evento, datetime):
        data_evento = raw_data_evento.strftime("%d/%m/%Y")
    else:
        data_evento = str(raw_data_evento)

    # 2. Parsing Operatori e PIN (dalla riga 9 in poi)
    dict_operatori = {}
    # La riga 8 (indice 8 base 0) contiene la tabella "Operatori | PIN"
    for idx in range(9, len(df_raw)):
        op_name = df_raw.iloc[idx, 0]
        pin_val = df_raw.iloc[idx, 1]
        
        if pd.notna(op_name) and str(op_name).strip() != "":
            # Pulisce eventuale formattazione del PIN mantenendo 0 iniziali
            pin_str = str(pin_val).split('.')[0].strip() if pd.notna(pin_val) else ""
            # Se il PIN è tipo '0000', assicura che sia salvato correttamente
            if len(pin_str) < 4 and pin_str.isdigit():
                pin_str = pin_str.zfill(4)
            dict_operatori[str(op_name).strip()] = pin_str

    return {
        "NOME_EVENTO": nome_evento,
        "PREZZO_ADULTO": prezzo_adulto,
        "PREZZO_BAMBINO": prezzo_bambino,
        "CAPARRA_ADULTO": caparra_adulto,
        "CAPARRA_BAMBINO": caparra_bambino,
        "DATA_EVENTO": data_evento,
        "OPERATORI_PIN": dict_operatori
    }

# Carichiamo i dati di configurazione
try:
    CONFIG = load_config()
except Exception as e:
    st.error(f"Errore durante il caricamento del foglio CONFIG: {e}")
    st.stop()

# Gestione Sessione Login e Stato Ultima Prenotazione
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.operatore = ""

if "last_booking" not in st.session_state:
    st.session_state.last_booking = None

# --- LOGIN ---
if not st.session_state.logged_in:
    if os.path.exists("logo.png"):
        col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
        with col_logo2:
            st.image("logo.png", use_container_width=True)

    st.markdown("<h2 style='text-align: center; color: #41AD49; font-weight: bold;'>Nuova Proloco Torre San Patrizio</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #6c757d;'>Cassa & Prenotazioni Cene</h4>", unsafe_allow_html=True)
    st.write("")
    
    lista_operatori = list(CONFIG["OPERATORI_PIN"].keys())
    
    with st.form("login_form"):
        operatore_sel = st.selectbox("Seleziona Operatore / Esercente", [""] + lista_operatori)
        pin_sel = st.text_input("PIN di Accesso", type="password")
        btn_login = st.form_submit_button("🔒 Accedi alla Cassa", use_container_width=True)
        
        if btn_login:
            pin_corretto = CONFIG["OPERATORI_PIN"].get(operatore_sel, None)
            
            if not operatore_sel:
                st.error("Seleziona un operatore prima di continuare.")
            elif pin_sel.strip() != str(pin_corretto):
                st.error("PIN errato per l'operatore selezionato.")
            else:
                st.session_state.logged_in = True
                st.session_state.operatore = operatore_sel
                st.rerun()

# --- CASSA PRENOTAZIONI ---
else:
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title(f"🍽️ {CONFIG['NOME_EVENTO']}")
        st.caption(f"📅 Data Evento: {CONFIG['DATA_EVENTO']}")
    with col_head2:
        st.write(f"👤 **{st.session_state.operatore}**")
        if st.button("Esci / Logout"):
            st.session_state.logged_in = False
            st.session_state.operatore = ""
            st.session_state.last_booking = None
            st.rerun()

    st.divider()

    # Mostra messaggio di successo e bottone WhatsApp per l'ultima prenotazione
    if st.session_state.last_booking:
        bk = st.session_state.last_booking
        st.success(f"✅ Prenotazione per **{bk['nome']} {bk['cognome']}** registrata con successo!")
        
        st.markdown(f'''
            <a href="{bk['url_wa']}" target="_blank" style="text-decoration:none;">
                <div style="background-color:#25D366;color:white;padding:12px;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:20px;">
                    📲 Invia Conferma WhatsApp a {bk['nome']} ({bk['telefono']})
                </div>
            </a>
        ''', unsafe_allow_html=True)
        
        if st.button("➕ Nuova Operazione"):
            st.session_state.last_booking = None
            st.rerun()

    st.subheader("✍️ Nuova Prenotazione")

    with st.form("prenotazione_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            cognome = st.text_input("Cognome *")
            telefono = st.text_input("Telefono / WhatsApp *")
            adulti = st.number_input(f"N° Adulti (€{CONFIG['PREZZO_ADULTO']:.2f})", min_value=0, value=1, step=1)
        with col2:
            nome = st.text_input("Nome *")
            email = st.text_input("Email (Opzionale)")
            bambini = st.number_input(f"N° Bambini (€{CONFIG['PREZZO_BAMBINO']:.2f})", min_value=0, value=0, step=1)

        st.divider()

        caparra_suggerita = (adulti * CONFIG["CAPARRA_ADULTO"]) + (bambini * CONFIG["CAPARRA_BAMBINO"])
        
        col3, col4 = st.columns(2)
        with col3:
            blocchetto = st.text_input("N° Blocchetto / Ricevuta *", placeholder="Es. N° 045")
            metodo_pagamento = st.selectbox("Metodo Pagamento", ["Contanti", "POS/Carta", "Bonifico"])
        with col4:
            caparra_versata = st.number_input("Caparra Incassata (€)", min_value=0.0, value=float(caparra_suggerita), step=0.5)
            note = st.text_input("Note / Intolleranze", placeholder="Es. Vegetariano")

        st.info(f"💡 Caparra Consigliata: **€ {caparra_suggerita:.2f}**")

        btn_salva = st.form_submit_button("💾 Salva e Registra Prenotazione", use_container_width=True)

        if btn_salva:
            if not cognome or not nome or not telefono or not blocchetto:
                st.error("Compila tutti i campi obbligatori (*).")
            elif (adulti + bambini) <= 0:
                st.error("Devi inserire almeno un partecipante (Adulto o Bambino).")
            else:
                try:
                    cod_fam = "FAM-" + str(uuid.uuid4())[:5].upper()
                    richiesti = adulti + bambini
                    caparra_dovuta = (adulti * CONFIG["CAPARRA_ADULTO"]) + (bambini * CONFIG["CAPARRA_BAMBINO"])
                    costo_totale = (adulti * CONFIG["PREZZO_ADULTO"]) + (bambini * CONFIG["PREZZO_BAMBINO"])
                    saldo = costo_totale - caparra_versata
                    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    # Mappatura dati
                    nuova_riga = pd.DataFrame([{
                        "Cod.Fam.": str(cod_fam),
                        "N°": "",
                        "Data": str(data_ora),
                        "Cognome": str(cognome).strip(),
                        "Nome": str(nome).strip(),
                        "Telefono": str(telefono).strip(),
                        "Adulti": int(adulti),
                        "Bambini": int(bambini),
                        "Persone": int(richiesti),
                        "Caparra Dovuta": float(caparra_dovuta),
                        "Caparra Versata": float(caparra_versata),
                        "Saldo": float(saldo),
                        "Pagamento": str(metodo_pagamento),
                        "Tavolo": "Da assegnare",
                        "Stato": "Confermata",
                        "Note": str(note).strip(),
                        "N°.Biglietto": str(blocchetto).strip(),
                        "Operatore": str(st.session_state.operatore)
                    }])

                    # Lettura e Scrittura Google Sheets
                    df_esistente = conn.read(worksheet="PRENOTAZIONI", ttl=0)
                    df_aggiornato = pd.concat([df_esistente, nuova_riga], ignore_index=True)
                    conn.update(worksheet="PRENOTAZIONI", data=df_aggiornato)

                    # Formattazione Numero di Telefono per WhatsApp
                    tel_clean = ''.join(filter(str.isdigit, telefono))
                    if len(tel_clean) == 10:
                        tel_clean = "39" + tel_clean

                    msg_wa = (
                        f"*{CONFIG['NOME_EVENTO'].upper()} - PROLOCO*\n"
                        f"*Ricevuta Prenotazione*\n\n"
                        f"Gentile *{nome.strip()} {cognome.strip()}*,\n"
                        f"Confermiamo la prenotazione effettuata presso *{st.session_state.operatore}*.\n\n"
                        f"📌 *Codice:* {cod_fam}\n"
                        f"🎟️ *Ricevuta N°:* {blocchetto}\n"
                        f"👥 *Partecipanti:* {adulti} Adulti, {bambini} Bambini\n"
                        f"💶 *Caparra Versata:* €{caparra_versata:.2f}\n\n"
                        f"Conservi questo messaggio. Ci vediamo alla serata!"
                    )
                    url_wa = f"https://api.whatsapp.com/send?phone={tel_clean}&text={urllib.parse.quote(msg_wa)}"

                    st.session_state.last_booking = {
                        "nome": nome,
                        "cognome": cognome,
                        "telefono": telefono,
                        "url_wa": url_wa
                    }
                    st.rerun()

                except Exception as e:
                    st.error(f"Errore durante il salvataggio sul Google Sheet: {e}")
