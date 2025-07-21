import streamlit as st
import requests
import pandas as pd
import genanki
import uuid
import openai
import time

# CONFIGURAÇÃO DA API
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="Notion → Flashcards IA", layout="wide")
st.title("🧠 Gerador Inteligente de Flashcards (Notion → Anki)")

# Input de URL e máximo de cards por bloco
url = st.text_input("URL pública do arquivo de texto exportado do Notion (.txt)")
max_cards = st.slider("Máximo de flashcards por bloco", min_value=1, max_value=5, value=3)

# Função para baixar o texto
def baixar_texto(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        st.error(f"Erro ao baixar arquivo: {e}")
        return None

# Função para dividir em blocos de até ~800 caracteres
def dividir_em_blocos(texto, limite=800):
    parags = [p.strip() for p in texto.split("\n\n") if p.strip()]
    blocos = []
    cur = ""
    for p in parags:
        if len(cur) + len(p) + 2 < limite:
            cur += ("\n\n" + p) if cur else p
        else:
            blocos.append(cur)
            cur = p
    if cur:
        blocos.append(cur)
    return blocos

# Prompt com múltiplos flashcards
def gerar_flashcards_ia(blocos, max_cards, modelo="gpt-3.5-turbo"):
    flashcards = []
    total = len(blocos)
    bar = st.progress(0)
    for idx, bloco in enumerate(blocos):
        prompt = f"""
A partir do texto abaixo, gere até {max_cards} flashcards que cubram T O D A S as informações importantes, com:
Pergunta: <pergunta>
Resposta: <resposta>
Formato YAML: 
- pergunta: ...
  resposta: ...
Texto:
\"\"\"
{bloco}
\"\"\"
"""
        try:
            resp = openai.ChatCompletion.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            conteudo = resp.choices[0].message.content
            for line in conteudo.strip().split("\n"):
                if line.lower().strip().startswith("- pergunta:"):
                    q = line.split(":",1)[1].strip()
                    # next line resposta
                    # we assume next line contains resposta
                    # simple parsing
                elif line.lower().strip().startswith("resposta:") or "resposta:" in line.lower():
                    a = line.split(":",1)[1].strip()
                    flashcards.append((q, a))
        except Exception as e:
            st.warning(f"Erro no bloco {idx+1}: {e}")
        bar.progress((idx + 1) / total)
        time.sleep(1.1)
    return flashcards

# Export CSV
def salvar_csv(flashcards):
    df = pd.DataFrame(flashcards, columns=["Front", "Back"])
    df.to_csv("flashcards_anki.csv", sep="\t", index=False)
    return "flashcards_anki.csv"

# Export APKG
def salvar_apkg(flashcards):
    model_id = uuid.uuid4().int >> 96
    deck_id = uuid.uuid4().int >> 96
    model = genanki.Model(
        model_id, "Modelo IA",
        fields=[{"name":"Front"},{"name":"Back"}],
        templates=[{"name":"Card","qfmt":"{{Front}}","afmt":"{{Back}}"}],
    )
    deck = genanki.Deck(deck_id, "Notion IA Flashcards")
    for front, back in flashcards:
        deck.add_note(genanki.Note(model=model, fields=[front, back]))
    pkg = genanki.Package(deck)
    pkg.write_to_file("flashcards_anki.apkg")
    return "flashcards_anki.apkg"

# Fluxo
if st.button("Processar Notion"):
    if not url:
        st.error("Cole a URL do arquivo .txt do Notion.")
    else:
        txt = baixar_texto(url)
        if txt:
            st.subheader("📄 Conteúdo completo")
            st.text_area("", txt, height=400)
            blocos = dividir_em_blocos(txt)
            st.info(f"{len(blocos)} blocos gerados para processamento.")

            with st.spinner("Gerando flashcards..."):
                cards = gerar_flashcards_ia(blocos, max_cards)

            st.success(f"{len(cards)} flashcards gerados!")
            for i,(q,a) in enumerate(cards,1):
                st.markdown(f"**{i}. Q:** {q}\n\n**A:** {a}")

            csv = salvar_csv(cards)
            apkg = salvar_apkg(cards)

            with open(csv,"rb") as f:
                st.download_button("⬇️ Baixar CSV", f, file_name=csv, mime="text/csv")
            with open(apkg,"rb") as f:
                st.download_button("⬇️ Baixar APKG", f, file_name=apkg, mime="application/octet-stream")
