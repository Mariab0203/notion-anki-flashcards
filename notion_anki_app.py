import streamlit as st
import requests
import json
from typing import List, Dict

# --- Funções de extração e geração ---

def extract_page_text(page_json: dict) -> str:
    """
    Extrai texto de uma página JSON do Notion de forma robusta.
    """
    texts = []
    try:
        for block in page_json.get("results", []):
            block_type = block.get("type")
            if not block_type:
                continue
            text_objs = block.get(block_type, {}).get("text", [])
            if not text_objs:
                continue
            texts.append("".join([t.get("plain_text", "") for t in text_objs]))
    except Exception as e:
        st.warning(f"Erro ao extrair texto do Notion: {e}")
    return "\n\n".join(texts)

def generate_flashcards_from_text(openai_api_key: str, text: str, max_cards=15) -> List[Dict[str, str]]:
    """
    Usa OpenAI para gerar flashcards a partir do texto. Limita a max_cards.
    """
    prompt = (
        f"Transforme o seguinte texto em flashcards no formato 'pergunta | resposta'. "
        f"Crie até {max_cards} flashcards com informações detalhadas:\n\n{text}"
    )
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "text-davinci-003",
        "prompt": prompt,
        "temperature": 0.7,
        "max_tokens": 1000,
        "n": 1,
        "stop": None
    }
    try:
        response = requests.post("https://api.openai.com/v1/completions", headers=headers, json=data)
        response.raise_for_status()
        completion = response.json()
        raw_text = completion["choices"][0]["text"].strip()
        cards = []
        for line in raw_text.split("\n"):
            if "|" in line and len(cards) < max_cards:
                front, back = line.split("|", 1)
                cards.append({"front": front.strip(), "back": back.strip()})
        if not cards:
            st.warning("Nenhum flashcard foi gerado pela OpenAI. Tente outro texto ou revise o conteúdo.")
        return cards
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro HTTP da OpenAI API: {e}")
        return []
    except Exception as e:
        st.error(f"Erro ao gerar flashcards: {e}")
        return []

# --- Funções para AnkiConnect ---

def send_to_anki(cards: List[Dict[str, str]], deck_name: str = "Notion Flashcards", tags: List[str] = []):
    """
    Envia flashcards para Anki via AnkiConnect.
    """
    if not cards:
        st.warning("Nenhum flashcard para enviar ao Anki.")
        return

    # Tenta criar deck (ignora erro se já existir)
    create_deck_payload = {
        "action": "createDeck",
        "version": 6,
        "params": {"deck": deck_name}
    }
    try:
        res_deck = requests.post("http://localhost:8765", json=create_deck_payload)
        res_deck.raise_for_status()
        deck_result = res_deck.json()
        if deck_result.get("error"):
            st.info(f"Deck pode já existir: {deck_result['error']}")
    except Exception as e:
        st.error(f"Erro ao criar deck no Anki: {e}")
        return

    # Adiciona notas
    added_count = 0
    for card in cards:
        note_payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": deck_name,
                    "modelName": "Basic",
                    "fields": {
                        "Front": card["front"],
                        "Back": card["back"]
                    },
                    "tags": tags
                }
            }
        }
        try:
            res_note = requests.post("http://localhost:8765", json=note_payload)
            res_note.raise_for_status()
            note_result = res_note.json()
            if note_result.get("error"):
                st.warning(f"Erro ao adicionar nota: {note_result['error']}")
            else:
                added_count += 1
        except Exception as e:
            st.error(f"Erro ao adicionar nota no Anki: {e}")
            return

    st.success(f"{added_count} flashcards adicionados ao deck '{deck_name}' com tags {tags}")

# --- Interface Streamlit ---

def main():
    st.title("Notion para Anki - Flashcards Automáticos")

    st.sidebar.header("Configurações")
    openai_api_key = st.sidebar.text_input("Chave API OpenAI", type="password")
    notion_token = st.sidebar.text_input("Token de Integração Notion", type="password")
    notion_page_id = st.sidebar.text_input("ID da Página do Notion")
    deck_name = st.sidebar.text_input("Nome do Deck Anki", value="Notion Flashcards")

    st.sidebar.markdown("""
    **Como obter o Token e o ID do Notion:**
    - Crie uma integração no Notion e copie o token secreto.
    - Compartilhe a página com essa integração.
    - Pegue o ID da página da URL do Notion (parte após https://www.notion.so/).
    """)

    # Área de upload alternativo (JSON exportado do Notion)
    uploaded_file = st.file_uploader("Ou envie arquivo JSON exportado da página Notion", type=["json"])

    if st.button("Gerar flashcards automaticamente"):
        if not openai_api_key:
            st.error("Por favor, insira a chave API da OpenAI.")
            return
        if notion_page_id and notion_token:
            # Busca dados da página do Notion via API
            headers = {
                "Authorization": f"Bearer {notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            url = f"https://api.notion.com/v1/blocks/{notion_page_id}/children?page_size=100"
            try:
                notion_response = requests.get(url, headers=headers)
                notion_response.raise_for_status()
                page_json = notion_response.json()
                page_text = extract_page_text(page_json)
            except Exception as e:
                st.error(f"Erro ao buscar dados do Notion: {e}")
                return
        elif uploaded_file:
            try:
                page_json = json.load(uploaded_file)
                page_text = extract_page_text(page_json)
            except Exception as e:
                st.error(f"Erro ao ler arquivo JSON: {e}")
                return
        else:
            st.error("Por favor, forneça a combinação Token + ID do Notion ou faça upload do arquivo JSON.")
            return

        if not page_text.strip():
            st.warning("Texto extraído está vazio. Verifique a página do Notion ou o arquivo enviado.")
            return

        with st.spinner("Gerando flashcards com OpenAI..."):
            cards = generate_flashcards_from_text(openai_api_key, page_text)

        if cards:
            st.session_state["cards"] = cards
            st.success(f"{len(cards)} flashcards gerados.")
            for i, card in enumerate(cards, 1):
                st.markdown(f"**Q{i}:** {card['front']}")
                st.markdown(f"**A{i}:** {card['back']}")
        else:
            st.warning("Nenhum flashcard gerado.")

    if "cards" in st.session_state and st.session_state["cards"]:
        if st.button("Enviar flashcards para Anki"):
            send_to_anki(st.session_state["cards"], deck_name, tags=[deck_name.replace(" ", "_")])

if __name__ == "__main__":
    main()
