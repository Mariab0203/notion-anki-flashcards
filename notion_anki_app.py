import streamlit as st
import json
import io
import csv

st.set_page_config(page_title="Notion to Anki Flashcards", layout="wide")

if "cards" not in st.session_state:
    st.session_state.cards = []

if "page" not in st.session_state:
    st.session_state.page = 1

if "tags" not in st.session_state:
    st.session_state.tags = set()

if "filtered_tags" not in st.session_state:
    st.session_state.filtered_tags = set()

def reset_app():
    st.session_state.cards = []
    st.session_state.page = 1
    st.session_state.tags = set()
    st.session_state.filtered_tags = set()

def extract_flashcards_from_notion(data):
    flashcards = []
    def recurse_blocks(blocks):
        for block in blocks:
            front = ""
            back = ""
            tag = "Notion"
            if "properties" in block and "title" in block["properties"]:
                front = block["properties"]["title"][0][0]
                back = block.get("content", "")
                flashcards.append({"front": front, "back": back, "tag": tag})
            if "children" in block:
                recurse_blocks(block["children"])
    if "blocks" in data:
        recurse_blocks(data["blocks"])
    return flashcards

with st.sidebar:
    st.header("1. Dados de Entrada")
    token = st.text_input("Token Notion (opcional)", type="password", help="Use seu token para buscar DB diretamente")
    db_id = st.text_input("Database ID Notion (opcional)", help="ID do banco de dados do Notion")
    uploaded_file = st.file_uploader("Ou envie arquivo JSON exportado do Notion", type=["json"])
    openai_key = st.text_input("OpenAI API Key (opcional)", type="password")

    st.markdown("---")
    st.header("2. Processar")

    if st.button("Importar do Notion (não implementado)"):
        st.warning("Importação via API ainda não disponível neste exemplo.")

    if uploaded_file:
        try:
            data = json.load(uploaded_file)
            cards_new = extract_flashcards_from_notion(data)
            if cards_new:
                st.session_state.cards.extend(cards_new)
                st.session_state.tags.update(set(card["tag"] for card in cards_new))
                st.success(f"{len(cards_new)} flashcards importados!")
            else:
                st.warning("Nenhum flashcard encontrado no arquivo.")
        except Exception as e:
            st.error(f"Erro ao processar arquivo JSON: {e}")

    st.markdown("---")
    st.header("3. Filtrar Flashcards")
    if st.session_state.tags:
        selected_tags = st.multiselect("Filtrar por tags", options=sorted(st.session_state.tags), default=sorted(st.session_state.filtered_tags or st.session_state.tags))
        st.session_state.filtered_tags = set(selected_tags)
    else:
        st.info("Sem flashcards para filtrar ainda.")

    st.markdown("---")
    st.header("4. Exportar / Limpar")
    if st.button("Limpar Tudo", key="clear"):
        reset_app()
        st.experimental_rerun()

    if st.session_state.cards:
        def generate_tsv(filtered_cards):
            output = io.StringIO()
            writer = csv.writer(output, delimiter="\t")
            writer.writerow(["Front", "Back", "Tag"])
            for card in filtered_cards:
                writer.writerow([card["front"], card["back"], card["tag"]])
            return output.getvalue()

        if st.session_state.filtered_tags:
            filtered_cards = [c for c in st.session_state.cards if c["tag"] in st.session_state.filtered_tags]
        else:
            filtered_cards = st.session_state.cards

        tsv_data = generate_tsv(filtered_cards)
        st.download_button("📥 Exportar flashcards (TSV)", data=tsv_data, file_name="flashcards_anki.txt", mime="text/tab-separated-values")
    else:
        st.info("Nenhum flashcard para exportar.")

st.title("Flashcards Gerados")

CARDS_PER_PAGE = 5

if st.session_state.cards:
    if st.session_state.filtered_tags:
        display_cards = [c for c in st.session_state.cards if c["tag"] in st.session_state.filtered_tags]
    else:
        display_cards = st.session_state.cards

    total_pages = max(1, (len(display_cards) - 1) // CARDS_PER_PAGE + 1)
    page = st.session_state.page

    if page > total_pages:
        st.session_state.page = total_pages
        page = total_pages

    start_idx = (page - 1) * CARDS_PER_PAGE
    end_idx = start_idx + CARDS_PER_PAGE

    st.write(f"Exibindo flashcards {start_idx+1} a {min(end_idx, len(display_cards))} de {len(display_cards)}")

    for i, card in enumerate(display_cards[start_idx:end_idx], start=start_idx+1):
        st.markdown(
            f"""
            <div style='
                border: 1px solid #ddd; 
                padding: 15px; 
                margin-bottom: 10px; 
                border-radius: 8px;
                background-color: #f9f9f9;'>
                <strong>{i}. Pergunta:</strong> {card['front']}<br>
                <strong>Resposta:</strong> {card['back']}<br>
                <small>🏷️ Tag: <code>{card['tag']}</code></small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        if st.button("⬅️ Anterior") and page > 1:
            st.session_state.page -= 1
            st.experimental_rerun()
    with col2:
        st.markdown(f"<center>Página {page} de {total_pages}</center>", unsafe_allow_html=True)
    with col3:
        if st.button("Próximo ➡️") and page < total_pages:
            st.session_state.page += 1
            st.experimental_rerun()
else:
    st.info("Nenhum flashcard gerado ou importado ainda.")
