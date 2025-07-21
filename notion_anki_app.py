import streamlit as st
import requests
import pandas as pd
import genanki
import uuid
import openai
import yaml
import time

st.set_page_config(page_title="Notion → Flashcards IA", layout="wide")
st.title("🧠 Gerador Inteligente de Flashcards (Notion → Anki)")

# --- Autenticação simples ---
password = st.text_input("🔒 Senha para acessar o app:", type="password")
if password != st.secrets.get("APP_PASSWORD"):
    st.error("Senha incorreta! Acesso negado.")
    st.stop()

# --- Configuração da chave OpenAI ---
openai_api_key = st.secrets.get("OPENAI_API_KEY")
if not openai_api_key:
    st.error("Chave OPENAI_API_KEY não configurada nos Secrets.")
    st.stop()
openai.api_key = openai_api_key

# Input do usuário
url = st.text_input("URL pública do arquivo de texto exportado do Notion (.txt)")
max_cards = st.slider("Máximo de flashcards por bloco", min_value=1, max_value=5, value=3)

@st.cache_data(show_spinner=False)
def baixar_texto(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text

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

@st.cache_data(show_spinner=False)
def gerar_flashcards_ia(blocos, max_cards, modelo="gpt-3.5-turbo"):
    flashcards = []
    total = len(blocos)
    for idx, bloco in enumerate(blocos):
        prompt = f"""
A partir do texto abaixo, gere até {max_cards} flashcards únicos, que não repitam perguntas ou respostas já criadas, cobrindo todas as informações relevantes.
Formato YAML:
- pergunta: ...
  resposta: ...
Texto:
\"\"\"
{bloco}
\"\"\"
Evite perguntas repetidas ou redundantes. Seja claro e conciso.
"""
        try:
            resp = openai.ChatCompletion.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            conteudo = resp.choices[0].message.content
            # Parse YAML com PyYAML
            cards_yaml = yaml.safe_load(conteudo)
            if isinstance(cards_yaml, list):
                for card in cards_yaml:
                    q = card.get("pergunta")
                    a = card.get("resposta")
                    if q and a:
                        flashcards.append((q, a))
        except Exception as e:
            st.warning(f"Erro no bloco {idx+1}: {e}")
        st.progress((idx + 1) / total)
        time.sleep(1.1)
    return flashcards

def salvar_csv(flashcards):
    df = pd.DataFrame(flashcards, columns=["Front", "Back"])
    df.to_csv("flashcards_anki.csv", sep="\t", index=False)
    return "flashcards_anki.csv"

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

if st.button("Processar Notion"):
    if not url:
        st.error("Cole a URL do arquivo .txt do Notion.")
    else:
        try:
            txt = baixar_texto(url)
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

        except Exception as e:
            st.error(f"Erro geral: {e}")

if st.button("Limpar cache"):
    st.cache_data.clear()
    st.success("Cache limpo!")
