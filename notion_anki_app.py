import streamlit as st
from notion_client import Client
import csv
from io import StringIO
import openai

st.set_page_config(page_title="Notion → Anki + IA", layout="centered")
st.title("🧠 Flashcards: Notion → Anki + IA")

# Aviso de segurança
st.warning("""
⚠️ **Importante:** Nunca compartilhe seu Token do Notion ou Chave da OpenAI com outras pessoas.
Estes dados são sensíveis e permitem acesso às suas informações privadas.
Use-os somente para este app e mantenha-os em segurança.
""")

# Configurações do OpenAI (necessário cadastrar sua chave se quiser IA)
openai_api_key = st.sidebar.text_input("🔑 OpenAI API Key (para IA)", type="password")
if openai_api_key:
    openai.api_key = openai_api_key

st.sidebar.header("⚠️ Atenção")
st.sidebar.info("""
Por segurança:
- Não compartilhe seu Token do Notion ou OpenAI.
- Esses dados são usados **apenas durante sua sessão**.
- O app **não armazena** nenhuma chave ou dado sensível.
""")

# Notion API
token = st.sidebar.text_input("Token Notion", type="password")
db_id = st.sidebar.text_input("ID do Banco de Dados Notion")

def fetch_from_notion(token, db_id):
    notion = Client(auth=token)
    data = notion.databases.query(database_id=db_id)['results']
    cards = []
    for r in data:
        props = r['properties']
        try:
            q = props['Pergunta']['title'][0]['text']['content']
            a = props['Resposta']['rich_text'][0]['text']['content']
            cards.append((q, a))
        except:
            continue
    return cards

def fetch_from_csv(uploaded):
    content = uploaded.getvalue().decode('utf-8')
    reader = csv.DictReader(StringIO(content))
    cards = [(row.get('Pergunta',''), row.get('Resposta','')) for row in reader if row.get('Pergunta')]
    return cards

def generate_with_ia(text):
    prompt = (
        "Gere flashcards em formato Pergunta – Resposta, separados por '||'.\n"
        f"Texto para análise:\n{text}\n"
        "Resposta no formato:\nPergunta 1 || Resposta 1\nPergunta 2 || Resposta 2\n..."
    )
    resp = openai.Completion.create(engine="gpt-3.5-turbo", prompt=prompt, max_tokens=500)
    cards = []
    for line in resp.choices[0].text.strip().splitlines():
        if '||' in line:
            q, a = [s.strip() for s in line.split('||',1)]
            cards.append((q, a))
    return cards

cards = []
# Execução
if st.sidebar.checkbox("📦 Obter do Notion (API)", value=True):
    if token and db_id:
        st.sidebar.success("Será buscado do Notion via API.")
        cards += fetch_from_notion(token, db_id)
    else:
        st.sidebar.warning("Token ou DB ID faltando para Notion API.")

if st.sidebar.checkbox("📁 Upload CSV do Notion", value=True):
    uploaded = st.sidebar.file_uploader("Upload CSV (com colunas Pergunta/Resposta)", type=['csv'])
    if uploaded:
        cards += fetch_from_csv(uploaded)

if st.sidebar.checkbox("🤖 Gerar com IA a partir de texto", value=True):
    raw_text = st.sidebar.text_area("Texto ou Markdown para IA gerar flashcards")
    if raw_text and openai_api_key:
        if st.sidebar.button("Gerar flashcards com IA"):
            ia_cards = generate_with_ia(raw_text)
            st.sidebar.info(f"IA gerou {len(ia_cards)} flashcards.")
            cards += ia_cards
    elif raw_text:
        st.sidebar.warning("Chave OpenAI necessária para IA.")

# Exibir resultados
if cards:
    st.subheader(f"Total de flashcards: {len(cards)}")
    for i,(q,a) in enumerate(cards[:10],1):
        st.markdown(f"**{i}. Q:** {q}\n> **A:** {a}")
    output = StringIO()
    writer = csv.writer(output, delimiter='\t')
    for q,a in cards:
        writer.writerow([q,a])
    st.download_button("📥 Baixar .txt para Anki", output.getvalue(), "flashcards.txt", "text/plain")
else:
    st.info("Nenhum flashcard gerado ainda.")
