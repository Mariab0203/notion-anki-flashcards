import streamlit as st
import requests
import os
from io import StringIO
import csv
import openai

# Função para buscar o conteúdo da página do Notion
def get_notion_page_text(notion_token, page_id):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    results = []
    has_more = True
    next_cursor = None

    while has_more:
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            st.error(f"Erro ao acessar Notion API: {response.status_code} {response.text}")
            return None
        data = response.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor", None)

    text_list = []
    for block in results:
        block_type = block.get("type")
        block_content = block.get(block_type, {})
        if "text" in block_content:
            texts = [t["plain_text"] for t in block_content["text"]]
            text_list.append("".join(texts))
    full_text = "\n\n".join(text_list)
    return full_text

# Função para gerar flashcards usando OpenAI
def generate_flashcards(openai_api_key, text, max_flashcards=15):
    openai.api_key = openai_api_key
    prompt = (
        f"Você é um assistente que cria flashcards no formato Pergunta e Resposta.\n"
        f"Baseado no texto abaixo, gere até {max_flashcards} flashcards. Cada flashcard deve ter uma pergunta e uma resposta detalhada.\n\n"
        f"Texto:\n{text}\n\n"
        f"Formato de resposta:\nPergunta: ...\nResposta: ...\n\n"
        f"Separe cada flashcard por uma linha em branco."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
        )
        content = response['choices'][0]['message']['content']
        return content
    except Exception as e:
        st.error(f"Erro na geração dos flashcards: {e}")
        return None

# Parse de flashcards do texto gerado para lista estruturada
def parse_flashcards(text):
    cards = []
    entries = text.strip().split("\n\n")
    question, answer = None, None
    for entry in entries:
        if entry.startswith("Pergunta:"):
            question = entry.replace("Pergunta:", "").strip()
        elif entry.startswith("Resposta:"):
            answer = entry.replace("Resposta:", "").strip()
            if question and answer:
                cards.append({"Pergunta": question, "Resposta": answer})
                question, answer = None, None
    return cards

# Função para gerar CSV para exportar ao Anki
def generate_csv(cards):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Front", "Back"])  # Cabeçalho para Anki
    for card in cards:
        writer.writerow([card["Pergunta"], card["Resposta"]])
    output.seek(0)
    return output

def main():
    st.title("Notion → Anki Flashcards Generator")
    st.markdown("""
        Insira seu token de integração do Notion e o ID da página para gerar flashcards automaticamente.
    """)

    notion_token = st.text_input("Token de Integração Notion (secreto)", type="password")
    notion_page_id = st.text_input("ID da Página Notion")
    openai_key = st.text_input("Chave API OpenAI", type="password")

    if st.button("Gerar flashcards automaticamente"):
        if not notion_token or not notion_page_id or not openai_key:
            st.error("Por favor, preencha todos os campos.")
            return

        with st.spinner("Buscando texto no Notion..."):
            text = get_notion_page_text(notion_token, notion_page_id)
        if text is None:
            return
        if not text.strip():
            st.warning("Nenhum texto encontrado na página do Notion.")
            return

        st.markdown("### Texto extraído do Notion:")
        st.write(text)

        with st.spinner("Gerando flashcards com OpenAI..."):
            flashcards_text = generate_flashcards(openai_key, text)
        if not flashcards_text:
            return

        cards = parse_flashcards(flashcards_text)
        if not cards:
            st.warning("Nenhum flashcard foi gerado.")
            return

        st.markdown("### Flashcards gerados:")
        for idx, card in enumerate(cards, 1):
            st.markdown(f"**{idx}. Pergunta:** {card['Pergunta']}")
            st.markdown(f"Resposta: {card['Resposta']}")
            st.write("---")

        csv_file = generate_csv(cards)
        st.download_button("Baixar flashcards CSV para Anki", csv_file, file_name="flashcards.csv", mime="text/csv")

if __name__ == "__main__":
    main()
