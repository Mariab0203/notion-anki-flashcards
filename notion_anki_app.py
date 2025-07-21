import streamlit as st
from openai import OpenAI

# ... seu código anterior ...

# Inicializa o cliente OpenAI com a chave dos secrets
client = OpenAI(api_key=st.secrets["sk-...Zd4A"]
# --- TESTE TEMPORÁRIO DA API OPENAI ---
st.markdown("### 🔍 Teste rápido da API OpenAI")
try:
    resposta = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Teste rápido da API OpenAI"}],
        temperature=0,
    )
    st.success("✅ API OpenAI conectada com sucesso!")
    st.write("Resposta da OpenAI:", resposta.choices[0].message.content)
except Exception as e:
    st.error(f"❌ Erro na chamada OpenAI: {e}")

# ... resto do seu app ...

import streamlit as st
import zipfile
import os
import tempfile
import genanki
import pandas as pd
import yaml
import uuid
import tiktoken
import time
from openai import OpenAI

# ========== CONFIGURAÇÕES ==========
st.set_page_config(page_title="Flashcards Notion → Anki", layout="wide")
st.title("🧠 Gerador de Flashcards para Residência Médica")

# ========== AUTENTICAÇÃO ==========
senha = st.text_input("🔐 Digite a senha:", type="password")
if senha != st.secrets.get("APP_PASSWORD"):
    st.error("Senha incorreta.")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
st.write("🔑 Chave OpenAI carregada:", st.secrets.get("OPENAI_API_KEY", "Não encontrada"))


# ========== PROMPT ==========
PROMPT_SISTEMA_BASE = """
Você é um assistente especializado em gerar flashcards de alta qualidade para revisão de conteúdos médicos, focado em residência médica.

Sua única fonte de informação é o texto fornecido. Nunca invente dados nem adicione conteúdo externo.

Gere até {max_cards} flashcards por bloco com o seguinte formato YAML:

- pergunta: (clara, objetiva, técnica e única)
  resposta: (completa, objetiva e fiel ao conteúdo)

Não repita perguntas. Use toda a informação relevante. Mantenha formato limpo e válido em YAML.
"""

# ========== ENTRADAS ==========
uploaded_file = st.file_uploader("📁 Envie o `.zip` exportado do Notion:", type="zip")
limite_tokens = st.slider("🔢 Tokens por bloco", 300, 1500, 1000)
limite_flashcards_totais = st.slider("📦 Máximo total de flashcards", 10, 300, 100)

exportar_csv = st.checkbox("⬇️ Exportar CSV", value=True)
exportar_apkg = st.checkbox("⬇️ Exportar APKG (Anki)", value=True)

# ========== FUNÇÕES AUXILIARES ==========

@st.cache_data(show_spinner=False)
def extrair_texto_do_zip(zip_file_bytes):
    textos = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_file_bytes, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
        for root, _, files in os.walk(tmpdir):
            for file in files:
                if file.endswith(".md"):
                    with open(os.path.join(root, file), 'r', encoding="utf-8") as f:
                        textos.append(f.read())
    return textos

@st.cache_data(show_spinner=False)
def dividir_em_blocos(textos, limite_tokens=1000):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    blocos = []
    for texto in textos:
        parags = texto.split('\n\n')
        atual = ''
        atual_tokens = 0
        for p in parags:
            p_tokens = len(encoding.encode(p))
            if atual_tokens + p_tokens < limite_tokens:
                atual += p + '\n\n'
                atual_tokens += p_tokens
            else:
                blocos.append(atual.strip())
                atual = p + '\n\n'
                atual_tokens = p_tokens
        if atual:
            blocos.append(atual.strip())
    return blocos

def filtrar_flashcards_duplicados(flashcards):
    vistos = set()
    unicos = []
    for f, b in flashcards:
        key = f.lower().strip()
        if key not in vistos:
            vistos.add(key)
            unicos.append((f, b))
    return unicos

