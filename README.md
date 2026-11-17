# ZEUS

## Configuração local

Instale as dependências no ambiente virtual do projeto:

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Crie o arquivo `.env` a partir de `.env.example` e gere um segredo de sessão local:

```bash
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Defina o valor gerado em `OI_ZEUS_SESSION_SECRET` no `.env`. Em produção, use `APP_ENV=production` atrás de HTTPS; o cookie de sessão terá o atributo `Secure` habilitado.

## Primeiro administrador

Com o `.env` configurado, execute:

```bash
python -m app.create_admin
```

O comando solicita nome, usuário, senha e confirmação interativamente. A senha é digitada sem eco, precisa ter ao menos 12 caracteres e é armazenada com Argon2id. O comando recusa criar outro administrador inicial.

Inicie o servidor local com `uvicorn app.main:app --reload`. A tela de login fica em `/admin/login`; o endpoint público `/chat` não exige autenticação.

## Painel administrativo

Após autenticar em `/admin/login`, o usuário é direcionado para `/admin`. Administradores têm acesso ao dashboard, usuários e auditoria; operadores podem consultar e editar unidades e contatos, mas não podem alterar a situação de unidades, gerenciar usuários ou consultar auditoria. As mesmas restrições são aplicadas pela API.

O início da aplicação cria a tabela de auditoria caso ainda não exista. Essa migração é aditiva e preserva as tabelas e os registros atuais. Alterações de unidades, contatos e usuários são gravadas junto com o respectivo evento de auditoria.

As rotas JSON do painel ficam sob `/admin/api`: `dashboard`, `units`, `contacts`, `users` e `audit`. Toda escrita autenticada exige o token CSRF fornecido pela sessão. Contatos são desativados logicamente; unidades também são desativadas, não removidas fisicamente.

## Busca por comarca e competência

Competências ficam em registros relacionados à unidade na tabela `competencias_unidade`. Na inicialização, o ZEUS importa de forma repetível competências de descrições com o marcador `Competência:` e de listas curtas segmentadas em descrições de categorias de Vara; o texto original da descrição é preservado. Não são inferidas competências de descrições livres genéricas.

A busca filtra a comarca informada antes de comparar nomes/competências. Se o nome for compatível em mais de uma comarca, o chat solicita esclarecimento. A resposta é mantida apenas na memória JavaScript da aba e é combinada com uma única resposta do usuário; não é persistida, compartilhada entre abas ou enviada como novo campo. O corpo de `POST /chat` continua contendo somente `mensagem`.

As respostas com contatos são montadas pelo frontend usando nós de texto (`textContent`). Apenas valores de contatos cujo tipo cadastrado é `ramal` recebem o estilo de destaque; nomes, competências e números de outros campos não são tratados como ramais.
