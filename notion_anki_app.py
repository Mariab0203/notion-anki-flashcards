import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import os
import tempfile
import genanki  # para criar pacotes Anki
from openai import OpenAI
import openai

# --- Funções auxiliares ---

def extrair_texto_notion_publico(url):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
    except Exception as e:
        st.error(f"Erro ao acessar a URL: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.decompose()
    texto = soup.get_text(separator="\n")
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    return "\n\n".join(linhas)

def dividir_por_titulos(texto, nivel=2):
    """
    Divide texto em seções usando títulos no padrão Markdown ## ou H2 equivalente.
    Retorna dict {titulo: texto_seção}
    """
    # Exemplo de regex para títulos no estilo '## Título' ou 'Título em linha separada'
    # Como a página do Notion pode não ter markdown, tentaremos separar por linhas em MAIÚSCULAS ou com padrão CIR 1
    pattern = re.compile(r"^(CIR\s*\d+.*)$", re.MULTILINE | re.IGNORECASE)

    # Divide pelo padrão
    indices = [(m.start(), m.group(1).strip()) for m in pattern.finditer(texto)]

    secoes = {}
    if not indices:
        # Nenhuma seção encontrada, retorna tudo
        secoes["Conteúdo Completo"] = texto
        return secoes

    for i, (pos, titulo) in enumerate(indices):
        start = pos
        end = indices[i+1][0] if i+1 < len(indices) else len(texto)
        conteudo = texto[start:end].strip()
        secoes[titulo] = conteudo

    return secoes

def gerar_flashcards(texto, openai_api_key, max_cards=10):
    """
    Envia o texto para OpenAI gerar flashcards no formato Q/A.
    Limita a max_cards para não estourar tokens.
    """
    openai.api_key = openai_api_key

    prompt = (
        f"Divida o texto abaixo em até {max_cards} flashcards de perguntas e respostas, "
        "com perguntas claras e respostas detalhadas. Use formato:\n"
        "Pergunta: ...\nResposta: ...\n\n"
        f"Texto:\n{texto}\n\n"
    )

    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=1500,
            temperature=0.5,
            n=1,
            stop=None,
        )
        resultado = response.choices[0].text.strip()
        return resultado
    except Exception as e:
        st.error(f"Erro na geração de flashcards: {e}")
        return None

def parse_flashcards(raw_text):
    """
    Transforma texto bruto da IA em lista de dicts {question, answer}
    Espera formato:
    Pergunta: ...
    Resposta: ...
    """
    cards = []
    blocos = raw_text.split("\n\n")
    for bloco in blocos:
        q_match = re.search(r"Pergunta:\s*(.*)", bloco, re.IGNORECASE)
        a_match = re.search(r"Resposta:\s*(.*)", bloco, re.IGNORECASE | re.DOTALL)
        if q_match and a_match:
            question = q_match.group(1).strip()
            answer = a_match.group(1).strip()
            cards.append({"question": question, "answer": answer})
    return cards

def criar_anki_decks(cards, deck_name="Flashcards Notion"):
    """
    Cria um arquivo .apkg com os flashcards gerados.
    """
    deck_id = int(abs(hash(deck_name)) % (10 ** 10))
    deck = genanki.Deck(deck_id, deck_name)
    modelo = genanki.Model(
        1607392319,
        'Simple Model',
        fields=[
            {'name': 'Question'},
            {'name': 'Answer'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': '{{Question}}',
                'afmt': '{{FrontSide}}<hr id="answer">{{Answer}}',
            },
        ])

    for card in cards:
        note = genanki.Note(
            model=modelo,
            fields=[card["question"], card["answer"]],
        )
        deck.add_note(note)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".apkg")
    genanki.Package(deck).write_to_file(temp_file.name)
    return temp_file.name


# --- Streamlit App ---

st.title("Flashcards Automáticos do Notion para Anki")

st.markdown("""
Este app lê uma página pública do Notion, extrai o texto, divide por seções, e gera flashcards automaticamente com IA.
""")

url = st.text_input("Cole a URL pública da página do Notion aqui:")
filtro_secao = st.text_input("Filtro de seção (ex: CIR 1 - SÍNDROMES DE HIPERTENSÃO PORTA) (opcional):")

openai_api_key = st.text_input("Sua OpenAI API Key (começa com sk-):", type="password")

max_cards = st.slider("Número máximo de flashcards a criar:", min_value=1, max_value=20, value=10)

if st.button("Gerar Flashcards"):

    if not url:
        st.error("Por favor, insira a URL pública do Notion.")
    elif not openai_api_key:
        st.error("Por favor, insira sua chave API da OpenAI.")
    else:
        with st.spinner("Extraindo texto da página..."):
            texto_completo = extrair_texto_notion_publico(url)
        if texto_completo is None:
            st.stop()

        secoes = dividir_por_titulos(texto_completo)
        st.write(f"Seções encontradas: {list(secoes.keys())}")

        if filtro_secao:
            # tenta encontrar seção pelo filtro (case insensitive)
            secao_texto = None
            for titulo, conteudo in secoes.items():
                if filtro_secao.lower() in titulo.lower():
                    secao_texto = conteudo
                    st.write(f"Usando seção filtrada: {titulo}")
                    break
            if not secao_texto:
                st.warning("Seção filtro não encontrada. Usando conteúdo completo.")
                secao_texto = texto_completo
        else:
            secao_texto = texto_completo

        with st.spinner("Gerando flashcards via OpenAI..."):
            flashcards_bruto = gerar_flashcards(secao_texto, openai_api_key, max_cards=max_cards)

        if not flashcards_bruto:
            st.error("Não foi possível gerar flashcards.")
            st.stop()

        cards = parse_flashcards(flashcards_bruto)

        if not cards:
            st.error("Nenhum flashcard válido foi gerado.")
            st.stop()

        st.success(f"{len(cards)} flashcards gerados!")

        for i, card in enumerate(cards, 1):
            st.markdown(f"**Pergunta {i}:** {card['question']}")
            st.markdown(f"Resposta: {card['answer']}")

        with st.spinner("Criando arquivo Anki (.apkg)..."):
            arq_anki = criar_anki_decks(cards)
            st.success("Arquivo Anki criado!")

        with open(arq_anki, "rb") as f:
            st.download_button(
                label="Download do arquivo Anki (.apkg)",
                data=f,
                file_name="flashcards_notion.apkg",
                mime="application/octet-stream",
            )
