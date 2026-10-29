# Desenvolvimento

O PJe-Calc Studio é um servidor local em Python (só a biblioteca padrão, sem dependências) que serve uma
interface web (HTML, CSS e JavaScript sem bibliotecas externas, funciona offline) e opera o PJe-Calc Cidadão
instalado no computador pela própria interface dele, como um navegador faria. Nada é gravado direto no banco
do PJe-Calc: quem valida, grava e calcula é sempre o PJe-Calc.

> Testado com o PJe-Calc Cidadão **2.16.0** (build 25/06/2026) numa instância de teste: fluxo completo,
> reabertura do `.PJC` exportado sem divergências e testes de integração (ver `docs/05`). A prova de
> equivalência com casos preenchidos manualmente na interface original ainda está pendente. Outras versões
> exibem um alerta de compatibilidade.

## Rodar pelo código-fonte

Requisitos: Windows 10 ou 11, Python 3.10+ e o PJe-Calc Cidadão aberto.

```bash
py -3 -I servidor.py
```

Ou dois cliques em `iniciar.bat`. O navegador abre em `http://127.0.0.1:8765/`; os cálculos ficam em `dados/`.
Opções: `--porta`, `--dados <pasta>`, `--pjecalc <url do PJe-Calc>`, `--sem-navegador`.

## Testes

Sem o PJe-Calc (os mesmos que o GitHub roda a cada envio, `.github/workflows/testes.yml`):

```bash
py -I tests/test_unidades.py
py -I tests/mcp_fluxo.py
py -I tests/atualizacao_fluxo.py
```

Com uma instância de teste do PJe-Calc em portas alternativas (`tools/iniciar-instancia-teste.ps1`):

```bash
py -I tests/fluxo_completo.py http://127.0.0.1:19257/pjecalc/
py -I tests/ocorrencias_verbas_manuais.py http://127.0.0.1:19257/pjecalc/
```

Com o PJe-Calc e o Studio abertos, operando as telas reais sem salvar nada:

```bash
py -I tests/mcp_telas_pjecalc.py %LOCALAPPDATA%\PJeCalcStudio\conexao.json <id de um cálculo já enviado>
```

## Instalador

`tools/gerar-instalador.ps1` monta o pacote (programa + Python portátil enxuto, `tools/empacotar.ps1`) e gera o
instalador com o Inno Setup 6 (`instalador/PJeCalcStudio.iss`):

```bash
winget install JRSoftware.InnoSetup
powershell -ExecutionPolicy Bypass -File tools\gerar-instalador.ps1
```

Saída em `dist/`: `PJeCalcStudio-<versão>.exe`, a cópia `PJeCalcStudio-Instalador.exe` e o `.sha256` dela.

- Instala só para o usuário, sem pedir administrador, em `%LOCALAPPDATA%\Programs\PJeCalcStudio`, com atalhos no
  menu Iniciar (Studio e "Como usar") e, se o usuário quiser, na Área de Trabalho.
- O Studio roda sem janela de console (`pythonw`); os registros vão para `dados\studio.log`.
- Os cálculos ficam em `%LOCALAPPDATA%\PJeCalcStudio\dados`, fora da pasta do programa: atualizar ou
  desinstalar não os apaga.
- Assinatura de código (opcional): `-Impressao <thumbprint>` ou `-Pfx <arquivo.pfx>` (senha em
  `PJSTUDIO_PFX_SENHA`), via `tools/assinar.ps1`. Sem certificado, o Windows mostra o aviso do SmartScreen.

No GitHub, o instalador é gerado sozinho a cada versão publicada (`.github/workflows/release.yml`); veja
[PUBLICAR.md](../PUBLICAR.md).

## Atualização automática

`ponte/atualizacao.py`: ao abrir e a cada 12 horas, o Studio instalado consulta a última release do repositório
(`REPOSITORIO` no início do arquivo; outro endereço pela variável `PJECALC_STUDIO_ATUALIZACOES`). Havendo versão
nova, mostra o aviso no topo; em **Configurações › Atualizações**, um clique baixa
`PJeCalcStudio-Instalador.exe` por HTTPS, confere o SHA-256 publicado (o `digest` da API do GitHub ou o arquivo
`.sha256` da release), roda o instalador em silêncio e reabre o Studio. Rascunhos, pré-releases, releases sem
instalador ou sem SHA-256 e downloads que não conferem são ignorados. Rodando pelo código-fonte, o Studio só avisa.

