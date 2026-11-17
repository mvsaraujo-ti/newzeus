# Zeus — Resumo de continuidade do projeto

**Projeto:** Zeus  
**Desenvolvedor:** Maxwell Araujo  
**Repositório:** https://github.com/mvsaraujo-ti/newzeus  
**Branch principal:** main  
**Último marco informado:** Etapa 7 concluída

Este documento registra o estado conhecido do projeto para facilitar a continuidade do desenvolvimento em outra conversa ou sessão.

## 1. Objetivo do sistema

O Zeus é um sistema inteligente de consulta e gerenciamento de contatos institucionais. O chat público permite consultar ramais e outros contatos por nome da unidade, comarca e competências cadastradas. O painel administrativo permite manter unidades, contatos, competências e usuários.

O nome oficial do serviço é **Zeus**. Não utilizar "Oi, Zeus" como nome do produto. A identificação do desenvolvedor é **Developer: Maxwell Araujo**.

## 2. Tecnologias e arquitetura

- Python e FastAPI.
- SQLAlchemy e SQLite.
- Frontend em HTML, CSS e JavaScript.
- pytest para testes automatizados.
- Argon2id para hash de senhas.
- Sessões administrativas com tokens aleatórios armazenados como hash e cookies HttpOnly.
- Proteção CSRF para operações administrativas de escrita.

Responsabilidades centrais:
- Chat público: endpoint `POST /chat`.
- Busca inteligente: normalização, interpretação da pergunta, identificação de unidade, comarca e competência, desambiguação e formatação.
- Administração: dashboard, unidades, contatos, usuários, permissões e auditoria.
- Banco: fonte única de verdade das consultas públicas.

O contrato público de `POST /chat` foi preservado nas etapas anteriores e não deve ser alterado sem necessidade explícita.

## 3. Histórico de implementação

### Etapa 1 — Diagnóstico
Análise da estrutura original, do chat e dos dados de ramais. Foram identificados riscos de falso positivo na busca por nomes semelhantes de varas.

### Etapa 2 — SQLite
Integração com SQLite e SQLAlchemy. O arquivo JSON foi mantido como fonte inicial de importação, não como fonte de consulta em tempo de execução. A importação foi descrita como idempotente.

### Etapa 3 — Busca inteligente
Separação da normalização de texto, interpretação de perguntas, identificação da unidade e formatação das respostas. Foram adicionados testes para acentos, ordinais, sinônimos, variações de escrita, erros de digitação e ambiguidades.

### Etapa 4 — Autenticação
Implementação de login administrativo, senhas com Argon2id, sessões revogáveis, perfis administrador e operador, cookie HttpOnly, CSRF e limitação de tentativas. O primeiro administrador foi criado localmente com sucesso.

### Etapa 5 — Painel administrativo
Implementação de dashboard, CRUD de unidades e contatos, gerenciamento de usuários, permissões aplicadas no backend e auditoria. A tabela de auditoria foi adicionada de forma aditiva ao SQLite. O chat público passou a ignorar unidades e contatos inativos.

### Etapa 6 — Identidade e interface
Consolidação da marca **Zeus**, sem o prefixo "Oi". Identificação do desenvolvedor como **Maxwell Araujo**. Foram aprimoradas a identidade visual, a interface do chat e a interface administrativa, preservando funcionalidades existentes.

### Etapa 7 — Busca multicomarca, competências e destaque dos contatos
A busca passou a diferenciar unidades por comarca e a solicitar esclarecimento quando existe ambiguidade entre comarcas. Foi adicionada a relação `competencias_unidade` e uma migração aditiva para competências explicitamente identificadas. O banco passou a permitir nomes iguais em comarcas diferentes, prevenindo duplicatas dentro da mesma comarca. O chat passou a apresentar cartões de contatos distintos e destacar ramais em ciano. A renderização dos valores cadastrados foi feita como texto, com teste contra injeção de HTML.

## 4. Estado mais recente informado

Segundo o relatório do Codex após a Etapa 7:

