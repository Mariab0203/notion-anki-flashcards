import streamlit as st
import requests
import re
from typing import List, Dict, Optional
from anki_export import Collection, Note

def fetch_notion_page_text(url: str) -> Optional[str]:
    try:
        response = requests.get(url)
        response.raise_for_status()
        html = response.text

        # Extrai textos simples
        paragraphs = re.findall(r'<p.*?>(.*?)<\/p>', html, flags=re.DOTALL)
        headers = re.findall(r'<h[1-6].*?>(.*?)<\/h[1-6]>', html, flags=re.DOTALL)
        list_items = re.findall(r'<li.*?>(.*?)<\/li>', html, flags=re.DOTALL)

        text_pieces = headers + paragraphs + list_items
        text_clean = "\n\n".join([re.sub('<.*?>', '', t).strip() for t in text_pieces if t.strip() != ''])

        if not text_clean:
            st.warning("Texto extraído está vazio. A página pode não ser pública ou está vazia.")
            return None

        return text_clean
    except requests.exceptions.HTTPError as e:
        st.error(f"Erro HTTP ao acessar página: {e}")
    except Exception as e:
        st.error(f"Erro inesperado: {e}")
    return None

def generate_flashcards(text: str, max_cards: int = 20) -> List[Dict[str, str]]:
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    cards = []
    if len(paragraphs) == 0:
        st.warning("Nenhum conteúdo encontrado para gerar flashcards.")
        return cards

    step = max(1, len(paragraphs) // max_cards)

    for i in range(0, len(paragraphs), step):
        front = paragraphs[i][:100] + '...' if len(paragraphs[i]) > 100 else paragraphs[i]
        verso_parts = paragraphs[i+1:i+step+1] if (i+1) < len(paragraphs) else []
        verso = "\n\n".join(verso_parts) if verso_parts else "Definição/explicação aqui."
        cards.append({"front": front, "back": verso})
        if len(cards) >= max_cards:
            break
    return cards

def export_to_csv(cards: List[Dict[str, str]], filename: str):
    import csv
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Frente', 'Verso'])
        for card in cards:
            writer.writerow([card['front'], card['back']])
    return filename

def export_to_apkg(cards: List[Dict[str, str]], deck_name: str = "Notion Flashcards") -> str:
    col = Collection(deck_name)
    for card in cards:
        note = Note(front=card['front'], back=card['back'])
        col.add_note(note)
    filename = f"{deck_name.replace(' ', '_')}.apkg"
    col.save(filename)
    return filename

st.set_page_config(page_title="Notion para Anki", layout='centered')

st.title("🧠 Notion para Flashcards Anki")
st.markdown("Insira o link público de uma página do Notion para extrair texto e criar flashcards automáticos.")

notion_url = st.text_input("URL da página pública do Notion")
max_cards = st.slider("Número máximo de flashcards a criar", 5, 50, 20)
export_format = st.radio("Formato para exportar:", [".apkg (Anki)", ".csv"])

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
                cards = generate_flashcards(text, max_cards)
                st.success(f"{len(cards)} flashcards gerados!")

                with st.expander("Visualizar flashcards gerados"):
                    for i, card in enumerate(cards, 1):
                        st.markdown(f"**Frente {i}:** {card['front']}")
                        st.markdown(f"**Verso {i}:** {card['back']}\n---")

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
                st.error("Não foi possível extrair texto. Verifique se a página está pública e URL correto.")
