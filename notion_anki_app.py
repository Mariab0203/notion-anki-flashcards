import streamlit as st
import json
import requests
from typing import List, Dict

# --- Função para extrair texto dos blocos da página JSON do Notion ---
def extract_page_text(page_json: dict) -> str:
    texts = []
    # Notion retorna blocos em "results"
    for block in page_json.get("results", []):
        # Nem todos os blocos tem texto, verificamos se tem tipo e texto
        if "type" in block and block.get(block["type"], {}).get("text"):
            texts.append("".join([t["plain_text"] for t in block[block["type"]]["text"]]))
    return "\n\n".join(texts)

# --- Função para gerar flashcards via OpenAI ---
def generate_flashcards_via_openai(text: str, openai_api_key: str) -> List[Dict]:
    import openai
    openai.api_key = openai_api_key

    prompt = f"""
Você é um gerador automático de flashcards. 
A partir do texto abaixo, gere flashcards no formato "Frente | Verso", separados por linhas.
Não gere mais que 15 flashcards.
Utilize informações detalhadas e relevantes.
Texto:
{text}
"""

    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=700,
            temperature=0.7,
            n=1,
            stop=None
        )
    except Exception as e:
        st.error(f"Erro na API OpenAI: {e}")
        return []

    raw_text = response.choices[0].text.strip()
    cards = []
    for line in raw_text.split("\n"):
        if "|" in line:
            front, back = line.split("|", 1)
            cards.append({"front": front.strip(), "back": back.strip()})
    return cards

# --- Função para enviar flashcards para o Anki via AnkiConnect ---
def send_to_anki(cards: List[Dict], deck_name: str = "Notion Flashcards") -> bool:
    endpoint = "http://localhost:8765"
    try:
        # Cria deck se não existir
        requests.post(endpoint, json={
            "action": "createDeck",
            "version": 6,
            "params": {"deck": deck_name}
        })

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
        if result.get("error") is None:
            return True
        else:
            st.error(f"Erro do AnkiConnect: {result.get('error')}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Não foi possível conectar ao Anki. Verifique se o Anki está aberto e o AnkiConnect está instalado e ativado.")
        return False

# --- Streamlit UI ---

st.set_page_config(page_title="Notion → Anki Flashcards", layout="centered")
st.title("Notion → Anki Flashcards (Automático + Sincronização)")

# Sidebar para chaves
openai_api_key = st.sidebar.text_input("Chave OpenAI", type="password", help="Sua API Key da OpenAI")
notion_api_key = st.sidebar.text_input("Token Notion (opcional)", type="password", help="Seu token Notion (opcional para importação direta)")
notion_database_id = st.sidebar.text_input("ID Database Notion (opcional)", help="ID do database Notion, se usar API direta")

# Upload múltiplo de arquivos JSON exportados do Notion
uploaded_files = st.file_uploader("Envie um ou mais arquivos JSON exportados do Notion", type=["json"], accept_multiple_files=True)

if "cards" not in st.session_state:
    st.session_state.cards = []

# Botão para gerar flashcards
if st.button("Gerar Flashcards via OpenAI"):
    if not openai_api_key:
        st.error("Insira sua chave OpenAI na barra lateral para gerar flashcards.")
    else:
        all_texts = []
        if uploaded_files:
            for file in uploaded_files:
                try:
                    page_json = json.load(file)
                    text = extract_page_text(page_json)
                    all_texts.append(text)
                except Exception as e:
                    st.warning(f"Erro ao ler arquivo {file.name}: {e}")
            full_text = "\n\n".join(all_texts)
        else:
            full_text = st.text_area("Ou cole o texto para gerar flashcards:", height=200)

        if full_text.strip():
            with st.spinner("Gerando flashcards..."):
                cards = generate_flashcards_via_openai(full_text, openai_api_key)
            if cards:
                st.session_state.cards = cards
                st.success(f"{len(cards)} flashcards gerados!")
            else:
                st.warning("Nenhum flashcard foi gerado. Tente com outro texto ou ajuste a API Key.")
        else:
            st.warning("Nenhum texto para processar.")

# Exibir flashcards gerados
if st.session_state.cards:
    st.subheader("Flashcards gerados")
    for idx, card in enumerate(st.session_state.cards):
        st.markdown(f"**Pergunta {idx+1}:** {card['front']}")
        st.markdown(f"**Resposta:** {card['back']}")
        st.markdown("---")

    # Botão para enviar ao Anki
    if st.button("Enviar flashcards para Anki"):
        with st.spinner("Enviando flashcards para Anki..."):
            success = send_to_anki(st.session_state.cards)
        if success:
            st.success("Flashcards enviados para o Anki com sucesso!")
        else:
            st.error("Falha ao enviar flashcards para o Anki.")

# Instruções
st.markdown("""
---
### Como usar:

1. Obtenha sua chave API da OpenAI (gratuita com créditos iniciais).
2. (Opcional) Insira token e ID do Notion se quiser integrar direto (funcionalidade futura).
3. Envie arquivos JSON exportados do Notion ou cole o texto manualmente.
4. Clique em "Gerar Flashcards via OpenAI" para criar os flashcards automaticamente.
5. Revise os flashcards gerados na tela.
6. Com o Anki aberto e o AnkiConnect instalado e ativado, clique em "Enviar flashcards para Anki" para sincronizar.
""")
