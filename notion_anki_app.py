import streamlit as st
from notion_client import Client
import csv
from io import StringIO
import openai

st.set_page_config(page_title="Notion → Anki + IA", layout="centered")
st.title("🧠 Flashcards: Notion → Anki + IA")

st.warning("""
⚠️ **Importante:** Nunca compartilhe seu Token do Notion ou Chave da OpenAI com outras pessoas.
Estes dados são sensíveis e permitem acesso às suas informações privadas.
Use-os somente para este app e mantenha-os em segurança.
""")

if 'cards' not in st.session_state:
    st.session_state.cards = []

st.sidebar.header("Configurações de Integração")

openai_api_key = st.sidebar.text_input("🔑 OpenAI API Key (para IA)", type="password")
if openai_api_key:
    openai.api_key = openai_api_key

st.sidebar.header("⚠️ Avisos de Segurança")
st.sidebar.info("""
- Nunca compartilhe seus tokens ou chaves.
- Dados são usados somente na sessão atual.
- O app não armazena suas chaves.
""")

st.sidebar.header("Obtenha Flashcards de...")

def fetch_from_notion(token, db_id):
    notion = Client(auth=token)
    cards = []
    start_cursor = None

    # Pega o título do banco de dados para usar como tag
    db_info = notion.databases.retrieve(database_id=db_id)
    tag = db_info['title'][0]['plain_text'] if db_info['title'] else "NotionDB"

    while True:
        query_params = {"database_id": db_id}
        if start_cursor:
            query_params["start_cursor"] = start_cursor
        response = notion.databases.query(**query_params)
        data = response['results']
        for r in data:
            props = r['properties']
            try:
                q = props['Pergunta']['title'][0]['text']['content']
                a = props['Resposta']['rich_text'][0]['text']['content']
                cards.append((q, a, tag))
            except:
                continue
        if not response.get('has_more'):
            break
        start_cursor = response.get('next_cursor')
    return cards

with st.sidebar.expander("📦 Notion API"):
    token = st.text_input("Token Notion", type="password", key="notion_token")
    db_id = st.text_input("ID do Banco de Dados Notion", key="notion_db_id")
    if st.button("Buscar do Notion"):
        if token and db_id:
            try:
                with st.spinner("Buscando dados no Notion..."):
                    cards = fetch_from_notion(token, db_id)
                    st.session_state.cards.extend(cards)
                    st.success(f"{len(cards)} flashcards adicionados do Notion.")
            except Exception as e:
                st.error(f"Erro ao acessar Notion: {e}")
        else:
            st.warning("Informe Token e ID do banco de dados.")

with st.sidebar.expander("📁 Upload CSV (Pergunta e Resposta)"):
    uploaded = st.file_uploader("Envie arquivo CSV", type=['csv'])
    if uploaded:
        try:
            filename = uploaded.name
            content = uploaded.getvalue().decode('utf-8')
            reader = csv.DictReader(StringIO(content))
            cards = [(row.get('Pergunta',''), row.get('Resposta',''), filename) for row in reader if row.get('Pergunta')]
            st.session_state.cards.extend(cards)
            st.success(f"{len(cards)} flashcards adicionados do CSV ({filename}).")
        except Exception as e:
            st.error(f"Erro ao processar CSV: {e}")

with st.sidebar.expander("🤖 Gerar Flashcards com IA"):
    raw_text = st.text_area("Texto ou Markdown para IA gerar flashcards", height=150)
    if raw_text and openai_api_key:
        if st.button("Gerar flashcards com IA"):
            try:
                prompt = (
                    "Você é um assistente que cria flashcards para estudo, no formato:\n"
                    "Pergunta || Resposta\n\n"
                    "Gere flashcards claros e diretos baseados no seguinte texto:\n"
                    f"{raw_text}\n\n"
                    "Responda somente com flashcards, uma pergunta e resposta por linha, separadas por '||'."
                )
                with st.spinner("Gerando flashcards com IA..."):
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=600,
                        temperature=0.7,
                        n=1,
                    )
                    text_response = response.choices[0].message.content.strip()
                    # Tag para IA gerados = "IA"
                    cards = []
                    for line in text_response.splitlines():
                        if '||' in line:
                            q,a = [s.strip() for s in line.split('||',1)]
                            cards.append((q,a,"IA"))
                    st.session_state.cards.extend(cards)
                    st.success(f"IA gerou {len(cards)} flashcards.")
            except Exception as e:
                st.error(f"Erro na geração IA: {e}")
    elif raw_text:
        st.info("Informe sua OpenAI API Key para gerar flashcards com IA.")

# --- FILTRO POR TAG ---

all_tags = list(set([tag for _,_,tag in st.session_state.cards]))
selected_tags = st.multiselect("Filtrar flashcards por tags:", options=all_tags, default=all_tags)

filtered_cards = [c for c in st.session_state.cards if c[2] in selected_tags]

st.subheader(f"Total de flashcards: {len(filtered_cards)} (filtrados por tags)")

page_size = 10
page_num = st.number_input("Página", min_value=1, max_value=max(1, (len(filtered_cards)-1)//page_size+1), step=1)
start_idx = (page_num - 1) * page_size
end_idx = start_idx + page_size

for i, (q,a,tag) in enumerate(filtered_cards[start_idx:end_idx], start=start_idx+1):
    st.markdown(f"**{i}. Q:** {q}\n> **A:** {a}\n> 🏷️ Tag: `{tag}`")

if filtered_cards:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Pergunta", "Resposta", "Tag"])
    for q,a,tag in filtered_cards:
        writer.writerow([q,a,tag])
    st.download_button(
        "📥 Baixar CSV para Anki",
        output.getvalue(),
        "flashcards_com_tags.csv",
        "text/csv"
    )
else:
    st.info("Nenhum flashcard disponível para exportar.")
