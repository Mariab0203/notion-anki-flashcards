import streamlit as st
import requests
import pandas as pd
import genanki
import uuid
import openai
import time

# CONFIGURAÇÃO DA API
api_key = st.secrets.get("OPENAI_API_KEY") or st.text_input("Sua chave da OpenAI", type="password")
if api_key:
    openai.api_key = api_key

st.title("🧠 Gerador de Flashcards com IA (Notion → Anki)")

url = st.text_input("URL pública do arquivo de texto (.txt) exportado do Notion")

def baixar_texto(url):
    try:
        resposta = requests.get(url)
        resposta.raise_for_status()
        return resposta.text
    except Exception as e:
        st.error(f"Erro ao baixar o arquivo: {e}")
        return None

def dividir_em_paragrafos(texto, limite=800):
    paragrafos = texto.split("\n")
    blocos = []
    bloco_atual = ""
    for p in paragrafos:
        if not p.strip():
            continue
        if len(bloco_atual) + len(p) < limite:
            bloco_atual += " " + p.strip()
        else:
            blocos.append(bloco_atual.strip())
            bloco_atual = p.strip()
    if bloco_atual:
        blocos.append(bloco_atual.strip())
    return blocos

def gerar_flashcards_ia(blocos, modelo="gpt-3.5-turbo"):
    flashcards = []
    for i, bloco in enumerate(blocos):
        prompt = f"""
A partir do texto abaixo, crie 1 flashcard com uma pergunta e uma resposta direta e precisa.

Texto:
\"\"\"
{bloco}
\"\"\"

Formato:
Pergunta: <pergunta>
Resposta: <resposta>
"""

        try:
            resposta = openai.ChatCompletion.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )

            conteudo = resposta.choices[0].message.content
            linhas = conteudo.strip().split("\n")
            pergunta = next((l.replace("Pergunta:", "").strip() for l in linhas if "Pergunta:" in l), None)
            resposta_card = next((l.replace("Resposta:", "").strip() for l in linhas if "Resposta:" in l), None)

            if pergunta and resposta_card:
                flashcards.append((pergunta, resposta_card))

            time.sleep(1.1)  # evitar rate limit
        except Exception as e:
            st.warning(f"Erro ao gerar flashcard {i+1}: {e}")
            continue

    return flashcards

def salvar_em_csv(flashcards):
    df = pd.DataFrame(flashcards, columns=["Front", "Back"])
    df.to_csv("flashcards_para_anki.csv", sep="\t", index=False)
    return "flashcards_para_anki.csv"

def gerar_pacote_anki(flashcards):
    model_id = uuid.uuid4().int >> 96
    my_model = genanki.Model(
        model_id,
        'Modelo IA',
        fields=[{'name': 'Front'}, {'name': 'Back'}],
        templates=[{
            'name': 'Card 1',
            'qfmt': '{{Front}}',
            'afmt': '{{Back}}',
        }]
    )

    deck_id = uuid.uuid4().int >> 96
    my_deck = genanki.Deck(deck_id, 'Flashcards IA Notion')

    for front, back in flashcards:
        note = genanki.Note(model=my_model, fields=[front, back])
        my_deck.add_note(note)

    arquivo_saida = 'flashcards_gerados.apkg'
    genanki.Package(my_deck).write_to_file(arquivo_saida)
    return arquivo_saida

if url and api_key:
    texto = baixar_texto(url)

    if texto:
        st.subheader("Texto obtido")
        st.text_area("Conteúdo", texto[:2000] + "...", height=300)

        blocos = dividir_em_paragrafos(texto)

        st.info(f"{len(blocos)} blocos de texto detectados para geração de flashcards.")
        if st.button("🔁 Gerar Flashcards com IA"):
            with st.spinner("Gerando flashcards com IA..."):
                flashcards = gerar_flashcards_ia(blocos)

            st.success(f"{len(flashcards)} flashcards gerados com sucesso!")

            for front, back in flashcards:
                st.markdown(f"**Q:** {front}\n\n**A:** {back}\n---")

            arquivo_csv = salvar_em_csv(flashcards)
            with open(arquivo_csv, "rb") as f:
                st.download_button("⬇️ Baixar CSV para Anki", f, file_name=arquivo_csv, mime="text/csv")

            arquivo_apkg = gerar_pacote_anki(flashcards)
            with open(arquivo_apkg, "rb") as f:
                st.download_button("⬇️ Baixar Pacote .apkg", f, file_name=arquivo_apkg, mime="application/octet-stream")
