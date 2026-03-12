import streamlit as st
import pandas as pd
import os
import time
import requests
import urllib.parse
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
import extra_streamlit_components as stx

# Adiciona a raiz do projeto no sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from adapters.repositories.sqlite_repo import SQLiteRepository
from use_cases.auth_use_cases import AuthUseCases, SettingsUseCases
from use_cases.job_use_cases import JobUseCases
from use_cases.role_use_cases import RoleUseCases
from use_cases.resume_use_cases import ResumeUseCases
from use_cases.ai_service import analyze_full_resume, parse_resume_from_pdf_text
from use_cases.pdf_reader import extract_text_from_pdf
from use_cases.pdf_generator import generate_resume_pdf

load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8501")

def get_redirect_uri():
    """Retorna a URI de redirecionamento configurada no .env (deve corresponder exatamente ao Google Console)."""
    return GOOGLE_REDIRECT_URI

st.set_page_config(page_title="Job Hunter Dashboard", page_icon="🕵️", layout="wide")

# Ocultar botão de Deploy nativo do Streamlit e rodapé
st.markdown("""
    <style>
        .stAppDeployButton {display:none;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Instanciação Limpa: O Streamlit não sabe o que é um banco de dados, apenas consome Casos de Uso.
repo = SQLiteRepository()
auth_uc = AuthUseCases(repo)
settings_uc = SettingsUseCases(repo)
job_uc = JobUseCases(repo)
role_uc = RoleUseCases(repo)
resume_uc = ResumeUseCases(repo)

def authenticate_google_code(code):
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": get_redirect_uri()
    }
    
    try:
        res = requests.post(token_url, data=payload, timeout=10)
        if res.status_code == 200:
            access_token = res.json().get("access_token")
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            user_res = requests.get(user_info_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            if user_res.status_code == 200:
                return user_res.json(), None
            return None, f"Erro ao buscar dados do usuário: HTTP {user_res.status_code}"
        return None, f"Falha na troca do código OAuth (HTTP {res.status_code}): {res.text[:200]}"
    except Exception as e:
        return None, f"Erro de conexão com o Google: {e}"

# --- GERENCIADOR DE COOKIES (Sessão Persistente) ---
cookie_manager = stx.CookieManager(key="jh_session_cookie_mgr")

# --- AUTHENTICATION UI ---
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
    st.session_state['just_logged_out'] = False

# ⚠️ Google OAuth PRIMEIRO — antes de qualquer rerun de cookie
if "code" in st.query_params and st.session_state['user_id'] is None:
    oauth_code = st.query_params["code"]
    with st.spinner("Autenticando com segurança via Google..."):
        user_info, auth_error = authenticate_google_code(oauth_code)
        if user_info and "email" in user_info:
            email = user_info["email"]
            uid = auth_uc.login_oauth(email)
            st.session_state['user_id'] = uid
            st.session_state['just_logged_out'] = False
            st.session_state['_cookie_checked'] = True
            try:
                expires = datetime.now() + timedelta(days=30)
                cookie_manager.set("jh_user_id", str(uid), expires_at=expires)
            except Exception:
                pass
            st.query_params.clear()
            st.rerun()
        else:
            st.query_params.clear()
            st.session_state['_cookie_checked'] = True  # Evita rerun do cookie
            st.error(f"❌ Falha ao autenticar com o Google.")
            if auth_error:
                st.error(f"Detalhe do erro: {auth_error}")
            
            # Dica proativa sobre Redirect URI
            current_url = get_redirect_uri() # Simplificado para mostrar o esperado
            st.info(f"💡 Verifique se a sua URL no navegador é exatamente **{current_url}**. Se estiver usando o IP da rede ou 127.0.0.1, o Google pode bloquear o login.")
            
            if "invalid_grant" in (auth_error or ""):
                st.warning("O código de autenticação expirou ou já foi usado. Tente novamente.")

# Controla se já tentamos carregar o cookie (evita loop infinito)
if '_cookie_checked' not in st.session_state:
    st.session_state['_cookie_checked'] = False

# Restaura sessão do cookie se o session_state estiver vazio (ex: após F5)
if st.session_state['user_id'] is None and not st.session_state.get('just_logged_out', False):
    saved_uid = cookie_manager.get("jh_user_id")
    if saved_uid:
        try:
            st.session_state['user_id'] = int(saved_uid)
        except (ValueError, TypeError):
            cookie_manager.delete("jh_user_id")
    elif not st.session_state['_cookie_checked']:
        # Na 1ª execução após F5, o CookieManager ainda não carregou.
        st.session_state['_cookie_checked'] = True
        st.rerun()


if st.session_state['user_id'] is None:
    st.title("🕵️ Job Hunter - Login")
    st.markdown("Bem-vindo! Faça login na sua conta ou crie uma nova para ter seu painel privado de buscas.")
    
    tab1, tab2 = st.tabs(["🔒 Entrar", "✨ Criar Conta"])
    
    with tab1:
        with st.form("login_form"):
            st.subheader("Já possui conta?")
            l_email = st.text_input("E-mail")
            l_pass = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar no Dashboard", type="primary")
            if submitted:
                if not l_email or not l_pass:
                    st.error("Preencha todos os campos.")
                else:
                    uid = auth_uc.login_local(l_email, l_pass)
                    if uid:
                        st.session_state['user_id'] = uid
                        st.session_state['just_logged_out'] = False
                        try:
                            expires = datetime.now() + timedelta(days=30)
                            cookie_manager.set("jh_user_id", str(uid), expires_at=expires)
                        except Exception:
                            pass
                        st.success("Login realizado com sucesso!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("Novo por aqui?")
            r_email = st.text_input("E-mail")
            r_pass = st.text_input("Senha", type="password")
            r_pass_conf = st.text_input("Confirmar Senha", type="password")
            registered = st.form_submit_button("Criar Conta e Entrar")
            if registered:
                if not r_email or not r_pass:
                    st.error("Preencha todos os campos.")
                elif r_pass != r_pass_conf:
                    st.error("As senhas não coincidem.")
                else:
                    uid = auth_uc.register_local(r_email, r_pass)
                    if uid:
                        st.session_state['user_id'] = uid
                        st.session_state['just_logged_out'] = False
                        try:
                            expires = datetime.now() + timedelta(days=30)
                            cookie_manager.set("jh_user_id", str(uid), expires_at=expires)
                        except Exception:
                            pass
                        st.success("Conta criada! Redirecionando para o seu dashboard...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Este e-mail já está em uso na plataforma.")
                        
    st.markdown("---")
    st.markdown("### Ou entre instantaneamente com o Google")
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_CLIENT_ID != "INSIRA_SEU_CLIENT_ID_AQUI":
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": get_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent"
        }
        login_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
        st.markdown(f'''
            <a href="{login_url}" target="_self" style="text-decoration:none;">
                <div style="
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    background-color: #ffffff; 
                    color: #757575; 
                    font-family: Roboto, Arial, sans-serif; 
                    font-weight: 500; 
                    font-size: 15px; 
                    padding: 10px 14px; 
                    border: 1px solid #dadce0; 
                    border-radius: 4px; 
                    cursor: pointer; 
                    transition: box-shadow 0.2s;
                    box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15);
                " onmouseover="this.style.backgroundColor='#f8f9fa';" onmouseout="this.style.backgroundColor='#ffffff';">
                    <img src="https://developers.google.com/identity/images/g-logo.png" style="width: 18px; height: 18px; margin-right: 12px;" alt="Google Logo">
                    <span>Continuar com o Google</span>
                </div>
            </a>
        ''', unsafe_allow_html=True)
    else:
        st.info("⚠️ Para ativar o botão de login com o Google, preencha as chaves de API no arquivo .env!")
    st.stop()


# --- START OF LOGGED-IN SCOPE ---
user_id = st.session_state['user_id']

col_t1, col_t2 = st.columns([5, 1], vertical_alignment="center")
with col_t1:
    st.title("🕵️ Job Hunter - Seu Painel Privado")
    st.markdown("Monitoramento de vagas isolado para a sua conta.")
with col_t2:
    if st.button("🚪 Sair", use_container_width=True, help="Encerrar a sessão de forma segura"):
        cookie_manager.delete("jh_user_id")
        st.session_state['user_id'] = None
        st.session_state['just_logged_out'] = True
        st.rerun()

try:
    df_jobs = job_uc.get_jobs_dataframe(user_id)
    df_runs = job_uc.get_runs_dataframe(user_id)
except Exception as e:
    st.error(f"Erro a carregar dados do banco: {str(e)}")
    st.stop()

# ----- GLOBAL DATAFRAME NORMALIZATION -----
if not df_jobs.empty:
    for bool_col in ['applied', 'is_invalid']:
        if bool_col in df_jobs.columns:
            mask = df_jobs[bool_col].fillna(False)
            if mask.dtype == object:
                df_jobs[bool_col] = mask.astype(str).str.lower().isin(['1', 'true', 'yes'])
            else:
                df_jobs[bool_col] = mask.astype(bool)
        else:
            df_jobs[bool_col] = False

# ----- KPIs E GRÁFICOS -----
if not df_jobs.empty:
    total_vagas = len(df_jobs)
    aplicadas = int(df_jobs['applied'].sum())
    hoje = pd.Timestamp.now().date()
    novas_hoje = len(df_jobs[pd.to_datetime(df_jobs['discovered_at']).dt.date == hoje]) if 'discovered_at' in df_jobs.columns else 0
    invalidas = int(df_jobs['is_invalid'].sum())

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("📋 Vagas Salvas", total_vagas)
    kpi2.metric("🙋 Candidaturas", aplicadas)
    kpi3.metric("🆕 Hoje", novas_hoje)
    kpi4.metric("⚠️ Expiradas", invalidas)

    st.markdown("---")

    with st.expander("📊 Gráficos e Análises", expanded=True):
        gc1, gc2 = st.columns(2)

        with gc1:
            st.write("**Vagas por Cargo**")
            vagas_por_cargo = df_jobs.groupby('role').size().reset_index(name='Quantidade').sort_values('Quantidade', ascending=False).head(10)
            st.bar_chart(vagas_por_cargo.set_index('role'), use_container_width=True)

        with gc2:
            st.write("**Home Office vs Presencial**")
            if 'is_home_office' in df_jobs.columns:
                ho_counts = df_jobs['is_home_office'].map({1: 'Home Office', 0: 'Presencial', True: 'Home Office', False: 'Presencial'}).value_counts().reset_index()
                ho_counts.columns = ['Modalidade', 'Quantidade']
                st.bar_chart(ho_counts.set_index('Modalidade'), use_container_width=True)

        if 'discovered_at' in df_jobs.columns:
            st.write("**Vagas Descobertas por Dia (últimos 30 dias)**")
            df_timeline = df_jobs.copy()
            df_timeline['Data'] = pd.to_datetime(df_timeline['discovered_at']).dt.date
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
            df_timeline = df_timeline[pd.to_datetime(df_timeline['discovered_at']) >= cutoff]
            vagas_por_dia = df_timeline.groupby('Data').size().reset_index(name='Novas Vagas')
            if not vagas_por_dia.empty:
                st.line_chart(vagas_por_dia.set_index('Data'), use_container_width=True)
            else:
                st.info("Sem dados dos últimos 30 dias.")

st.markdown("---")

st.subheader("🎯 Seus Cargos Alvo")
st.markdown("Adicione ou remova cargos que o robô deve procurar para você diariamente.")


with st.form("add_role_form", clear_on_submit=True):
    new_role = st.text_input(
        "Adicionar novo cargo (Ex: Engenheiro de Software):",
        help=(
            "Dica: use variações do mesmo cargo para encontrar mais vagas.\n\n"
            "Ex: 'Arquiteto de Software' + 'Software Architect' + 'Arquiteto de Soluções'.\n\n"
            "Empresas brasileiras frequentemente postam em inglês — cadastrar ambos aumenta "
            "muito o volume de resultados!"
        )
    )
    submitted = st.form_submit_button("Salvar", type="primary")
    if submitted and new_role.strip():
        if role_uc.add_role(user_id, new_role.strip()):
            st.success(f"Cargo '{new_role}' adicionado!")
        else:
            st.error(f"O cargo '{new_role}' já existe na sua lista.")

roles_data = role_uc.get_all_roles(user_id)
if roles_data:
    df_roles = pd.DataFrame([vars(r) for r in roles_data])
    for i, row in df_roles.iterrows():
        col_name, col_action = st.columns([3, 1], vertical_alignment="center")
        with col_name:
            if row['is_active']:
                st.markdown(f"✅ **{row['role_name']}**")
            else:
                st.markdown(f"⏸️ ~~{row['role_name']}~~")
        with col_action:
            btn_label = "Desativar" if row['is_active'] else "Ativar"
            btn_type = "secondary" if row['is_active'] else "primary"
            if st.button(btn_label, key=f"toggle_{row['id']}", use_container_width=True, type=btn_type):
                role_uc.toggle_role_status(user_id, row['id'], not row['is_active'])
                st.rerun()
else:
    st.info("Sua lista de cargos está vazia. Adicione acima para iniciar suas buscas.")

st.markdown("---")

st.subheader("🌍 Regras de Busca")
with st.expander("Configurações do Robô", expanded=True):
    current_countries = settings_uc.get_countries(user_id)
    available_countries = ["Brasil", "Portugal", "Estados Unidos", "Canadá", "Espanha", "Reino Unido", "Austrália", "Alemanha", "Holanda", "Irlanda"]
    
    for c in current_countries:
        if c and c not in available_countries:
            available_countries.append(c)
            
    selected_countries = st.multiselect(
        "Selecione os Países Alvo:", 
        options=available_countries,
        default=current_countries,
        help="O robô fará uma varredura para cada país selecionado nesta lista."
    )

    current_freq = settings_uc.get_frequency(user_id)
    safe_freq = max(10, int(current_freq))
    new_freq = st.number_input("Periodicidade do robô (Minutos):", min_value=10, max_value=4320, value=safe_freq)

    if st.button("Salvar Configurações", use_container_width=True, type="primary"):
        if not selected_countries:
            st.error("Por favor, selecione pelo menos um país.")
        else:
            settings_uc.set_countries(user_id, selected_countries)
            settings_uc.set_frequency(user_id, str(new_freq))
            st.success("Configurações atualizadas! O robô no servidor vai notar a mudança logo.")
            time.sleep(1)
            st.rerun()

st.markdown("---")

import subprocess
st.subheader("⚙️ Histórico do Robô (Sua Conta)")
col_btn, col_info = st.columns([1, 4])
with col_btn:
    if st.button("🚀 Forçar Busca na Própria Máquina Agora", type="primary", use_container_width=True):
        with st.spinner("Procurando vagas em seu nome..."):
            scraper_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'background', 'run_scraper.py')
            try:
                subprocess.run(['python', scraper_path, '--limit', '200', '--no-proxy', '--user-id', str(user_id)], capture_output=True)
                st.success("Busca finalizada!")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
        
if not df_runs.empty:
    view_runs = df_runs.copy()
    view_runs['timestamp'] = pd.to_datetime(view_runs['timestamp']).dt.strftime('%d/%m/%Y %H:%M:%S')
    view_runs.columns = ['ID Execução', 'User ID', 'Data da Varredura', 'Cargos Pesquisados', 'Novas Vagas Salvas']
    view_runs = view_runs.drop(columns=['User ID'])
    st.dataframe(view_runs, use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma busca rodou para sua conta ainda.")

st.markdown("---")

with st.expander("👥 Usuários da Plataforma", expanded=False):
    all_users = auth_uc.get_all_users()
    if all_users:
        from infrastructure.database.connection import get_connection as _get_conn
        conn_admin = _get_conn()
        user_rows = []
        for u in all_users:
            cursor_adm = conn_admin.cursor()
            cursor_adm.execute("SELECT COUNT(*) FROM jobs WHERE user_id = ?", (u.id,))
            total_jobs = cursor_adm.fetchone()[0]
            cursor_adm.execute("SELECT COUNT(*) FROM jobs WHERE user_id = ? AND applied = 1", (u.id,))
            applied_jobs = cursor_adm.fetchone()[0]
            cursor_adm.execute("SELECT MAX(timestamp) FROM runs WHERE user_id = ?", (u.id,))
            last_run_row = cursor_adm.fetchone()[0]
            last_run = last_run_row[:16] if last_run_row else "Nunca"
            created = u.created_at[:10] if u.created_at else "N/A"
            you_badge = " ⭐ (você)" if u.id == user_id else ""
            user_rows.append({
                "ID": u.id,
                "E-mail": u.email + you_badge,
                "Cadastro": created,
                "Vagas Salvas": total_jobs,
                "Candidaturas": applied_jobs,
                "Última Busca": last_run
            })
        conn_admin.close()
        df_users = pd.DataFrame(user_rows)
        st.dataframe(df_users, use_container_width=True, hide_index=True)
        st.caption(f"Total: **{len(all_users)}** usuário(s) cadastrado(s) na plataforma.")
    else:
        st.info("Nenhum usuário cadastrado.")

st.markdown("---")

if df_jobs.empty:
    st.info("Ainda não existem vagas salvas para a sua conta. Adicione cargos e instigue a primeira busca!")
    st.stop()

tab_vagas, tab_crm, tab_resume = st.tabs(["🎯 Caça de Vagas", "🤝 Meus Processos Seletivos", "📄 Meu Currículo (IA)"])

with tab_resume:
    st.subheader("📄 Construtor de Currículo (AI-Powered)")
    st.markdown("Preencha suas informações para gerar um PDF otimizado para softwares de RH e receber dicas da nossa Inteligência Artificial.")

    # --- IMPORTAR PDF DO LINKEDIN ---
    with st.expander("📥 Importar PDF do LinkedIn (preenche o formulário automaticamente)", expanded=False):
        st.info("💡 **Como fazer:** No LinkedIn, acesse seu perfil → clique em **'Mais'** → **'Salvar como PDF'** → faça o upload aqui.")
        uploaded_pdf = st.file_uploader("Selecione o PDF exportado do LinkedIn", type=["pdf"], key="linkedin_pdf_upload")

        import_col1, import_col2 = st.columns([1, 3])
        with import_col1:
            import_btn = st.button("🤖 Importar e Preencher com IA", type="primary", use_container_width=True, disabled=uploaded_pdf is None)

        if import_btn and uploaded_pdf is not None:
            with st.spinner("Lendo o PDF e extraindo as informações com IA... Isso pode levar alguns segundos."):
                try:
                    from use_cases.pdf_reader import extract_text_from_pdf
                    from use_cases.ai_service import parse_resume_from_pdf_text

                    raw_text = extract_text_from_pdf(uploaded_pdf.read())
                    if not raw_text.strip():
                        st.error("Não foi possível extrair texto deste PDF. Certifique-se de que é o PDF exportado diretamente pelo LinkedIn (não uma imagem escaneada).")
                    else:
                        parsed = parse_resume_from_pdf_text(raw_text)
                        if "error" in parsed:
                            st.error(f"Erro na IA: {parsed['error']}")
                        else:
                            st.session_state['pdf_import'] = parsed
                            st.success("✅ Currículo importado com sucesso! O formulário abaixo foi preenchido automaticamente. Revise os dados e clique em **Salvar**.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar o PDF: {str(e)}")

    # Usa dados importados do PDF, sugestão da IA, ou dados salvos no banco
    pdf_import = st.session_state.get('pdf_import', {})
    ai_fill = st.session_state.get('ai_fill', {})
    current_resume = resume_uc.get_resume(user_id)

    def _val(field):
        # Prioridade: sugestão IA > PDF importado > dados salvos no banco > vazio
        return ai_fill.get(field) or pdf_import.get(field) or getattr(current_resume, field, '') or ''

    res_data = {
        'full_name': _val('full_name'), 'email': _val('email'),
        'phone': _val('phone'), 'linkedin': _val('linkedin'),
        'portfolio': _val('portfolio'), 'professional_summary': _val('professional_summary'),
        'experience': _val('experience'), 'education': _val('education'),
        'skills': _val('skills'), 'languages': _val('languages'),
    }


    with st.form("resume_form"):
        st.write("### 👤 Informações Pessoais")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            f_name = st.text_input("Nome Completo", value=res_data['full_name'])
            f_email = st.text_input("E-mail Profissional", value=res_data['email'])
            f_linkedin = st.text_input("LinkedIn (URL)", value=res_data['linkedin'])
        with col_r2:
            f_phone = st.text_input("Telefone / WhatsApp", value=res_data['phone'])
            f_portfolio = st.text_input("Portfólio / GitHub (URL)", value=res_data['portfolio'])
            
        st.markdown("---")
        st.write("### ✍️ Resumo Profissional")
        f_summary = st.text_area("Um breve descritivo sobre o seu perfil direcionado aos recrutadores...", value=res_data['professional_summary'], height=150)
        
        st.markdown("---")
        st.write("### 🏢 Experiência Profissional")
        f_exp = st.text_area("Liste suas experiências. Recomendamos o formato:\nCargo - Empresa (Período)\n- Realização 1\n- Realização 2", value=res_data['experience'], height=250)
        
        st.markdown("---")
        st.write("### 🎓 Formação Acadêmica & Conhecimentos")
        col_r3, col_r4 = st.columns(2)
        with col_r3:
            f_edu = st.text_area("Formação Acadêmica (Faculdades, Cursos Técnicos...)", value=res_data['education'], height=150)
            f_lang = st.text_area("Idiomas", value=res_data['languages'], height=100)
        with col_r4:
            f_skills = st.text_area("Hard Skills & Soft Skills (Separadas por vírgula)", value=res_data['skills'], height=280)
            
        saved_resume = st.form_submit_button("💾 Salvar Dados do Currículo", type="primary", use_container_width=True)
        if saved_resume:
            new_data = {
                'full_name': f_name, 'email': f_email, 'phone': f_phone, 'linkedin': f_linkedin, 'portfolio': f_portfolio,
                'professional_summary': f_summary, 'experience': f_exp, 'education': f_edu, 'skills': f_skills, 'languages': f_lang
            }
            resume_uc.save_resume(user_id, new_data)
            st.success("Currículo salvo na sua conta com sucesso!")
            time.sleep(1)
            st.rerun()
            
    # --- ACÕES DE CURRÍCULO (PDF E IA) ---
    st.markdown("---")
    col_a1, col_a2 = st.columns(2)
    
    with col_a1:
        st.write("### 📥 Exportar Currículo")
        pdf_color = st.color_picker("Cor dos títulos das seções", value="#2980B9", key="pdf_color")
        if st.button("Gerar Arquivo PDF", use_container_width=True):
            if current_resume and current_resume.full_name:
                with st.spinner("Desenhando seu currículo..."):
                    hex_c = pdf_color.lstrip("#")
                    primary_rgb = tuple(int(hex_c[i:i+2], 16) for i in (0, 2, 4))
                    pdf_path = generate_resume_pdf(current_resume, primary_color=primary_rgb)
                    with open(pdf_path, "rb") as pdf_file:
                        pdf_bytes = pdf_file.read()
                    
                    st.download_button(
                        label="⬇️ Clique aqui para Baixar seu PDF",
                        data=pdf_bytes,
                        file_name=f"Curriculo_{current_resume.full_name.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
            else:
                st.warning("Você precisa salvar o currículo preenchido pelo menos uma vez antes de gerar o PDF.")
                
    with col_a2:
        st.write("### ✨ Assistente IA (Gemini)")
        if st.button("🤖 Analisar Currículo Completo", use_container_width=True, type="primary"):
            if current_resume and (current_resume.experience or current_resume.professional_summary):
                with st.spinner("O Gemini está analisando seu currículo... Aguarde."):
                    from use_cases.ai_service import analyze_full_resume
                    suggestion = analyze_full_resume(
                        summary=current_resume.professional_summary or "",
                        experience=current_resume.experience or "",
                        skills=current_resume.skills or ""
                    )
                    st.session_state['ai_suggestion'] = suggestion
            else:
                st.warning("Preencha e salve ao menos o Resumo Profissional ou a Experiência antes de analisar.")

        if 'ai_suggestion' in st.session_state and st.session_state['ai_suggestion']:
            with st.expander("Analise e Sugestoes da IA", expanded=True):
                st.text(st.session_state['ai_suggestion'])

                if st.button("Preencher formulario com esta sugestao", type="primary", use_container_width=True):
                    raw = st.session_state['ai_suggestion']

                    def _extract(text, start_marker, end_markers):
                        """Extrai o bloco de texto entre start_marker e o proximo marcador."""
                        upper = text.upper()
                        idx = upper.find(start_marker.upper())
                        if idx == -1:
                            return ""
                        # Pula o titulo da secao
                        block_start = text.find('\n', idx)
                        if block_start == -1:
                            return ""
                        block_start += 1
                        # Encontra o proximo marcador
                        end_idx = len(text)
                        for em in end_markers:
                            ei = upper.find(em.upper(), block_start)
                            if ei != -1 and ei < end_idx:
                                end_idx = ei
                        return text[block_start:end_idx].strip()

                    all_markers = ["RESUMO PROFISSIONAL", "EXPERIENCIA PROFISSIONAL", "HARD SKILLS", "SOFT SKILLS"]
                    resumo = _extract(raw, "RESUMO PROFISSIONAL", ["EXPERIENCIA PROFISSIONAL", "HARD SKILLS", "SOFT SKILLS"])
                    experiencia = _extract(raw, "EXPERIENCIA PROFISSIONAL", ["HARD SKILLS", "SOFT SKILLS"])
                    hard = _extract(raw, "HARD SKILLS", ["SOFT SKILLS"])
                    soft = _extract(raw, "SOFT SKILLS", [])

                    skills_combined = (hard + ("\n" + soft if soft else "")).strip()

                    st.session_state['ai_fill'] = {
                        'professional_summary': resumo,
                        'experience': experiencia,
                        'skills': skills_combined,
                    }
                    st.session_state.pop('ai_suggestion', None)
                    st.rerun()


with tab_vagas:
    st.subheader("📋 Vagas Encontradas")
    with st.expander("Filtros Avançados", expanded=False):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            roles_list = ["Todos"] + list(df_jobs['role'].unique())
            selected_role = st.selectbox("Filtrar por Cargo:", roles_list)
            search_term = st.text_input("Buscar (Título/Empresa):", "")
            
        with f_col2:
            st.write("Visibilidade")
            home_office_only = st.checkbox("Só Home Office", value=False)
            show_invalid = st.checkbox("Exibir Vagas Expiradas", value=False)
            hide_applied = st.checkbox("Ocultar Vagas Já Aplicadas", value=True)

    filtered_df = df_jobs.copy()

    if not filtered_df.empty and 'discovered_at' in filtered_df.columns:
        filtered_df['discovered_at_dt'] = pd.to_datetime(filtered_df['discovered_at'])

    if selected_role != "Todos":
        filtered_df = filtered_df[filtered_df['role'] == selected_role]

    if search_term:
        search_term = search_term.lower()
        mask = (
            filtered_df['title'].str.lower().str.contains(search_term, na=False) | 
            filtered_df['company'].str.lower().str.contains(search_term, na=False) |
            filtered_df['description'].str.lower().str.contains(search_term, na=False)
        )
        filtered_df = filtered_df[mask]

    if home_office_only:
        filtered_df = filtered_df[filtered_df['is_home_office'] == 1]

    if hide_applied:
        filtered_df = filtered_df[filtered_df['applied'] == 0]

    if not show_invalid and 'is_invalid' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['is_invalid'] == 0]

    if not filtered_df.empty:
        filtered_df['Data'] = filtered_df['discovered_at_dt'].dt.strftime('%d/%m/%Y')
    else:
        filtered_df['Data'] = []

    filtered_df['Home Office?'] = filtered_df['is_home_office'].apply(lambda x: '✅ Sim' if x else '❌ Não')

    if 'applied' not in filtered_df.columns:
        filtered_df['applied'] = False
    else:
        filtered_df['applied'] = filtered_df['applied'].astype(bool)

    if 'is_invalid' not in filtered_df.columns:
        filtered_df['is_invalid'] = False
    else:
        filtered_df['is_invalid'] = filtered_df['is_invalid'].astype(bool)

    filtered_df['title'] = filtered_df.apply(
        lambda row: f"🚫 {row['title']} (EXPIRADA)" if row['is_invalid'] else row['title'], 
        axis=1
    )

    view_df = filtered_df[['id', 'Data', 'role', 'title', 'company', 'Home Office?', 'email', 'url', 'apply_link', 'applied', 'is_invalid']].copy()
    view_df['🔍'] = False
    view_df['Excluir'] = False 
    view_df.columns = ['ID', 'Data', 'Cargo', 'Título', 'Empresa', 'Home Office', 'Email', 'Link Principal', 'Link Candidatura', 'Aplicada', 'Inválida', '🔍', 'Excluir']

    edited_df = st.data_editor(
        view_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": None,
            "Link Principal": None,
            "Link Candidatura": None,
            "🔍": st.column_config.CheckboxColumn("🔍 Ver Links", width="small"),
            "Aplicada": st.column_config.CheckboxColumn("🙋‍♂️ Já apliquei?"),
            "Inválida": st.column_config.CheckboxColumn("⚠️ Expirada"),
            "Excluir": st.column_config.CheckboxColumn("🗑️ Excluir")
        },
        disabled=["Data", "Cargo", "Título", "Empresa", "Home Office", "Email", "Link Principal", "Link Candidatura"]
    )

    st.caption(f"Você possui {len(view_df)} vagas filtradas no momento.")

    has_target_changes = False
    for i in range(len(edited_df)):
        orig_row = view_df.iloc[i]
        new_row = edited_df.iloc[i]
        
        if new_row['Excluir']:
            job_uc.delete_job(user_id, new_row['ID'])
            has_target_changes = True
        elif new_row['Aplicada'] != orig_row['Aplicada']:
            job_uc.mark_job_applied(user_id, new_row['ID'], new_row['Aplicada'])
            has_target_changes = True
        elif new_row['Inválida'] != orig_row['Inválida']:
            job_uc.mark_job_invalid(user_id, new_row['ID'], new_row['Inválida'])
            has_target_changes = True

    if has_target_changes:
        st.rerun()

    # --- VISUALIZAÇÃO DE LINKS (LUPA) ---
    selected_rows = edited_df[edited_df['🔍'] == True]
    if not selected_rows.empty:
        for _, row in selected_rows.iterrows():
            with st.container(border=True):
                st.markdown(f"#### 🔍 Detalhes: {row['Título']}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Empresa:** {row['Empresa']}")
                    st.markdown(f"**Cargo:** {row['Cargo']}")
                with c2:
                    if row['Link Principal']:
                        st.link_button("🌐 Ver Vaga Original", row['Link Principal'], use_container_width=True)
                    if row['Link Candidatura']:
                        st.link_button("🚀 Link Direto de Candidatura", row['Link Candidatura'], use_container_width=True, type="primary")
                    if row['Email']:
                        st.markdown(f"📧 **E-mail de Contato:** {row['Email']}")
                
                # Botão para fechar a visualização (apenas desmarcando a checkbox)
                if st.button(f"Fechar Visualização de {row['ID']}", key=f"close_{row['ID']}"):
                    # Como o Streamlit trabalha com estados, o ideal seria manipular o session_state se quiséssemos algo mais complexo.
                    # Mas desmarcar a checkbox no grid já remove o frame no próximo ciclo se o usuário desmarcar manualmente.
                    st.info("Desmarque a lupa no grid para fechar esta seção.")

with tab_crm:
    st.subheader("📊 Kanban de Processos Seletivos")
    st.markdown("Acompanhe o status e avalie as empresas das vagas que você já aplicou. Veja quem está te dando *Ghosting*.")
    
    # Garantir Cast Booleano Limpo (Lidando com NULLS e Tipos Genéricos do SQLite)
    _applied_mask = df_jobs['applied'].fillna(False)
    if _applied_mask.dtype == object:
        _applied_mask = _applied_mask.astype(str).str.lower().isin(['1', 'true', 'yes'])
    else:
        _applied_mask = _applied_mask.astype(bool)
        
    crm_df = df_jobs[_applied_mask].copy()
    
    if crm_df.empty:
        st.info("Você ainda não marcou nenhuma vaga como 'Aplicada' na aba de Caça de Vagas.")
    else:
        if 'discovered_at' in crm_df.columns:
            crm_df['discovered_at_dt'] = pd.to_datetime(crm_df['discovered_at'])
            crm_df = crm_df.sort_values(by='discovered_at_dt', ascending=False)
            crm_df['Data'] = crm_df['discovered_at_dt'].dt.strftime('%d/%m/%Y')
        else:
            crm_df['Data'] = []

        # Certificar que as colunas novas existem no dataframe pego (resiliencia de db)
        if 'application_status' not in crm_df.columns: crm_df['application_status'] = 'Enviado'
        if 'company_rating' not in crm_df.columns: crm_df['company_rating'] = 0
            
        view_crm = crm_df[['id', 'Data', 'company', 'title', 'application_status', 'company_rating', 'url', 'applied']].copy()
        view_crm.columns = ['ID', 'Encontrada em', 'Empresa', 'Vaga', 'Status', 'Nota (1 a 5)', 'Link', 'Desaplicar']
        view_crm['Desaplicar'] = False

        edited_crm = st.data_editor(
            view_crm,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": None,
                "Encontrada em": st.column_config.TextColumn(disabled=True),
                "Empresa": st.column_config.TextColumn(disabled=True),
                "Vaga": st.column_config.TextColumn(disabled=True),
                "Link": st.column_config.LinkColumn("Acessar Link", display_text="Ver", max_chars=100, disabled=True),
                "Status": st.column_config.SelectboxColumn(
                    "Status do Processo",
                    help="Em que fase da contratação você está?",
                    options=["Enviado", "Em Andamento", "Entrevista", "Teste Técnico", "Rejeitado", "⚠️ Ghosting", "🎉 Oferta!"],
                    required=True
                ),
                "Nota (1 a 5)": st.column_config.NumberColumn(
                    "Nota da Empresa",
                    help="Qual nota você daria para o desenrolar com essa empresa?",
                    min_value=0,
                    max_value=5,
                    step=1,
                    format="%d ⭐"
                ),
                "Desaplicar": st.column_config.CheckboxColumn("❌ Desaplicar")
            }
        )
        
        has_crm_changes = False
        for i in range(len(edited_crm)):
            orig_row = view_crm.iloc[i]
            new_row = edited_crm.iloc[i]
            row_id = new_row['ID']
            
            if new_row['Desaplicar']:
                job_uc.mark_job_applied(user_id, row_id, False)
                has_crm_changes = True
            elif new_row['Status'] != orig_row['Status']:
                job_uc.update_job_status(user_id, row_id, new_row['Status'])
                has_crm_changes = True
            elif new_row['Nota (1 a 5)'] != orig_row['Nota (1 a 5)']:
                job_uc.update_job_rating(user_id, row_id, new_row['Nota (1 a 5)'])
                has_crm_changes = True
                
        if has_crm_changes:
            st.rerun()
