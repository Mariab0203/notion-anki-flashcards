import streamlit as st
import zipfile
import os
import tempfile
import openai
import genanki
import pandas as pd
import yaml
import uuid

# Configurações
st.set_page_config(page_title="Flashcards Markdown → Anki", layout="wide")
st.title("🧠 Gerador Inteligente de Flashcards (Markdown Notion)")

# Autenticação
senha = st.text_input("🔐 Digite a senha:", type="password")
if senha != st.secrets.get("APP_PASSWORD"):
    st.error("Senha incorreta.")
    st.stop()

# OpenAI API
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Upload de .zip com arquivos .md
uploaded_file = st.file_uploader("📁 Envie o arquivo `.zip` exportado do Notion em Markdown:", type="zip")
max_cards = st.slider("Máximo de flashcards por bloco:", 1, 5, 3)

def extrair_texto_do_zip(zip_file):
    textos = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
        for root, _, files in os.walk(tmpdir):
            for file in files:
                if file.endswith(".md"):
                    with open(os.path.join(root, file), 'r', encoding="utf-8") as f:
                        textos.append(f.read())
    return textos

def dividir_em_blocos(textos, limite=1000):
    blocos = []
    for texto in textos:
        parags = texto.split('\n\n')
        atual = ''
        for p in parags:
            if len(atual) + len(p) < limite:
                atual += p + '\n\n'
            else:
                blocos.append(atual.strip())
                atual = p + '\n\n'
        if atual:
            blocos.append(atual.strip())
    return blocos

def gerar_flashcards(blocos, max_cards):
    flashcards = []
    for i, bloco in enumerate(blocos):
        prompt = f"""
A partir do conteúdo abaixo, gere até {max_cards} flashcards em YAML com campos:
- pergunta:
  resposta:

Conteúdo:
\"\"\"
{bloco}
\"\"\"
"""
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            resultado = yaml.safe_load(resp.choices[0].message.content)
            if isinstance(resultado, list):
                for item in resultado:
                    pergunta = item.get("pergunta")
                    resposta = item.get("resposta")
                    if pergunta and resposta:
                        flashcards.append((pergunta.strip(), resposta.strip()))
        except Exception as e:
            st.warning(f"Erro ao gerar flashcards no bloco {i+1}: {e}")
    return flashcards

def salvar_csv(flashcards):
    df = pd.DataFrame(flashcards, columns=["Front", "Back"])
    df.to_csv("flashcards.csv", sep="\t", index=False)
    return "flashcards.csv"

def salvar_apkg(flashcards):
    model_id = uuid.uuid4().int >> 96
    deck_id = uuid.uuid4().int >> 96
    model = genanki.Model(
        model_id,
        'Modelo Markdown',
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{"name": "Card", "qfmt": "{{Front}}", "afmt": "{{Back}}"}]
    )
    deck = genanki.Deck(deck_id, "Flashcards do Notion")
    for front, back in flashcards:
        deck.add_note(genanki.Note(model=model, fields=[front, back]))
    genanki.Package(deck).write_to_file("flashcards.apkg")
    return "flashcards.apkg"

# Processamento
if uploaded_file and st.button("🚀 Gerar Flashcards"):
    textos = extrair_texto_do_zip(uploaded_file)
    blocos = dividir_em_blocos(textos)
    st.info(f"{len(blocos)} blocos serão processados.")
    flashcards = gerar_flashcards(blocos, max_cards)
    st.success(f"{len(flashcards)} flashcards gerados!")

    csv_path = salvar_csv(flashcards)
    apkg_path = salvar_apkg(flashcards)

    with open(csv_path, "rb") as f:
        st.download_button("⬇️ Baixar CSV", f, file_name="flashcards.csv")
    with open(apkg_path, "rb") as f:
        st.download_button("⬇️ Baixar APKG (Anki)", f, file_name="flashcards.apkg")