def gerar_flashcards(blocos, limite_total_flashcards, max_retries=2):
    flashcards = []
    progresso = st.progress(0)
    total_blocos = len(blocos)

    for i, bloco in enumerate(blocos):
        bloco = bloco.strip()
        if not bloco:
            st.warning(f"⚠️ Bloco {i+1} vazio. Pulando.")
            progresso.progress((i + 1) / total_blocos)
            continue

        restante = limite_total_flashcards - len(flashcards)
        if restante <= 0:
            st.info("✅ Limite total de flashcards alcançado.")
            break
        max_cards_bloco = min(5, restante)

        system_prompt = PROMPT_SISTEMA_BASE.format(max_cards=max_cards_bloco)

        prompt_usuario = f"""
A partir do conteúdo abaixo, gere até {max_cards_bloco} flashcards no formato pedido.

Conteúdo:
\"\"\"{bloco}\"\"\"
"""

        retry = 0
        while retry <= max_retries:
            try:
                resposta = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_usuario}
                    ],
                    temperature=0.3,
                )
                conteudo = resposta.choices[0].message.content
                st.text_area(f"🧠 Resposta da IA (bloco {i+1})", conteudo, height=200)

                try:
                    resultado = yaml.safe_load(conteudo)
                    if isinstance(resultado, list):
                        for item in resultado:
                            pergunta = item.get("pergunta")
                            resposta = item.get("resposta")
                            if pergunta and resposta:
                                flashcards.append((pergunta.strip(), resposta.strip()))
                                if len(flashcards) >= limite_total_flashcards:
                                    st.info("✅ Limite total alcançado.")
                                    break
                        break
                    else:
                        st.warning(f"⚠️ Bloco {i+1} retornou formato inesperado.")
                        st.code(conteudo)
                        break
                except yaml.YAMLError as ye:
                    st.error(f"❌ Erro ao interpretar YAML no bloco {i+1}: {ye}")
                    st.code(conteudo)
                    break

            except Exception as e:
                st.error(f"❌ Erro no bloco {i+1}, tentativa {retry+1}: {e}")
                retry += 1
                time.sleep(1)

        progresso.progress((i + 1) / total_blocos)

    return flashcards

def salvar_csv(flashcards):
    df = pd.DataFrame(flashcards, columns=["Front", "Back"])
    path = os.path.join(tempfile.gettempdir(), "flashcards.csv")
    df.to_csv(path, sep="\t", index=False)
    return path

def salvar_apkg(flashcards):
    model_id = 1607392319
    deck_id = 2059400110
    model = genanki.Model(
        model_id,
        'Modelo Markdown',
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{"name": "Card", "qfmt": "{{Front}}", "afmt": "{{Back}}"}]
    )
    deck = genanki.Deck(deck_id, "Flashcards do Notion")
    for front, back in flashcards:
        deck.add_note(genanki.Note(model=model, fields=[front, back]))
    path = os.path.join(tempfile.gettempdir(), "flashcards.apkg")
    genanki.Package(deck).write_to_file(path)
    return path

# ========== EXECUÇÃO ==========
if uploaded_file and st.button("🚀 Gerar Flashcards"):
    start = time.time()

    textos = extrair_texto_do_zip(uploaded_file)
    blocos = dividir_em_blocos(textos, limite_tokens)
    st.info(f"📄 {len(blocos)} blocos serão processados.")

    flashcards = gerar_flashcards(blocos, limite_flashcards_totais)
    flashcards = filtrar_flashcards_duplicados(flashcards)
    st.success(f"✅ {len(flashcards)} flashcards únicos gerados!")

    if flashcards:
        st.markdown("### 🧪 Preview dos primeiros 5 flashcards")
        for i, (front, back) in enumerate(flashcards[:5]):
            st.markdown(f"**{i+1}.** {front}")
            st.markdown(f"**Resposta:** {back}")
            st.markdown("---")

        if exportar_csv:
            csv_path = salvar_csv(flashcards)
            with open(csv_path, "rb") as f:
                st.download_button("⬇️ Baixar CSV", f, file_name="flashcards.csv")

        if exportar_apkg:
            apkg_path = salvar_apkg(flashcards)
            with open(apkg_path, "rb") as f:
                st.download_button("⬇️ Baixar APKG", f, file_name="flashcards.apkg")

    end = time.time()
    st.info(f"⏱️ Tempo total: {end - start:.2f} segundos")
