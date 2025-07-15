import streamlit as st
from notion_client import Client
import openai
import requests
from bs4 import BeautifulSoup
import csv
import io

# Função para buscar texto da página Notion via API
def get_notion_page_text(notion, page_id):
    try:
        blocks = notion.blocks.children.list(page_id)['results']
        texts = []
        for block in blocks:
            if block['type'] == 'paragraph':
                paragraph = block['paragraph']
                texts.append(''.join([text['plain_text'] for text in paragraph['text']]))
        return '\n'.join(texts)
    except Exception as e:
        st.error(f"Erro ao acessar Notion: {e}")
        return ""

# Função para gerar flashcards usando OpenAI GPT
def generate_flashcards(text, openai_api_key, max_cards=10):
    openai.api_key = openai_api_key
    prompt = (
        "Crie flashcards de perguntas e respostas a partir do texto abaixo. "
        f"Crie até {max_cards} flashcards, com perguntas claras e respostas detalhadas:\n\n{text}\n\n"
        "Formato: Pergunta: ... Resposta: ..."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Corrigido para usar o modelo correto
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
        )
        content = response['choices'][0]['message']['content']
        flashcards = []
        for line in content.split('\n'):
            if line.strip().startswith("Pergunta:"):
                question = line.strip().replace("Pergunta:", "").strip()
                flashcards.append({"question": question, "answer": ""})
            elif line.strip().startswith("Resposta:") and flashcards:
                flashcards[-1]['answer'] = line.strip().replace("Resposta:", "").strip()
        return flashcards
    except Exception as e:
        st.error(f"Erro na geração dos flashcards: {e}")
        return []

# Função para extrair texto de página web (ex: página Notion publicada)
def extract_text_from_url(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        # Extrai texto visível da página
        texts = soup.stripped_strings
        return '\n'.join(texts)
    except Exception as e:
        st.error(f"Erro ao acessar URL: {e}")
        return ""

# Função para exportar flashcards para um arquivo CSV
def export_flashcards_to_csv(flashcards):
    # Criar um objeto StringIO para armazenar o CSV em memória
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Cabeçalho do CSV
    writer.writerow(['Pergunta', 'Resposta'])
    
    # Escrever os flashcards no CSV
    for card in flashcards:
        writer.writerow([card['question'], card['answer']])
    
    # Mover o ponteiro para o início do arquivo
    output.seek(0)
    return output

# Interface Streamlit
def main():
    st.title("Notion to Flashcards")

    st.markdown("""
    ### Passo 1: Configuração

    - Informe o **Notion Integration Token** e o **ID da página** (ou URL pública do Notion).
    - Informe sua chave **OpenAI API Key** para geração automática dos flashcards.
    """)

    notion_token = st.text_input("Notion Integration Token", type="password")
    notion_page_id_or_url = st.text_input("Notion Page ID ou URL pública")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    max_cards = st.slider("Número máximo de flashcards", 1, 30, 10)

    if st.button("Gerar Flashcards"):
        if not notion_token or not notion_page_id_or_url or not openai_api_key:
            st.error("Preencha todos os campos!")
            return

        # Instanciar client Notion
        notion = Client(auth=notion_token)

        # Detectar se o input é URL pública ou apenas ID da página
        if notion_page_id_or_url.startswith("http"):
            st.info("Extraindo texto da URL pública do Notion...")
            text = extract_text_from_url(notion_page_id_or_url)
        else:
            st.info("Extraindo texto via API do Notion...")
            text = get_notion_page_text(notion, notion_page_id_or_url)

        if not text:
            st.error("Não foi possível extrair texto da página Notion.")
            return

        st.write("Texto extraído (resumo):")
        st.write(text[:1000] + "..." if len(text) > 1000 else text)

        st.info("Gerando flashcards com OpenAI GPT...")
        flashcards = generate_flashcards(text, openai_api_key, max_cards)

        if flashcards:
            st.success(f"{len(flashcards)} flashcards gerados:")
            for i, card in enumerate(flashcards, 1):
                st.markdown(f"**{i}. Pergunta:** {card['question']}")
                st.markdown(f"**Resposta:** {card['answer']}")

            # Exportar os flashcards para um arquivo CSV
            st.info("Clique no botão abaixo para exportar os flashcards para um arquivo .csv, compatível com o Anki.")
            csv_file = export_flashcards_to_csv(flashcards)
            st.download_button(
                label="Baixar arquivo CSV",
                data=csv_file,
                file_name="flashcards_anki.csv",
                mime="text/csv"
            )
        else:
            st.error("Não foi possível gerar flashcards.")

if __name__ == "__main__":
    main()
