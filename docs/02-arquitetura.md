# 2. Arquitetura recomendada

## 2.1 Alternativas avaliadas

| Alternativa | Como funcionaria | Avaliação |
|---|---|---|
| **A. Extensão de navegador** sobre as telas originais | Reestilizar/reorganizar o DOM do JSF no Firefox Portable | Limita-se ao layout das telas existentes (não permite fluxo em etapas, rascunho, cenários, conferência prévia); o Firefox Portable 45 não aceita extensões modernas; DOM do RichFaces 3.3 é instável para manipulação. **Descartada** |
| **B. Adaptar a interface existente** (editar `.xhtml`/CSS do WAR) | Alterar arquivos da aplicação instalada | Modifica o programa oficial (risco jurídico e de suporte), é sobrescrita a cada atualização e mistura responsabilidades. **Descartada** |
| **C. Gravar direto no banco H2** | SQL nas tabelas do PJe-Calc | Contorna validações, regras Drools e invariantes do motor; banco bloqueado pelo processo. **Vedada** |
| **D. Gerar `.PJC` próprio e importar** | Montar o XML e usar “Importar” | Exigiria reproduzir o modelo de dados interno (engenharia reversa frágil); a validação ocorre só na importação. **Descartada como caminho principal** (o `.PJC` é usado apenas para *ler* resultados e trocar arquivos oficiais) |
| **E. Aplicativo local conectado à instalação, operando a interface oficial** | Servidor local que preenche as telas JSF por HTTP, como um navegador, e lê relatório/`.PJC` | Mantém 100% das validações e do motor; não altera o PJe-Calc; permite fluxo próprio, rascunhos, conferência, cenários; depende das telas por versão (mitigado por testes de equivalência). **Escolhida** |

## 2.2 Visão geral

```
┌──────────────── navegador (127.0.0.1:8765) ────────────────┐
│ web/  Painel · 10 etapas · ajuda · tabelas · resultados     │
└───────────────▲─────────────────────────────────────────────┘
                │ JSON (cabeçalho X-PJeCalc-Studio, Host verificado)
┌───────────────┴──────────── servidor.py ────────────────────┐
│ armazenamento  rascunho · revisões · auditoria · modelos    │──► dados/ (JSON, backups .zip)
│ conferencia    verificações preventivas (sem cálculo)       │
│ sincronizar    gravar (rascunho → telas) · executar         │
│ relatorio      lê relatório oficial e .PJC; compara         │
│ ponte/pjecalc  operações sobre as telas oficiais            │
│ ponte/jsf      cliente JSF/A4J (campos, eventos, botões)    │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTP 127.0.0.1:9257 (mesmas requisições do navegador)
┌───────────────▼──────────── PJe-Calc Cidadão (inalterado) ──┐
│ Tomcat · JSF/Seam · validadores · motor · H2 · Jasper       │
└─────────────────────────────────────────────────────────────┘
```

## 2.3 Princípios

1. **Motor intocado.** Nenhuma fórmula é reimplementada. Valores exibidos como resultado vêm do
   relatório oficial e do `.PJC`, com versão, data/hora da liquidação, revisão das entradas e
   SHA-256 do arquivo. A interface não mostra “estimativas” próprias.
2. **Validação oficial é soberana.** A conferência preventiva só antecipa problemas de
   preenchimento; toda gravação passa pelas telas do PJe-Calc, e as mensagens dele são exibidas
   com a severidade original (marcador “Erro./Alerta./Sucesso.”).
3. **Rascunho ≠ gravado ≠ calculado.** Três estados sempre visíveis: revisão do rascunho, revisão
   gravada no PJe-Calc (nº do cálculo) e revisão usada na última execução. Qualquer edição torna o
   resultado “desatualizado”.
4. **Idempotência e retomada.** Cada etapa da gravação registra o que já foi sincronizado (hash por
   histórico, verba, FGTS, atualização). Uma falha no meio preserva o vínculo com o cálculo, e a nova
   tentativa continua no mesmo cálculo.
5. **Local e offline.** Servidor só em 127.0.0.1, interface sem CDN, dados em JSON local, registros
   técnicos sem dados pessoais (método, rota, status).
6. **Continuidade.** O cálculo gravado pode ser aberto e editado na interface original a qualquer
   momento (nº informado na etapa Documentos).
7. **Nenhuma tela com o visual antigo.** As funções sem formulário próprio são lidas da tela oficial e
   desenhadas pelo Studio (`ponte/tela.py`); valores e botões voltam para a mesma tela, que valida e grava.

## 2.4 Componentes principais

- **Telas redesenhadas (`ponte/tela.py`)** — abre cada função do PJe-Calc numa sessão própria, descreve a
  página (grupos, abas, campos com rótulo, ajuda e erro, tabelas com ações, paginação, botões) e repassa
  valores, cliques, envio e download de arquivos; a interface (`visaoTela` em `web/app.js`) desenha a descrição.

- **Cliente JSF (`ponte/jsf.py`)** — lê formulários, mantém o `javax.faces.ViewState`, dispara os
  eventos `A4J.AJAX.Submit` declarados em `onchange/onclick` (ex.: escolher o estado carrega os
  municípios), aciona botões e links, trata redirecionamentos AJAX e uploads do `rich:fileUpload`.
- **Operações (`ponte/pjecalc.py`)** — cada operação percorre o menu do PJe-Calc e devolve um
  `Resultado` com as mensagens oficiais.
- **Leitura de resultados (`ponte/relatorio.py`)** — reconstrói a grade do relatório Jasper
  (`colspan`, `rowspan`, tabelas aninhadas) e lê o XML do `.PJC`.
- **Armazenamento (`ponte/armazenamento.py`)** — gravação atômica, revisões completas, trilha de
  auditoria (quem, quando, o quê), lixeira, modelos versionados sem dados pessoais e backups com
  manifesto SHA-256 e restauração verificada.

## 2.5 Tecnologias e justificativa

Python 3 (somente biblioteca padrão) e HTML/CSS/JavaScript sem dependências: instalação simples,
funcionamento offline, nenhuma cadeia de pacotes de terceiros, fácil auditoria do código por
escritórios. Alternativas como Electron ou .NET foram evitadas no MVP pelo tamanho e pela
manutenção; um empacotamento como executável único pode ser feito depois (ver roteiro).
