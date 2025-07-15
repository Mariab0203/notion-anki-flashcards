import streamlit as st
import json
import io
import csv

st.set_page_config(page_title="Notion to Anki Flashcards", layout="wide")

# Inicialização do estado
if "cards" not in st.session_state:
    st.session_state.cards = []

if "page" not in st.session_state:
    st.session_state.page = 1

if "tags" not in st.session_state:
    st.session_state.tags = set()

if "filtered_tags" not in st.session_state:
    st.session_state.filtered_tags = set()

if "last_upload_count" not in st.session_state:
    st.session_state.last_upload_count = 0

def reset_app():
    st.session_state.cards = []
    st.session_state.page = 1
    st.session_state.tags = set()
    st.session_state.filtered_tags = set()
    st.session_state.last_upload_count = 0

def extract_flashcards_from_notion(data):
    flashcards = []
    def recurse_blocks(blocks):
        for block in blocks:
            front = ""
            back = ""
            tag = "Notion"  # Pode evoluir para pegar nome da página
            if "properties" in block and "title" in block["properties"]:
                # Título da página ou bloco
                title_prop = block["properties"]["title"]
                if isinstance(title_prop, list) and len(title_prop) > 0:
                    front = title_prop[0][0]
                elif isinstance(title_prop, str):
                    front = title_prop
                back = block.get("content", "")
                flashcards.append({"front": front, "back": back, "tag": tag})
            if "children" in block:
                recurse_blocks(block["children"])
    if "blocks" in data:
        recurse_blocks(data["blocks"])
    return flashcards

# --- LAYOUT ---

st.markdown(
    """
    <style>
    .section-container {
        background: #fefefe;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgb(0 0 0 / 0.1);
        padding: 20px;
        margin-bottom: 20px;
    }
    .flashcard {
        background: #f9f9fb;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 12px;
        box-shadow: 0 1px 5px rgb(0 0 0 / 0.08);
        font-size: 16px;
        line-height: 1.4;
    }
    .flashcard strong {
        color: #333;
    }
    .tag-code {
        font-family: monospace;
        background-color: #e2e8f0;
        border-radius: 5px;
        padding: 2px 6px;
        font-size: 13px;
        color: #555;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Notion → Anki Flashcards")

st.markdown(
    """
    <div class="section-container">
    <h4>Como usar</h4>
    <ol>
        <li>Faça upload de um arquivo JSON exportado do Notion contendo seus dados.</li>
        <li>Visualize os flashcards extraídos e filtre por tags.</li>
        <li>Exporte seus flashcards em formato TSV para importar no Anki.</li>
    </ol>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown('<div class="section-container">', unsafe_allow_html=True)
    st.header("1. Upload e Importação")
    uploaded_file = st.file_uploader("Envie arquivo JSON exportado do Notion", type=["json"])

    st.markdown("---")
    st.header("2. Filtrar Flashcards")
    if st.session_state.tags:
        selected_tags = st.multiselect(
            "Filtrar por tags", 
            options=sorted(st.session_state.tags), 
            default=sorted(st.session_state.filtered_tags or st.session_state.tags),
            help="Selecione as tags para filtrar os flashcards exibidos."
        )
        st.session_state.filtered_tags = set(selected_tags)
    else:
        st.info("Nenhum flashcard disponível para filtro.")

    st.markdown("---")
    st.header("3. Exportar e Limpar")
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
    st.markdown('</div>', unsafe_allow_html=True)

# Processar upload e extrair flashcards
if uploaded_file:
    try:
        data = json.load(uploaded_file)
        cards_new = extract_flashcards_from_notion(data)
        if cards_new:
            st.session_state.cards.extend(cards_new)
            st.session_state.tags.update(set(card["tag"] for card in cards_new))
            st.session_state.last_upload_count = len(cards_new)
            st.success(f"✅ {len(cards_new)} flashcards importados!")
        else:
            st.warning("Nenhum flashcard encontrado no arquivo.")
    except Exception as e:
        st.error(f"Erro ao processar arquivo JSON: {e}")

# Display flashcards e paginação
st.markdown('<div class="section-container">', unsafe_allow_html=True)
st.header("Flashcards Gerados")

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

    st.markdown(f"<p>Exibindo flashcards {start_idx+1} a {min(end_idx, len(display_cards))} de {len(display_cards)}</p>", unsafe_allow_html=True)

    for i, card in enumerate(display_cards[start_idx:end_idx], start=start_idx+1):
        st.markdown(
            f"""
            <div class="flashcard">
                <strong>{i}. Pergunta:</strong> {card['front']}<br>
                <strong>Resposta:</strong> {card['back']}<br>
                <small>🏷️ Tag: <span class="tag-code">{card['tag']}</span></small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        prev_disabled = page <= 1
        if st.button("⬅️ Anterior", disabled=prev_disabled):
            if page > 1:
                st.session_state.page -= 1
                st.experimental_rerun()
    with col2:
        st.markdown(f"<center>Página {page} de {total_pages}</center>", unsafe_allow_html=True)
    with col3:
        next_disabled = page >= total_pages
        if st.button("Próximo ➡️", disabled=next_disabled):
            if page < total_pages:
                st.session_state.page += 1
                st.experimental_rerun()
else:
    st.info("Nenhum flashcard gerado ou importado ainda.")

st.markdown('</div>', unsafe_allow_html=True)
