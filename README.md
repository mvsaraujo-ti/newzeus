# Zeus

Sistema inteligente de consulta e gerenciamento de contatos institucionais.

**Developer: Maxwell Araujo**

O Zeus permite consultar ramais e outros contatos institucionais por unidade, comarca e competência, além de oferecer um painel administrativo para manter essas informações atualizadas.

> O projeto está em desenvolvimento contínuo. As informações institucionais disponíveis dependem dos dados cadastrados pelos administradores.

## Funcionalidades

### Chat público
- Consulta de ramais e contatos institucionais.
- Busca inteligente com normalização de texto, acentos, ordinais e variações de escrita.
- Busca por nome da unidade, comarca e competências cadastradas.
- Desambiguação de unidades homônimas: quando necessário, o Zeus solicita que o usuário informe a comarca.
- Continuidade de uma pergunta de esclarecimento na mesma aba.
- Apresentação dos contatos em cartões, com destaque visual para ramais.
- Renderização segura dos dados cadastrados.

### Painel administrativo
- Dashboard com indicadores disponíveis no banco de dados.
- Cadastro, consulta, edição e pesquisa de unidades.
- Filtros por nome, categoria, comarca e situação.
- Cadastro e gerenciamento de múltiplos contatos por unidade.
- Tipos de contato: ramal, telefone, WhatsApp, e-mail e outros.
- Cadastro e gerenciamento de competências das unidades.
- Gerenciamento de usuários e perfis.
- Perfis de administrador e operador, com permissões aplicadas no backend.
- Auditoria de alterações administrativas.

### Segurança e persistência
- SQLite como fonte única de verdade para as consultas.
- SQLAlchemy para mapeamento dos dados.
- Senhas protegidas com Argon2id.
- Sessões administrativas com tokens aleatórios e cookies HttpOnly.
- Proteção CSRF nas operações administrativas de escrita.
- Auditoria gravada na mesma transação da alteração correspondente.
- Desativação e exclusão lógica para preservar o histórico dos registros.

## Arquitetura e tecnologias

- Python
- FastAPI
- SQLAlchemy
- SQLite
- HTML, CSS e JavaScript
- pytest
- Argon2id para proteção de senhas

O endpoint público `POST /chat` mantém o contrato de resposta existente:

```json
{
  "resposta": "Texto da resposta do Zeus",
  "dados": {}
}
```

O arquivo JSON utilizado na carga inicial não é a fonte de consulta em tempo de execução. As consultas públicas utilizam o banco SQLite.

## Estrutura funcional

O projeto está organizado em módulos de aplicação, serviços, modelos, rotas administrativas, frontend, dados e testes. Os nomes e caminhos exatos devem ser conferidos na versão do código que acompanha este README.

Principais responsabilidades:

- **Autenticação:** login, sessões e autorização por perfil.
- **Administração:** dashboard, unidades, contatos, usuários e auditoria.
- **Busca inteligente:** interpretação da pergunta, normalização, identificação de unidade, comarca e competência.
- **Chat:** comunicação com o endpoint público e apresentação segura das respostas.
- **Banco de dados:** persistência de unidades, contatos, competências, usuários, sessões e auditoria.

## Requisitos

- Python 3.11 ou versão compatível com as dependências do projeto.
- Git.
- Linux, macOS ou Windows com ambiente Python configurado.

Consulte também o arquivo `requirements.txt` e a configuração do projeto para confirmar a versão de Python efetivamente suportada.

## Instalação local

Clone o repositório:

```bash
git clone https://github.com/mvsaraujo-ti/newzeus.git
cd newzeus
```

Crie e ative um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell, a ativação é:

```powershell
.venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Caso o projeto tenha dependências de desenvolvimento separadas, instale-as também:

```bash
pip install -r requirements-dev.txt
```

## Configuração

O projeto utiliza variáveis de ambiente para configurações sensíveis.

1. Consulte o arquivo `.env.example`, se presente.
2. Crie o arquivo local `.env`.
3. Configure os valores exigidos pela aplicação.
4. Gere um segredo de sessão forte e exclusivo para o ambiente.

Exemplo para gerar um segredo:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Configure o valor em `OI_ZEUS_SESSION_SECRET`, conforme a configuração de autenticação do projeto.

**Nunca versionar o arquivo `.env`, senhas, tokens, chaves privadas ou o banco de dados com dados reais.** Confira o `.gitignore` antes do primeiro envio.

## Criar o primeiro administrador

A autenticação do Zeus prevê a criação explícita do primeiro usuário administrador. Com o ambiente virtual ativado e as variáveis de ambiente configuradas, execute:

```bash
python -m app.create_admin
```

Siga as instruções do comando para cadastrar as credenciais. Não compartilhe senhas ou segredos em logs, commits ou conversas.

## Executar a aplicação

O comando utilizado durante o desenvolvimento local foi:

```bash
uvicorn app.main:app --reload --port 8001
```

Acesse:

- Chat público: http://127.0.0.1:8001/
- Painel administrativo: http://127.0.0.1:8001/admin/login

A porta pode ser ajustada conforme a configuração local.

## Testes

Com o ambiente virtual ativado e as dependências de desenvolvimento instaladas:

```bash
pytest
```

No último ciclo de validação informado pelo desenvolvimento, a suíte completa apresentou **62 testes aprovados**. Esse resultado é referente àquele ciclo e deve ser confirmado novamente após clonar e executar o código deste repositório.

## Evolução do projeto

O desenvolvimento foi organizado em etapas:

1. **Diagnóstico:** análise da aplicação original e da busca de ramais.
2. **Persistência:** integração do SQLite e SQLAlchemy, preservando os dados iniciais.
3. **Busca inteligente:** normalização, interpretação de perguntas, identificação de unidades e testes.
4. **Autenticação:** login administrativo, proteção de senhas, sessões e perfis.
5. **Painel administrativo:** dashboard, unidades, contatos, usuários, permissões e auditoria.
6. **Identidade e interface:** consolidação do nome Zeus, identificação do desenvolvedor e melhorias visuais.
7. **Busca multicomarca:** diferenciação por comarca, busca por competências cadastradas, esclarecimento de ambiguidades e cartões de contatos com ramais destacados.

## Observações importantes

- O Zeus não deve inferir competências que não estejam cadastradas.
- Quando houver unidades com nomes iguais em comarcas diferentes, a busca deve solicitar esclarecimento se a comarca não estiver informada.
- Unidades e contatos inativos não devem aparecer nas consultas públicas.
- Os dados oficiais devem ser conferidos antes de serem cadastrados ou atualizados.
- Para produção, é necessário revisar configurações de segurança, HTTPS, backup, persistência, logs, execução do servidor e política de acesso.

## Desenvolvedor

**Maxwell Araujo**

Projeto: **Zeus**
