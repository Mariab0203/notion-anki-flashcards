import streamlit as st
import json
from notion_client import Client
from notion_client.helpers import iterate_paginated_api
import csv
import io

st.set_page_config(page_title="Notion → Anki Flashcards", layout="wide")

# ---------------------------
# Utilitários para extrair texto do Notion
def extract_text_from_prop(prop):
    if prop["type"] == "title":
        return "".join([t["plain_text"] for t in prop["title"]])
    elif prop["type"] == "rich_text":
        return "".join([t["plain_text"] for t in prop["rich_text"]])
    elif prop["type"] == "select":
        return prop["select"]["name"] if prop["select"] else ""
    elif prop["type"] == "multi_select":
        return ", ".join([item["name"] for item in prop["multi_select"]])
    # Pode adicionar mais tipos conforme necessidade
    return ""

def extract_flashcards_from_notion_api(notion, database_id):
    flashcards = []
    try:
        pages = iterate_paginated_api(notion.databases.query, database_id=database_id)
    except Exception as e:
        st.error(f"Erro ao consultar API do Notion: {e}")
        return []

    for page in pages:
        props = page["properties"]
        front = ""
        back = ""
        tag = ""
        # Ajuste os nomes das propriedades conforme seu database Notion
        if "Question" in props and "Answer" in props:
            front = extract_text_from_prop(props["Question"])
            back = extract_text_from_prop(props["Answer"])
        else:
            # Se não tiver as propriedades esperadas, ignorar
            continue
        
        # Optional: pegar uma tag (pode ser nome da página, status, etc)
        if "Tags" in props:
            tag = extract_text_from_prop(props["Tags"])
        else:
            tag = "NotionAPI"
        
        flashcards.append({"front": front, "back": back, "tag": tag})
    return flashcards

def extract_flashcards_from_notion_data(data):
    # Aqui espera-se um JSON exportado do Notion. Depende do formato do seu arquivo.
    # Exemplo simplificado: buscar páginas e extrair blocos com Q/A

    flashcards = []

    def parse_block(block):
        # Extrai texto simples do bloco (pode ser melhorado para vários tipos)
        if "type" in block:
            if block["type"] == "toggle":
                # Pode ser Q/A no toggle, por exemplo
                q = block["toggle"]["text"][0]["plain_text"] if block["toggle"]["text"] else ""
                # Supondo que o conteúdo do toggle seja a resposta
                if "children" in block:
                    a = ""
                    for child in block["children"]:
                        a += child.get("text", [{"plain_text":""}])[0]["plain_text"]
                    return (q, a)
        return None

    # Dependendo do JSON exportado, a estrutura muda — adaptar conforme seu arquivo
    if "recordMap" in data and "block" in data["recordMap"]:
        blocks = data["recordMap"]["block"].values()
        for b in blocks:
            value = b.get("value", {})
            if value.get("type") == "toggle":
                question = "".join([t["plain_text"] for t in value.get("properties", {}).get("title", [[""]])[0]])
                # Para resposta, pegar filhos (children) e concatenar textos
                answer = ""
                # Aqui teria que navegar pelos filhos para pegar a resposta
                # Para simplificar, ignoramos filhos por enquanto
                flashcards.append({"front": question, "back": answer, "tag": "ManualUpload"})
    else:
        st.warning("Arquivo JSON não está no formato esperado do Notion export.")

    return flashcards

# ---------------------------
# Estado global no Streamlit

if "cards" not in st.session_state:
    st.session_state.cards = []

if "tags" not in st.session_state:
    st.session_state.tags = set()

if "filtered_tags" not in st.session_state:
    st.session_state.filtered_tags = set()

if "last_import_count" not in st.session_state:
    st.session_state.last_import_count = 0

# ---------------------------
# UI

st.title("📚 Notion → Anki Flashcards")

st.sidebar.header("Importar flashcards")

use_api = st.sidebar.checkbox("Importar via API do Notion (automático)", value=True)

if use_api:
    notion_token = st.sidebar.text_input("Token Secreto da API do Notion", type="password")
    database_id = st.sidebar.text_input("ID do Database/Página do Notion")

    if st.sidebar.button("Buscar Flashcards via API"):
        if not notion_token or not database_id:
            st.sidebar.warning("Informe token e ID do database/página.")
        else:
            with st.spinner("Consultando Notion API..."):
                try:
                    notion = Client(auth=notion_token)
                    new_cards = extract_flashcards_from_notion_api(notion, database_id)
                    if new_cards:
                        st.session_state.cards.extend(new_cards)
                        st.session_state.tags.update([c["tag"] for c in new_cards if c["tag"]])
                        st.session_state.last_import_count = len(new_cards)
                        st.success(f"✅ {len(new_cards)} flashcards importados via API!")
                    else:
                        st.warning("Nenhum flashcard encontrado na API.")
                except Exception as e:
                    st.error(f"Erro ao acessar API do Notion: {e}")
else:
    uploaded_file = st.sidebar.file_uploader("Upload arquivo JSON exportado do Notion", type=["json"])
    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            new_cards = extract_flashcards_from_notion_data(data)
            if new_cards:
                st.session_state.cards.extend(new_cards)
                st.session_state.tags.update([c["tag"] for c in new_cards if c["tag"]])
                st.session_state.last_import_count = len(new_cards)
                st.success(f"✅ {len(new_cards)} flashcards importados do arquivo!")
            else:
                st.warning("Nenhum flashcard encontrado no arquivo.")
        except Exception as e:
            st.error(f"Erro ao processar arquivo JSON: {e}")

if st.sidebar.button("Limpar flashcards importados"):
    st.session_state.cards = []
    st.session_state.tags = set()
    st.session_state.filtered_tags = set()
    st.session_state.last_import_count = 0
    st.success("Flashcards limpos.")

# ---------------------------
# Mostrar flashcards

st.markdown(f"### Flashcards importados: {len(st.session_state.cards)} (Última importação: {st.session_state.last_import_count})")

if st.session_state.tags:
    st.sidebar.header("Filtrar por Tags")
    selected_tags = st.sidebar.multiselect("Selecione tags para filtrar", options=sorted(st.session_state.tags))
else:
    selected_tags = []

def filter_cards_by_tags(cards, tags):
    if not tags:
        return cards
    return [c for c in cards if c.get("tag") in tags]

cards_to_show = filter_cards_by_tags(st.session_state.cards, selected_tags)

if cards_to_show:
    for i, card in enumerate(cards_to_show, start=1):
        st.markdown(f"**{i}. Pergunta:** {card['front']}")
        st.markdown(f"**Resposta:** {card['back']}")
        st.markdown(f"*Tag: {card['tag']}*")
        st.markdown("---")
else:
    st.info("Nenhum flashcard para mostrar com os filtros atuais.")

# ---------------------------
# Exportar para CSV (Anki)

def convert_to_csv(cards):
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t')
    writer.writerow(["Front", "Back", "Tag"])  # header opcional
    for card in cards:
        writer.writerow([card["front"], card["back"], card["tag"]])
    return output.getvalue()

if cards_to_show:
    csv_data = convert_to_csv(cards_to_show)
    st.download_button(
        label="⬇️ Exportar flashcards para CSV (Anki)",
        data=csv_data,
        file_name="flashcards_anki.csv",
        mime="text/csv"
    )
