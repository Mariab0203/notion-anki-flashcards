import streamlit as st
import zipfile
import os
import tempfile
import openai
import genanki
import pandas as pd
import yaml
import uuid

# Configurações da página
st.set_page_config(page_title="Flashcards Markdown → Anki", layout="wide")
st.title("🧠 Gerador Inteligente de Flashcards (Markdown Notion)")

# --- AUTENTICAÇÃO ---
senha = st.text_input("🔐 Digite a senha:", type="password")
if senha != st.secrets.get("APP_PASSWORD"):
    st.error("Senha incorreta.")
    st.stop()

# Configuração da API OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Upload de arquivo .zip
uploaded_file = st.file_uploader("📁 Envie o arquivo `.zip` exportado do Notion em Markdown:", type="zip")
max_cards = st.slider("Máximo de flashcards por bloco:", 1, 5, 3)


def extrair_texto_do_zip(zip_file):
    """
    Extrai textos dos arquivos .md contidos no arquivo zip.
    Retorna uma lista de strings.
    """
    textos = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)
        for root, _, files in os.walk(tmpdir):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding="utf-8") as f:
                        textos.append(f.read())
    return textos


def dividir_em_blocos(textos, limite=1000):
    """
    Divide os textos em blocos menores para envio à API, baseando-se em tamanho (caracteres).
    """
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
    """
    Para cada bloco de texto, chama a OpenAI para gerar flashcards em YAML.
    Retorna lista de tuplas (pergunta, resposta).
    """
    flashcards = []
    system_message = (
        "Você é um assistente que gera flashcards úteis em formato YAML com base em conteúdo de texto. "
        "Cada flashcard deve conter os campos 'pergunta' e 'resposta'."
    )
    for i, bloco in enumerate(blocos):
        prompt = f"""
A partir do conteúdo abaixo, gere até {max_cards} flashcards em YAML com campos:
- pergunta:
  resposta:

Conteúdo:
\"\"\"{bloco}\"\"\"
"""
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
                continue

            if isinstance(resultado, list):
                for item in resultado:
                    pergunta = item.get("pergunta")
                    resposta = item.get("resposta")
                    if pergunta and resposta:
                        flashcards.append((pergunta.strip(), resposta.strip()))
            else:
                st.warning(f"Formato inesperado no bloco {i+1}: {type(resultado)}")
                st.text_area(f"Conteúdo retornado pela API no bloco {i+1}", conteudo, height=150)

        except Exception as e:
            st.warning(f"Erro ao gerar flashcards no bloco {i+1}: {e}")

    return flashcards


def salvar_csv(flashcards):
    """
    Salva os flashcards em CSV (TSV) para download.
    """
    df = pd.DataFrame(flashcards, columns=["Front", "Back"])
    path = "flashcards.csv"
    df.to_csv(path, sep="\t", index=False)
    return path


def salvar_apkg(flashcards):
    """
    Salva os flashcards em arquivo .apkg para Anki usando genanki.
    """
    # Model e deck fixos para consistência entre execuções
    model_id = 1607392319
    deck_id = 2059400110
    model = genanki.Model(
        model_id,
        'Modelo Markdown',
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{"name": "Card", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
        css="""
        .card {
            font-family: arial;
            font-size: 18px;
            color: black;
            background-color: white;
        }
        """
    )
    deck = genanki.Deck(deck_id, "Flashcards do Notion")
    for front, back in flashcards:
        deck.add_note(genanki.Note(model=model, fields=[front, back]))
    path = "flashcards.apkg"
    genanki.Package(deck).write_to_file(path)
    return path


# --- PROCESSAMENTO E INTERAÇÃO ---

if uploaded_file and st.button("🚀 Gerar Flashcards"):
    with st.spinner("Extraindo textos do zip..."):
        textos = extrair_texto_do_zip(uploaded_file)

    if not textos:
        st.error("Nenhum arquivo markdown (.md) encontrado no zip.")
        st.stop()

    blocos = dividir_em_blocos(textos)
    st.info(f"{len(blocos)} blocos serão processados.")

    flashcards = gerar_flashcards(blocos, max_cards)
    st.success(f"{len(flashcards)} flashcards gerados!")

    if flashcards:
        # Mostrar alguns exemplos para o usuário
        st.subheader("🔎 Exemplos de Flashcards Gerados")
        for front, back in flashcards[:3]:
            st.markdown(f"**Q:** {front}\n\n**A:** {back}")

        # Salvar arquivos
        csv_path = salvar_csv(flashcards)
        apkg_path = salvar_apkg(flashcards)

        # Criar YAML para download
        yaml_output = yaml.dump(
            [{"pergunta": f, "resposta": b} for f, b in flashcards],
            allow_unicode=True,
            sort_keys=False
        )

        # Botões de download
        with open(csv_path, "rb") as f_csv, open(apkg_path, "rb") as f_apkg:
            st.download_button("⬇️ Baixar CSV", f_csv, file_name="flashcards.csv")
            st.download_button("⬇️ Baixar APKG (Anki)", f_apkg, file_name="flashcards.apkg")

        st.download_button("⬇️ Baixar YAML", yaml_output, file_name="flashcards.yaml")

    else:
        st.warning("Nenhum flashcard válido foi gerado. Tente ajustar os parâmetros ou o conteúdo.")

