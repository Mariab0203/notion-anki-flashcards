import streamlit as st
import zipfile
import os
import tempfile
import openai
import genanki
import pandas as pd
import yaml
import uuid
import tiktoken
import time

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

# Prompt base para geração de flashcards
PROMPT_SISTEMA_BASE = """
Você é um assistente especializado em gerar flashcards de alta qualidade para revisão de conteúdos médicos, focado em residência médica.

Sua única fonte de informação é o texto fornecido no prompt do usuário. Você não deve adicionar informações externas ou inventar dados.

Regras importantes para a geração dos flashcards:
- Utilize **toda** informação relevante contida no texto, garantindo cobertura máxima do conteúdo.
- Crie até {max_cards} flashcards por bloco, focando na eficiência para revisão rápida e eficaz.
- Cada flashcard deve conter:
  - pergunta: curta, objetiva e clara, focada em fatos importantes, conceitos chave, diagnósticos, tratamentos, fisiologia, farmacologia, exames, sinais clínicos e outras informações essenciais para a prática médica.
  - resposta: explicativa e completa, mas direta, com detalhes suficientes para compreensão e memorização.
- Evite repetir informações entre flashcards; cada pergunta deve ser única.
- Não crie flashcards com perguntas vagas, muito genéricas ou irrelevantes.
- Use linguagem técnica apropriada para residentes médicos, mas mantenha clareza e objetividade.
- Mantenha o formato YAML válido, com lista de flashcards, cada um com campos “pergunta” e “resposta”.
- Exemplo:
  - pergunta: Quais são os critérios diagnósticos para diabetes mellitus tipo 2?
    resposta: Glicemia de jejum ≥126 mg/dL em duas ocasiões diferentes, ou hemoglobina glicada ≥6,5%, ou teste oral de tolerância à glicose com glicemia ≥200 mg/dL em 2 horas.

Não inclua nada além da lista YAML de flashcards conforme descrito.
"""

# Upload de .zip com arquivos .md
uploaded_file = st.file_uploader("📁 Envie o arquivo `.zip` exportado do Notion em Markdown:", type="zip")

# Configurações do usuário
limite_tokens = st.slider("Limite de tokens por bloco para envio ao OpenAI:", 200, 1500, 1000)
limite_flashcards_totais = st.slider("Máximo total de flashcards a gerar:", 10, 300, 100)
exportar_csv = st.checkbox("Exportar CSV", value=True)
exportar_apkg = st.checkbox("Exportar APKG (Anki)", value=True)

# Cache para extrair texto do zip
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

# Cache para dividir texto em blocos com limite de tokens
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
    filtrados = []
    for front, back in flashcards:
        key = front.lower()
        if key not in vistos:
            vistos.add(key)
            filtrados.append((front, back))
    return filtrados

def gerar_flashcards(blocos, limite_total_flashcards, max_retries=2):
    flashcards = []
    total_blocos = len(blocos)
    progresso = st.progress(0)
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

    if 'logs' not in st.session_state:
        st.session_state.logs = []

    for i, bloco in enumerate(blocos):
        # Calcula max_cards para este bloco para não ultrapassar limite total
        restante = limite_total_flashcards - len(flashcards)
        if restante <= 0:
            st.info(f"Limite total de {limite_total_flashcards} flashcards alcançado.")
            break
        # Define máximo para o bloco: mínimo entre slider máximo e restante
        max_cards_bloco = min(5, restante)

        system_message = PROMPT_SISTEMA_BASE.format(max_cards=max_cards_bloco)

        prompt = f"""
A partir do conteúdo abaixo, gere até {max_cards_bloco} flashcards em YAML com campos:
- pergunta:
  resposta:

Conteúdo:
\"\"\"{bloco}\"\"\"
"""
        retry = 0
        while retry <= max_retries:
            try:
                resp = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                )
                conteudo = resp.choices[0].message.content
                try:
                    resultado = yaml.safe_load(conteudo)
                except yaml.YAMLError as ye:
                    st.warning(f"Erro de parse YAML no bloco {i+1}: {ye}")
                    st.text_area(f"Conteúdo retornado pela API no bloco {i+1}", conteudo, height=150)
                    break

                if isinstance(resultado, list):
                    for item in resultado:
                        pergunta = item.get("pergunta")
                        resposta = item.get("resposta")
                        if pergunta and resposta:
                            flashcards.append((pergunta.strip(), resposta.strip()))
                            if len(flashcards) >= limite_total_flashcards:
                                st.info(f"Limite total de {limite_total_flashcards} flashcards alcançado.")
                                break
                else:
                    st.warning(f"Formato inesperado no bloco {i+1}: {type(resultado)}")
                    st.text_area(f"Conteúdo retornado pela API no bloco {i+1}", conteudo, height=150)
                break

            except Exception as e:
                st.session_state.logs.append(f"Erro no bloco {i+1}, tentativa {retry+1}: {e}")
                retry += 1
                if retry > max_retries:
                    st.warning(f"Falha ao gerar flashcards no bloco {i+1} após {max_retries} tentativas.")
                else:
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

# Processamento

if uploaded_file and st.button("🚀 Gerar Flashcards"):
    start_time = time.time()
    textos = extrair_texto_do_zip(uploaded_file)
    blocos = dividir_em_blocos(textos, limite_tokens)
    st.info(f"{len(blocos)} blocos serão processados.")

    flashcards = gerar_flashcards(blocos, limite_flashcards_totais)
    flashcards = filtrar_flashcards_duplicados(flashcards)

    st.success(f"{len(flashcards)} flashcards gerados!")

    if len(flashcards) > 0:
        # Preview dos 5 primeiros flashcards
        st.markdown("### 👀 Preview dos flashcards gerados (5 primeiros)")
        for i, (frente, tras) in enumerate(flashcards[:5]):
            st.markdown(f"**{i+1}. Pergunta:** {frente}")
            st.markdown(f"**Resposta:** {tras}")
            st.markdown("---")

        if exportar_csv:
            csv_path = salvar_csv(flashcards)
            with open(csv_path, "rb") as f:
                st.download_button("⬇️ Baixar CSV", f, file_name="flashcards.csv")

        if exportar_apkg:
            apkg_path = salvar_apkg(flashcards)
            with open(apkg_path, "rb") as f:
                st.download_button("⬇️ Baixar APKG (Anki)", f, file_name="flashcards.apkg")
    else:
        st.warning("Nenhum flashcard válido foi gerado.")

    end_time = time.time()
    st.info(f"Tempo total de processamento: {end_time - start_time:.2f} segundos")

    if 'logs' in st.session_state and st.session_state.logs:
        st.text_area("Logs de erros e avisos:", "\n".join(st.session_state.logs), height=150)