## Assistentes Claude e Codex (MCP)

O Claude (Claude Desktop ou Claude Code) e o Codex operam o Studio pelas mesmas regras da interface: ler e criar
cálculos, responder as perguntas guiadas, preencher campos (com as mesmas validações de CPF, CNPJ, número CNJ,
datas e valores), escolher e configurar verbas, históricos, correção e juros, conferir, enviar ao PJe-Calc e ler o
resultado.

- As ferramentas ficam no Studio (`ponte/assistente.py`), atendidas em `POST /mcp` com o protocolo MCP. Os
  argumentos de cada chamada são conferidos com o esquema da ferramenta antes de executar. O endereço só aceita a
  própria máquina, exige a chave do assistente (gerada na pasta de dados) e recusa pedidos com origem de site.
- Ao iniciar, o Studio grava em `%LOCALAPPDATA%\PJeCalcStudio\conexao.json` o endereço, a chave e a lista de
  ferramentas (outro caminho: variável `PJECALC_STUDIO_CONEXAO`).
- As pontes só repassam mensagens, lendo esse arquivo: a extensão do Claude Desktop (`extensao/`, Node que vem com
  o Claude Desktop, empacotada como `.mcpb` pelo próprio Studio em `/api/claude/extensao.mcpb`) e `mcp_studio.py`
  (Python, para o Claude Code e o Codex). Com o Studio fechado, elas respondem a lista de ferramentas e pedem para
  abrir o Studio.
- Além das etapas do Studio, o assistente opera todas as telas do PJe-Calc (`telas_pjecalc`, `abrir_tela`,
  `preencher_tela`, `acionar_tela`), pelo mesmo mecanismo de "Funções do PJe-Calc" (`ponte/tela.py`).
- Regras do assistente (`INSTRUCOES` em `ponte/assistente.py`): fiel ao documento; na omissão, usa o padrão do
  PJe-Calc e avisa; pergunta só o indispensável; faz tudo sozinho e confere o resultado com o documento.

## Estrutura

| Pasta/arquivo | Conteúdo |
|---|---|
| `servidor.py` | Servidor local (API JSON + arquivos da interface), somente em 127.0.0.1 |
| `ponte/atualizacao.py`, `instalador/`, `tools/gerar-instalador.ps1` | Atualização automática e instalador (Inno Setup; assinatura em `tools/assinar.ps1`) |
| `ponte/assistente.py` | Assistentes Claude e Codex: ferramentas MCP (atendidas pelo servidor em `/mcp`) |
| `extensao/`, `mcp_studio.py` | Pontes MCP: extensão do Claude Desktop (`.mcpb`) e ponte para o Claude Code e o Codex |
| `ponte/jsf.py` | Cliente HTTP para a interface JSF/RichFaces do PJe-Calc (como um navegador) |
| `ponte/pjecalc.py` | Operações: criar/abrir, dados, históricos (CSV oficial), verbas, reflexos, FGTS, atualização, liquidar, relatório, exportar, importar |
| `ponte/sincronizar.py` | Rascunho → PJe-Calc (gravar) e execução (liquidar + arquivos oficiais) |
| `ponte/relatorio.py` | Leitura do relatório oficial (HTML) e do `.PJC`; comparação entre cálculos |
| `ponte/conferencia.py` | Conferência preventiva (não calcula verbas) |
| `ponte/armazenamento.py` | Rascunhos, revisões, auditoria, modelos e backups em JSON local |
| `ponte/tela.py` | Funções do PJe-Calc no visual do Studio: lê cada tela oficial e repassa valores e cliques |
| `ponte/padroes.py` | Padrões do escritório: repete numa função do PJe-Calc um preenchimento gravado |
| `ponte/ajuda_oficial.py` | Extrai os textos de ajuda das telas da versão instalada |
| `web/` | Interface; `ajuda.js` e `ajuda-pjecalc.js`: textos de ajuda |
| `tests/` | Testes unitários, MCP, atualização, fluxo completo, reabertura de `.PJC` e equivalência |
| `tools/` | Instalador, publicação no GitHub e ferramentas de desenvolvimento |
| `docs/` | Diagnóstico, arquitetura, telas, roadmap, plano de equivalência, instalação, cobertura, padrões |
