# 🕵️ Job Hunter V2 - Guia Rápido de Uso

Bem-vindo à nova versão do **Job Hunter**! Esta versão agora utiliza um banco de dados **SQLite** seguro e rápido, e inclui um lindo painel de visualização (Dashboard) via **Streamlit**, além de um agendador (**Scheduler**) que roda sozinho em segundo plano.

Siga os passos abaixo para configurar e extrair o máximo de valor da ferramenta.

---

## 🛠️ Passo 1: Configurar Suas Vagas Alvo
1. Abra o seu Dashboard executando num terminal: `streamlit run app.py`
2. Pelo Dashboard, navegue até a seção **🎯 Gerenciar Cargos Alvo**.
3. Adicione novos cargos pelo campo de texto.
4. Você pode ativar e desativar buscas nos cargos usando os botões ✅/⏸️.
   **Se é a primeira vez rodando**, seus cargos antigos do arquivo `roles.md` já foram migrados automaticamente para o banco!

---

## 🚀 Passo 2: Executando o Job Hunter 

Para rodar a aplicação inteira (que consiste no robô de buscas automáticas e no Painel de Resultados), você não precisa digitar comandos complicados toda vez!

1. Vá até a pasta `c:\dev\job_hunter`.
2. Clique com o botão direito no arquivo **`start.ps1`** e selecione **"Executar com PowerShell"** (ou execute via terminal com `.\start.ps1`).
3. **O que vai acontecer?**
   - Uma tela azul do PowerShell se abrirá. 
   - O robô (`scheduler.py`) começará a rodar **invisível em segundo plano**. A cada 6 horas ele fará uma varredura nas suas vagas alvo.
   - O seu navegador padrão abrirá uma nova aba automaticamente no endereço `http://localhost:8501/` contendo o Dashboard interativo.

⚠️ **Importante:** Quando quiser parar as varreduras e o Dashboard, basta ir na tela do PowerShell e apertar qualquer tecla para que ele feche tudo corretamente.

---

## 📊 Passo 3: Visualizando Seu Dashboard

O Dashboard (`http://localhost:8501/`) é onde você verá todo o resultado do esforço do seu agendador.

### O que você encontrará no Dashboard:
- **Indicadores Chaves (KPIs):** Entenda no topo o total de vagas retidas no histórico, quantas delas são 100% Home Office e quantas acabaram de ser descobertas "Hoje".
- **Gráficos Dinâmicos:** Analise visualmente quais áreas estão bombando de contratações (Vagas por Cargo) bem como gráficos em formato de linha temporal com cruzamento das suas coletas (Descobertas por Data).
- **Tabela Mágica Filtrável:** A lista completa das suas vagas! 
  Use as opções acima da tabela para visualizar:
  - *"Somente as que estão descritas como Home Office/Remoto"* (caixa de seleção ✅).
  - *"Apenas uma vaga X do dropdown"*.
  - Explore por um *"Termo em Específico"* (Ex: escreva "Sênior" no termo de localização).
  
Na tabela final, aproveite as colunas informativas de `E-mails` que o robô extraiu junto dos seus respectivos links oficiais de acesso!
