# Como publicar o PJe-Calc Studio no GitHub

Guia para quem mantém o projeto. Na primeira vez leva uns 10 minutos; depois, cada versão nova é um comando.

## Primeira vez

### 1. Crie a conta e o repositório (no navegador)

1. Crie uma conta em [github.com/signup](https://github.com/signup), se ainda não tiver.
2. Crie um repositório novo em [github.com/new](https://github.com/new):
   - **Repository name:** `pjecalc-studio`
   - **Public**
   - **Não** marque "Add a README", ".gitignore" nem "license": o projeto já tem tudo isso, e o repositório
     precisa começar vazio.
3. Clique em **Create repository**.

### 2. Envie o projeto (no seu computador)

Precisa do Git. Se o comando `git --version` não funcionar no PowerShell, instale com
`winget install Git.Git` e abra o PowerShell de novo.

Na pasta do projeto, rode (troque `SEU-USUARIO` pelo seu usuário do GitHub):

```powershell
powershell -ExecutionPolicy Bypass -File tools\publicar-no-github.ps1 -Usuario SEU-USUARIO
```

O script:

1. coloca o seu usuário nos links de download, no instalador e na atualização automática;
2. pergunta o nome e o e-mail que vão aparecer no histórico. Para não expor o seu e-mail, use o e-mail privado
   do GitHub: github.com › Settings › Emails, algo como `12345678+SEU-USUARIO@users.noreply.github.com`;
3. envia o código. Na primeira vez, o navegador abre para você entrar na conta do GitHub e autorizar;
4. pergunta se já pode publicar a primeira versão. Responda **S**.

### 3. Confira

Em uns 5 minutos, a aba **Actions** do repositório mostra "Publicar versão" com um ✓ verde. A versão aparece
em **Releases**, com o `PJeCalcStudio-Instalador.exe`, e o botão "Baixar o instalador" do README passa a
funcionar.

Se aparecer um ✗ vermelho, clique nele para ver o passo que falhou. Corrija e publique de novo com outro
número de versão.

## Cada versão nova

1. Em `NOVIDADES.md`, acrescente no topo a seção da versão nova, com o que mudou, escrito para quem usa:

   ```markdown
   ## 0.2.1

   - Corrigido o envio de férias com abono.
   ```

2. Rode:

   ```powershell
   powershell -ExecutionPolicy Bypass -File tools\publicar-versao.ps1 -Versao 0.2.1
   ```

O script troca a versão em `servidor.py`, grava as mudanças, cria a versão e envia ao GitHub. O GitHub roda os
testes, gera o instalador e publica a versão. Quem já usa o Studio recebe o aviso de atualização em até 12
horas, ou na hora, em **Configurações › Atualizações › Verificar agora**.

Números de versão: o último muda em correções (0.2.0 → 0.2.1), o do meio em novidades (0.2.1 → 0.3.0).

## Opcional: tirar o aviso azul do Windows

Sem assinatura de código, o Windows mostra "O Windows protegeu o computador" ao abrir o instalador, e o README
explica como seguir. Para tirar o aviso é preciso um certificado de assinatura de código, que é pago. Com o
arquivo `.pfx` do certificado em mãos:

1. Converta o arquivo para texto: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\caminho\codigo.pfx")) | Set-Clipboard`
2. No repositório, vá em **Settings › Secrets and variables › Actions › New repository secret** e crie:
   - `CERTIFICADO_PFX_BASE64`: cole o texto copiado;
   - `CERTIFICADO_PFX_SENHA`: a senha do `.pfx`.

As versões seguintes já saem assinadas.
