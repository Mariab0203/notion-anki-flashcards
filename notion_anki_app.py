import streamlit as st
import json
import requests
from typing import List, Dict

# --- Função para extrair texto simples de JSON da página do Notion (simplificada) ---
def extract_page_text(page_json: dict) -> str:
    # Extrai texto do json (exemplo simples, adaptar conforme estrutura do Notion)
    texts = []
    for block in page_json.get("results", []):
        if "type" in block and "text" in block[block["type"]]:
            texts.append("".join([t["plain_text"] for t in block[block["type"]]["text"]]))
    return "\n\n".join(texts)

# --- Função que usa OpenAI para gerar flashcards a partir do texto ---
def generate_flashcards_via_openai(text: str, openai_api_key: str) -> List[Dict]:
    import openai
    openai.api_key = openai_api_key
    prompt = f"""
    Gere flashcards no formato Front | Back a partir do texto abaixo.
    Separe Front e Back por '|'.
    Não gere mais que 15 flashcards.
    Use informações detalhadas.
    Texto: {text}
    """

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=700,
        temperature=0.7,
        n=1,
        stop=None
    )

    raw_text = response.choices[0].text.strip()
    cards = []
    for line in raw_text.split("\n"):
        if "|" in line:
            front, back = line.split("|", 1)
            cards.append({"front": front.strip(), "back": back.strip()})
    return cards

# --- Função para enviar flashcards ao Anki via AnkiConnect ---
def send_to_anki(cards: List[Dict], deck_name: str = "Notion Flashcards") -> bool:
    # AnkiConnect API endpoint
    endpoint = "http://localhost:8765"
    # Cria deck (ignorar erro se já existir)
    requests.post(endpoint, json={
        "action": "createDeck",
        "version": 6,
        "params": {"deck": deck_name}
    })

    # Monta notas para adicionar
    notes = []
    for card in cards:
        notes.append({
            "deckName": deck_name,
            "modelName": "Basic",
            "fields": {
                "Front": card["front"],
                "Back": card["back"]
            },
            "tags": ["notion"]
        })

    payload = {
        "action": "addNotes",
        "version": 6,
        "params": {"notes": notes}
    }
    response = requests.post(endpoint, json=payload)
    result = response.json()

    return "error" not in result or result["error"] is None

# --- Streamlit app ---

st.title("Notion → Anki Flashcards (Automático + Sincronização)")

openai_api_key = st.sidebar.text_input("Chave OpenAI", type="password")
notion_api_key = st.sidebar.text_input("Token Notion (para integração automática)", type="password")
notion_database_id = st.sidebar.text_input("ID Database Notion")

uploaded_files = st.file_uploader("Envie um ou mais JSONs de página do Notion", type=["json"], accept_multiple_files=True)

if "cards" not in st.session_state:
    st.session_state.cards = []

if st.button("Gerar Flashcards via OpenAI"):

    if not openai_api_key:
        st.error("Insira sua chave OpenAI na barra lateral")
    else:
        all_texts = []
        if uploaded_files:
            for file in uploaded_files:
                page_json = json.load(file)
                text = extract_page_text(page_json)
                all_texts.append(text)
            full_text = "\n\n".join(all_texts)
        else:
            full_text = st.text_area("Ou cole o texto para gerar flashcards:")

        if full_text.strip():
            cards = generate_flashcards_via_openai(full_text, openai_api_key)
            st.session_state.cards = cards
            st.success(f"{len(cards)} flashcards gerados!")
        else:
            st.warning("Nenhum texto para processar.")

if st.session_state.cards:
    st.subheader("Flashcards gerados")
    for idx, card in enumerate(st.session_state.cards):
        st.markdown(f"**Q{idx+1}:** {card['front']}")
        st.markdown(f"**A:** {card['back']}")
        st.markdown("---")

    if st.button("Enviar flashcards para Anki"):
        success = send_to_anki(st.session_state.cards)
        if success:
            st.success("Flashcards enviados para o Anki com sucesso!")
        else:
            st.error("Falha ao enviar flashcards para o Anki. Verifique se Anki e AnkiConnect estão rodando.")

st.markdown(
    """
    ---
    ### Como usar:
    1. Obtenha sua chave OpenAI e token do Notion na barra lateral.
    2. Envie JSONs exportados do Notion ou cole texto manualmente.
    3. Clique em 'Gerar Flashcards via OpenAI'.
    4. Revise os flashcards gerados.
    5. Clique em 'Enviar flashcards para Anki' para sincronizar (AnkiConnect deve estar ativo).
    """
)