- 62 testes automatizados aprovados.
- 22 unidades cadastradas.
- 25 contatos cadastrados.
- 11 competências migradas.
- Migração criou a tabela `competencias_unidade`.
- Restrição de nome global foi removida para permitir homônimos em comarcas diferentes.
- Verificação de chaves estrangeiras: zero erros.
- Nova execução do backfill adicionou zero registros.
- Fluxo de esclarecimento validado.
- Destaque visual dos ramais validado em viewport de 390 px, sem overflow horizontal.
- Endpoint `POST /chat` e seu contrato preservados.

Esses números são o último estado relatado e devem ser conferidos no banco e na suíte de testes antes de qualquer operação de migração ou publicação.

## 5. Exemplos de comportamento implementado

- Pergunta por uma unidade homônima sem comarca: o Zeus pede para escolher a comarca.
- Após resposta "Balsas": o Zeus usa a comarca para resolver a unidade pretendida.
- Consulta de competência, como Saúde Pública em Balsas: localiza unidade somente quando a competência está cadastrada.
- Unidade não localizada na comarca solicitada: informa que não encontrou, sem substituir automaticamente por outra comarca.
- Contatos tipados como ramal recebem destaque visual ciano.
- Valores de contatos são renderizados com segurança, sem interpretar HTML fornecido nos dados cadastrados.

O contexto de esclarecimento foi descrito como temporário: dura uma resposta e fica na memória da aba, sem persistência ou compartilhamento entre usuários. Não presumir que o sistema possui memória conversacional geral ou persistente.

## 6. Execução local conhecida

Durante o desenvolvimento, o projeto foi executado com:

```bash
uvicorn app.main:app --reload --port 8001
```

Endereços locais informados:
- Chat: http://127.0.0.1:8001/
- Login administrativo: http://127.0.0.1:8001/admin/login
- Painel: http://127.0.0.1:8001/admin

O módulo de criação do primeiro administrador foi executado com:

```bash
python -m app.create_admin
```

Ativar o ambiente virtual antes dos comandos Python. Conferir o diretório real do projeto e os arquivos de configuração antes de executar operações.

## 7. Segurança e cuidados de publicação

Antes de enviar código ao GitHub:
- Conferir `.gitignore`.
- Não versionar `.env`, segredos, tokens, senhas, `.venv/`, caches ou banco SQLite com dados locais.
- Manter `.env.example` apenas com valores fictícios/de exemplo.
- Verificar se algum arquivo sensível já está sendo rastreado pelo Git.
- Não apagar nem recriar o banco local.
- Não executar migrações destrutivas sem backup e análise.

Antes de implantação em produção:
- Configurar HTTPS e cookies seguros.
- Definir segredo exclusivo para o ambiente.
- Planejar backup e restauração do SQLite.
- Definir estratégia de execução do servidor e logs.
- Rever limites de tentativa de login e configuração para múltiplos workers.
- Validar permissões, CSRF, dados e testes no ambiente-alvo.

## 8. Próximos passos possíveis

Não há uma Etapa 8 implementada neste registro. Próximas evoluções a avaliar, após revisar o código atual:

1. Importação e atualização em lote de unidades, competências e contatos, com pré-visualização, validação e relatório de erros.
2. Histórico de consultas e indicadores reais de utilização, respeitando privacidade e minimização de dados.
3. Backup, restauração e rotina de manutenção do banco.
4. Preparação para implantação institucional, com configuração de produção e checklist de segurança.
5. Continuidade conversacional mais robusta, caso seja necessário manter contexto por mais de uma resposta ou em mais de uma pergunta.

Não iniciar uma dessas evoluções antes de examinar o estado atual do código e confirmar se alguma parte já foi desenvolvida.

## 9. Orientação para a próxima sessão

Ao continuar o projeto:
1. Consultar este arquivo e o README.
2. Revisar o código real do repositório e o estado local antes de propor alterações.
3. Preservar o que já funciona: chat público, contrato de `POST /chat`, busca inteligente, autenticação, painel, permissões, auditoria e migrações.
4. Fazer alterações incrementais.
5. Adicionar testes para cada mudança.
6. Executar toda a suíte antes de considerar uma etapa concluída.

**Identidade:** Zeus  
**Developer:** Maxwell Araujo
