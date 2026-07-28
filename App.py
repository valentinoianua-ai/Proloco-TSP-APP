import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import urllib.parse
import warnings
import os

warnings.filterwarnings('ignore')

# ==========================================
# 1. CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(
    page_title="Gestione Cene Proloco",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# CSS per mobile
st.markdown("""
    <style>
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        font-size: 16px !important;
    }
    .stButton > button {
        width: 100%;
        font-size: 18px !important;
        padding: 12px 0 !important;
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONNESSIONE DINAMICA (URL dai secrets)
# ==========================================
@st.cache_data(ttl=10)
def load_config():
    # Legge l'URL del foglio dai secrets (o da variabile d'ambiente per test locale)
    spreadsheet_url = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet")
    
    if not spreadsheet_url:
        # Fallback per test locale
        spreadsheet_url = os.getenv("GOOGLE_SHEET_URL", "https://docs.google.com/spreadsheets/d/1OYaACNDPfz1TSaKtC1lHNVPKhFH053CR5937zQCLJAs/edit")
    
    conn = st.connection("gsheets", type=GSheetsConnection, spreadsheet=spreadsheet_url)
    
    try:
        df_raw = conn.read(worksheet="CONFIG", header=None, ttl=10)
        
        config_dict = {}
        for _, row in df_raw.iterrows():
            key = str(row[0]).strip().lower() if pd.notna(row[0]) else ""
            val = row[1]
            if key and key != "nan":
                config_dict[key] = val

        nome_evento = str(config_dict.get("nome evento", "CENA IN BIANCO")).upper()
        prezzo_adulto = float(str(config_dict.get("prezzo adulto", 60)).replace(',', '.'))
        prezzo_bambino = float(str(config_dict.get("prezzo bambino", 25)).replace(',', '.'))
        caparra_adulto = float(str(config_dict.get("caparra per persona adulta", 30)).replace(',', '.'))
        caparra_bambino = float(str(config_dict.get("caparra per persona bambino", 15)).replace(',', '.'))
        posti_totali = int(str(config_dict.get("posti totali sala", 80)).replace(',', '.'))
        
        raw_data = config_dict.get("data evento", "01/01/2026")
        data_evento = raw_data.strftime("%d/%m/%Y") if isinstance(raw_data, datetime) else str(raw_data)

        dict_operatori = {}
        op_indices = df_raw[df_raw[0].str.lower().str.contains("operatori", na=False)].index
        if len(op_indices) > 0:
            start_idx = op_indices[0] + 1
            df_ops = df_raw.iloc[start_idx:].dropna(subset=[0])
            for _, row in df_ops.iterrows():
                op_name = str(row[0]).strip()
                pin_val = str(row[1]).strip() if pd.notna(row[1]) else ""
                if op_name and op_name.lower() != "nan":
                    dict_operatori[op_name] = pin_val

        return {
            "NOME_EVENTO": nome_evento,
            "PREZZO_ADULTO": prezzo_adulto,
            "PREZZO_BAMBINO": prezzo_bambino,
            "CAPARRA_ADULTO": caparra_adulto,
            "CAPARRA_BAMBINO": caparra_bambino,
            "DATA_EVENTO": data_evento,
            "POSTI_TOTALI": posti_totali,
            "OPERATORI_PIN": dict_operatori
        }
    except Exception as e:
        st.error(f"Errore critico nel caricamento del foglio CONFIG: {e}")
        st.stop()

CONFIG = load_config()

# ==========================================
# 3. GESTIONE STATO SESSIONE
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "operatore" not in st.session_state:
    st.session_state.operatore = ""
if "last_booking" not in st.session_state:
    st.session_state.last_booking = None

# ==========================================
# 4. SCHERMATA DI LOGIN
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #41AD49;'>🍷 Nuova Proloco TSP</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #6c757d;'>Cassa & Prenotazioni</h4>", unsafe_allow_html=True)
    st.write("")
    
    lista_operatori = list(CONFIG["OPERATORI_PIN"].keys())
    
    with st.form("login_form"):
        operatore_sel = st.selectbox("👤 Seleziona Operatore", [""] + lista_operatori)
        pin_sel = st.text_input("🔑 PIN di Accesso (se previsto)", type="password")
        btn_login = st.form_submit_button("🔒 Accedi", use_container_width=True)
        
        if btn_login:
            if not operatore_sel:
                st.error("Seleziona un operatore.")
            else:
                pin_corretto = CONFIG["OPERATORI_PIN"].get(operatore_sel, "")
                # Se il PIN è configurato, deve corrispondere. Se è vuoto, accetta qualsiasi cosa (o vuoto)
                if pin_corretto and pin_sel.strip() != str(pin_corretto):
                    st.error("PIN errato.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.operatore = operatore_sel
                    st.rerun()

# ==========================================
# 5. DASHBOARD PRENOTAZIONI
# ==========================================
else:
    # Header
    col_head1, col_head2 = st.columns([3, 1])
    with col_head1:
        st.title(f"🍽️ {CONFIG['NOME_EVENTO']}")
        st.caption(f"📅 {CONFIG['DATA_EVENTO']}")
    with col_head2:
        st.write(f"**{st.session_state.operatore}**")
        if st.button("🚪 Esci", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.operatore = ""
            st.session_state.last_booking = None
            st.rerun()

    st.divider()

    # --- MESSAGGIO DI SUCCESSO POST-PRENOTAZIONE ---
    if st.session_state.last_booking:
        bk = st.session_state.last_booking
        st.markdown(f"""
            <div class="success-box">
                <h3>✅ Prenotazione Registrata!</h3>
                <p><b>{bk['nome']} {bk['cognome']}</b> ({bk['persone']} persone)</p>
                <p>Codice: <b>{bk['cod_fam']}</b></p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f'''
            <a href="{bk['url_wa']}" target="_blank" style="text-decoration:none;">
                <div style="background-color:#25D366;color:white;padding:14px;border-radius:8px;text-align:center;font-weight:bold;font-size:18px;margin-bottom:20px;">
                    📲 Invia Conferma WhatsApp
                </div>
            </a>
        ''', unsafe_allow_html=True)
        
        if st.button("➕ Nuova Prenotazione", use_container_width=True):
            st.session_state.last_booking = None
            st.rerun()
        st.divider()

    # --- FORM PRENOTAZIONE ---
    st.subheader("✍️ Nuova Prenotazione")

    # Controllo Capienza Dinamico PRIMA di mostrare il form
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_prenotazioni = conn.read(worksheet="PRENOTAZIONI", ttl=10)
        if not df_prenotazioni.empty and "Persone" in df_prenotazioni.columns and "Stato" in df_prenotazioni.columns:
            df_prenotazioni["Stato"] = df_prenotazioni["Stato"].fillna("")
            posti_ocupati = int(df_prenotazioni[df_prenotazioni["Stato"].str.contains("Confermata", na=False)]["Persone"].sum())
        else:
            posti_ocupati = 0
    except Exception:
        posti_ocupati = 0

    posti_rimanenti = CONFIG["POSTI_TOTALI"] - posti_ocupati
    st.info(f"📊 Posti disponibili in sala: **{posti_rimanenti}** su {CONFIG['POSTI_TOTALI']}")

    if posti_rimanenti <= 0:
        st.error("🚫 **SALA COMPLETA!** Non è possibile accettare nuove prenotazioni.")
        st.stop()

    with st.form("prenotazione_form", clear_on_submit=True):
        # Layout a 2 colonne su PC, si impila automaticamente su smartphone
        col1, col2 = st.columns(2)
        with col1:
            cognome = st.text_input("Cognome *", max_chars=30)
            telefono = st.text_input("Telefono / WhatsApp *", max_chars=15)
            adulti = st.number_input(f"Adulti (€{CONFIG['PREZZO_ADULTO']:.0f})", min_value=0, value=1, step=1)
        with col2:
            nome = st.text_input("Nome *", max_chars=30)
            email = st.text_input("Email (Opzionale)", max_chars=40)
            bambini = st.number_input(f"Bambini (€{CONFIG['PREZZO_BAMBINO']:.0f})", min_value=0, value=0, step=1)

        st.divider()

        nuovi_partecipanti = adulti + bambini
        
        # Controllo capienza sul numero inserito nel form
        if nuovi_partecipanti > posti_rimanenti:
            st.warning(f"⚠️ Attenzione: richiedi {nuovi_partecipanti} posti, ma ne rimangono solo {posti_rimanenti}.")

        caparra_suggerita = (adulti * CONFIG["CAPARRA_ADULTO"]) + (bambini * CONFIG["CAPARRA_BAMBINO"])
        
        col3, col4 = st.columns(2)
        with col3:
            blocchetto = st.text_input("N° Ricevuta/Blocchetto *", placeholder="Es. 045")
            metodo_pagamento = st.selectbox("Pagamento Caparra", ["Contanti", "POS/Carta", "Bonifico"])
        with col4:
            caparra_versata = st.number_input("Caparra Incassata (€)", min_value=0.0, value=float(caparra_suggerita), step=0.5)
            note = st.text_input("Note / Intolleranze", placeholder="Es. Celiaco")

        st.info(f"💡 Caparra Consigliata: **€ {caparra_suggerita:.2f}**")

        btn_salva = st.form_submit_button("💾 Salva Prenotazione", use_container_width=True, type="primary")

        if btn_salva:
            if not cognome or not nome or not telefono or not blocchetto:
                st.error("⚠️ Compila tutti i campi obbligatori (*).")
            elif nuovi_partecipanti <= 0:
                st.error("⚠️ Inserisci almeno un partecipante.")
            elif nuovi_partecipanti > posti_rimanenti:
                st.error(f"⚠️ Posti insufficienti! Rimangono solo {posti_rimanenti} posti.")
            else:
                try:
                    # 1. Prepara i dati
                    cod_fam = "FAM-" + str(uuid.uuid4())[:5].upper()
                    costo_totale = (adulti * CONFIG["PREZZO_ADULTO"]) + (bambini * CONFIG["PREZZO_BAMBINO"])
                    saldo = costo_totale - caparra_versata
                    data_ora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                    nuova_riga_pren = pd.DataFrame([{
                        "Cod.Fam.": cod_fam,
                        "N°": "",
                        "Data": data_ora,
                        "Cognome": cognome.strip().title(),
                        "Nome": nome.strip().title(),
                        "Telefono": telefono.strip(),
                        "Adulti": int(adulti),
                        "Bambini": int(bambini),
                        "Persone": int(nuovi_partecipanti),
                        "Caparra Dovuta": float(caparra_suggerita),
                        "Caparra Versata": float(caparra_versata),
                        "Saldo": float(saldo),
                        "Pagamento": metodo_pagamento,
                        "Tavolo": "Da assegnare",
                        "Stato": "Confermata",
                        "Note": note.strip().title(),
                        "N°.Biglietto": str(blocchetto).strip(),
                        "Operatore": st.session_state.operatore
                    }])

                    # 2. Scrivi su PRENOTAZIONI
                    df_prenotazioni = conn.read(worksheet="PRENOTAZIONI", ttl=10)
                    if df_prenotazioni.empty:
                        conn.update(worksheet="PRENOTAZIONI", data=nuova_riga_pren)
                    else:
                        df_agg = pd.concat([df_prenotazioni, nuova_riga_pren], ignore_index=True)
                        conn.update(worksheet="PRENOTAZIONI", data=df_agg)

                    # 3. Scrivi su LOGS
                    nuova_riga_log = pd.DataFrame([{
                        "Data/Ora": data_ora,
                        "Operatore": st.session_state.operatore,
                        "Azione": "NUOVA_PRENOTAZIONE",
                        "CodFam": cod_fam,
                        "Cliente": f"{cognome.strip().title()} {nome.strip().title()}",
                        "Caparra (€)": float(caparra_versata),
                        "Dettagli": f"Metodo: {metodo_pagamento} | Ad: {adulti}, Bam: {bambini}"
                    }])
                    try:
                        df_logs = conn.read(worksheet="LOGS", ttl=10)
                        if df_logs.empty:
                            conn.update(worksheet="LOGS", data=nuova_riga_log)
                        else:
                            df_log_agg = pd.concat([df_logs, nuova_riga_log], ignore_index=True)
                            conn.update(worksheet="LOGS", data=df_log_agg)
                    except Exception as log_err:
                        st.warning(f"Salvataggio prenotazione riuscito, ma errore nel foglio LOGS: {log_err}")

                    # 4. Genera Link WhatsApp
                    tel_clean = ''.join(filter(str.isdigit, telefono))
                    if len(tel_clean) == 10:  # Se è un numero italiano senza prefisso
                        tel_clean = "39" + tel_clean
                    
                    msg_wa = (
                        f"*{CONFIG['NOME_EVENTO']} - PROLOCO TSP*\n"
                        f"🎟️ *Ricevuta N°:* {blocchetto}\n"
                        f"👤 *Intestata a:* {nome.strip().title()} {cognome.strip().title()}\n"
                        f"👥 *Partecipanti:* {adulti} Adulti, {bambini} Bambini\n"
                        f"💶 *Caparra Versata:* €{caparra_versata:.2f} ({metodo_pagamento})\n"
                        f"📌 *Codice Prenotazione:* {cod_fam}\n\n"
                        f"Conservi questo messaggio. Ci vediamo il {CONFIG['DATA_EVENTO']}!"
                    )
                    url_wa = f"https://api.whatsapp.com/send?phone={tel_clean}&text={urllib.parse.quote(msg_wa)}"

                    # 5. Aggiorna stato sessione e ricarica
                    st.session_state.last_booking = {
                        "nome": nome.strip().title(),
                        "cognome": cognome.strip().title(),
                        "persone": nuovi_partecipanti,
                        "cod_fam": cod_fam,
                        "url_wa": url_wa
                    }
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Errore durante il salvataggio: {e}")
