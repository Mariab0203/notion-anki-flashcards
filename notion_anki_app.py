import streamlit as st
import requests
import json
import re
import time
from typing import List, Dict, Optional
from anki_export import Collection, Note

# Função para extrair texto de uma página pública Notion (API pública)
def fetch_notion_page_text(url: str) -> Optional[str]:
    try:
        # Tentativa de extrair conteúdo da página Notion via scraping simples (se pública)
        # Alternativa para API oficial (mais complexa)
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"Não foi possível acessar a página Notion. Código HTTP: {response.status_code}")
            return None
        html = response.text

        # Regex para extrair conteúdo textual da página (simplificado)
        # Busca por conteúdo dentro de <p>, <h1>-<h6>, <li> etc para montar texto bruto
        paragraphs = re.findall(r'<p.*?>(.*?)<\/p>', html, flags=re.DOTALL)
        headers = re.findall(r'<h[1-6].*?>(.*?)<\/h[1-6]>', html, flags=re.DOTALL)
        list_items = re.findall(r'<li.*?>(.*?)<\/li>', html, flags=re.DOTALL)

        # Juntando tudo
        text_pieces = headers + paragraphs + list_items
        text_clean = "\n\n".join([re.sub('<.*?>', '', t).strip() for t in text_pieces if t.strip() != ''])

        return text_clean if text_clean else None
    except Exception as e:
        st.error(f"Erro ao tentar extrair texto: {e}")
        return None

# Função para criar flashcards (básico: divide texto em blocos)
def generate_flashcards(text: str, max_cards: int = 20) -> List[Dict[str, str]]:
    # Divide o texto em blocos aproximados para gerar flashcards
    # Pode melhorar com NLP para perguntas e respostas

    # Divide em parágrafos
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    cards = []

    # Limita para max_cards
    step = max(1, len(paragraphs) // max_cards)

    for i in range(0, len(paragraphs), step):
        front = paragraphs[i][:100] + '...' if len(paragraphs[i]) > 100 else paragraphs[i]
        # verso é o próximo parágrafo ou concatenação dos próximos
        verso_parts = paragraphs[i+1:i+step+1] if (i+1) < len(paragraphs) else []
        verso = "\n\n".join(verso_parts) if verso_parts else "Definição/explicação aqui."
        cards.append({"front": front, "back": verso})
        if len(cards) >= max_cards:
            break
    return cards

# Exporta flashcards para CSV compatível com Anki
def export_to_csv(cards: List[Dict[str, str]], filename: str):
    import csv
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Frente', 'Verso'])
        for card in cards:
            writer.writerow([card['front'], card['back']])
    return filename

# Exporta flashcards para .apkg usando anki_export
def export_to_apkg(cards: List[Dict[str, str]], deck_name: str = "Notion Flashcards") -> str:
    col = Collection(deck_name)
    for card in cards:
        note = Note(front=card['front'], back=card['back'])
        col.add_note(note)
    filename = f"{deck_name.replace(' ', '_')}.apkg"
    col.save(filename)
    return filename

# --- Streamlit app ---

st.set_page_config(page_title="Notion to Anki Flashcards", layout='centered')

st.title("🧠 Notion para Flashcards Anki")
st.markdown("""
Insira o link público de uma página do Notion para extrair o texto e criar flashcards automáticos.
""")

# Entrada da URL do Notion
notion_url = st.text_input("URL da página pública do Notion")

# Opção de número máximo de flashcards
max_cards = st.slider("Número máximo de flashcards a criar", min_value=5, max_value=50, value=20)

# Opção para exportar
export_format = st.radio("Formato para exportar:", options=[".apkg (Anki)", ".csv"])

# Botão para iniciar o processo
if st.button("Gerar flashcards"):
    if not notion_url.strip():
        st.warning("Por favor, insira um URL válido do Notion.")
    else:
        with st.spinner("Extraindo texto da página..."):
            text = fetch_notion_page_text(notion_url)
            if text:
                st.success("Texto extraído com sucesso!")
                with st.expander("Visualizar texto extraído"):
                    st.write(text[:3000] + ("..." if len(text) > 3000 else ""))

                st.info("Gerando flashcards...")
                cards = generate_flashcards(text, max_cards=max_cards)
                st.success(f"{len(cards)} flashcards gerados!")

                with st.expander("Visualizar flashcards gerados"):
                    for i, card in enumerate(cards, 1):
                        st.markdown(f"**Frente {i}:** {card['front']}")
                        st.markdown(f"**Verso {i}:** {card['back']}\n---")

                # Exportar
                if export_format == ".csv":
                    filename = "flashcards.csv"
                    export_to_csv(cards, filename)
                    with open(filename, "rb") as f:
                        st.download_button("Download CSV", f, file_name=filename, mime="text/csv")
                else:
                    filename = export_to_apkg(cards)
                    with open(filename, "rb") as f:
                        st.download_button("Download Anki (.apkg)", f, file_name=filename, mime="application/octet-stream")
            else:
                st.error("Não foi possível extrair texto da página. Verifique se a página está pública e o URL correto.")

st.markdown("---")
st.markdown("""
**Notas importantes:**

- Certifique-se que a página Notion está pública para que o app consiga ler o conteúdo.
- A extração do texto é simplificada e pode não preservar toda a formatação original.
- A geração dos flashcards é automática, com base em blocos de texto — pode ser aprimorada futuramente.
""")
