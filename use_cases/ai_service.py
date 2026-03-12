import os
import json
import google.generativeai as genai

def get_gemini_api_key():
    # Attempt to read from env or return None
    key = os.environ.get("GEMINI_API_KEY")
    return key if key and key != "SUA_CHAVE_GEMINI_AQUI" else None

def improve_resume_experience(experience_text: str) -> str:
    """Mantido para compatibilidade. Use analyze_full_resume para análise completa."""
    return analyze_full_resume(experience=experience_text)

def analyze_full_resume(summary: str = "", experience: str = "", skills: str = "") -> str:
    """Usa o Gemini para analisar e reescrever as seções principais do currículo:
    Resumo Profissional, Experiência Profissional, Hard Skills e Soft Skills.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return "⚠️ Erro: A chave API do Gemini não foi configurada. Por favor adicione GEMINI_API_KEY no arquivo .env."

    if not summary and not experience and not skills:
        return "⚠️ Nenhum conteúdo fornecido para analisar. Preencha ao menos uma seção."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""
Você é um Headhunter Sênior especialista em currículos para sistemas ATS.
Analise as seções do currículo abaixo e entregue uma versão melhorada.

REGRAS OBRIGATORIAS DE FORMATACAO:
- Use APENAS texto puro: sem emojis, sem asteriscos (*), sem markdown (**, __, ##, -, *).
- Separe as secoes com uma linha em branco e o titulo da secao em MAIUSCULAS seguido de dois-pontos.
- Use recuo com espacos ou tabulacao para listas.
- Mantenha o idioma em Portugues do Brasil.
- Use verbos de acao no inicio de cada conquista ou responsabilidade.
- Foque em resultados quantificaveis (ex: Reduzi em 30% o tempo de...).
- Retorne APENAS o texto estruturado, sem comentarios adicionais.

Formato esperado:

RESUMO PROFISSIONAL:
[texto do resumo]

EXPERIENCIA PROFISSIONAL:
[cargo - empresa (periodo)]
   - realizacao 1
   - realizacao 2

HARD SKILLS:
   Linguagens: Python, Java
   Ferramentas: Git, Docker
   Metodologias: Scrum, Kanban

SOFT SKILLS:
   - habilidade 1
   - habilidade 2

---

DADOS DO CANDIDATO:

RESUMO ATUAL:
{summary or "(nao preenchido)"}

EXPERIENCIA ATUAL:
{experience or "(nao preenchida)"}

HABILIDADES ATUAIS:
{skills or "(nao preenchidas)"}
        """

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"ERRO: Ocorreu um erro ao comunicar com a IA: {str(e)}"



def parse_resume_from_pdf_text(raw_text: str) -> dict:
    """Usa o Gemini para estruturar o texto bruto de um PDF do LinkedIn nos campos do currículo.
    Retorna um dicionário com os campos: full_name, email, phone, linkedin, portfolio,
    professional_summary, experience, education, skills, languages.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return {"error": "GEMINI_API_KEY não configurada no arquivo .env."}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""
        Você receberá o texto bruto extraído de um currículo em PDF (possivelmente exportado do LinkedIn).
        Sua tarefa é extrair e organizar as informações nos seguintes campos:
        - full_name: Nome completo
        - email: E-mail de contato
        - phone: Telefone
        - linkedin: URL do perfil LinkedIn (se houver)
        - portfolio: URL de portfólio, GitHub ou site pessoal (se houver)
        - professional_summary: Resumo/Objetivo profissional
        - experience: Todas as experiências profissionais formatadas como "Cargo - Empresa (Período)\\n- Responsabilidade"
        - education: Formação acadêmica
        - skills: Lista de habilidades técnicas e comportamentais separadas por vírgula
        - languages: Idiomas e níveis de fluência

        Retorne APENAS um JSON válido com esses campos. Se um campo não for encontrado, retorne string vazia "".
        Não adicione nenhum texto fora do JSON. Não use markdown adicional.

        TEXTO DO CURRÍCULO:
        {raw_text[:8000]}
        """

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Remove markdown code block if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        return {"error": f"IA retornou formato inválido: {str(e)}"}
    except Exception as e:
        return {"error": f"Erro ao comunicar com a IA: {str(e)}"}
