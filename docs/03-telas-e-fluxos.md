# 3. Mapa de telas e fluxos

## 3.1 Telas

| Tela | Rota | Conteúdo |
|---|---|---|
| Cálculos (painel) | `#/` | “Continuar de onde parei” (cálculo mais recente, com a etapa real e a situação), “Precisam de atenção” (resultado desatualizado, alterações não enviadas, pendências do PJe-Calc), lista com pesquisa, filtros (situação; responsável e etiqueta no modo Avançado), favoritos, densidade confortável/compacta, “Abrir” e menu “Mais” por cálculo (ver resultado, duplicar como cenário, lixeira) |
| Novo cálculo | diálogo | Em branco ou modelo, com todas as premissas exibidas antes da criação (itens “Confirmar” destacados) |
| Importar `.PJC` | diálogo | Importa pela tela oficial e lê os dados de volta |
| Trazer do PJe-Calc | diálogo | Lista os cálculos do PJe-Calc (busca por nº ou reclamante), indica os já ligados ao Studio e liga um cálculo existente sem duplicá-lo (dados, históricos mês a mês, lista de verbas) |
| Funções do PJe-Calc (do cálculo) | `#/caso/<id>/original/<tela>` | As 27 telas oficiais do cálculo (Cálculo, Operações e Atualização de pagamentos) dentro do Studio, abertas automaticamente no cálculo e no item de menu certos; status, “Recarregar a tela”, “Abrir em outra janela”. Atalho “Tela completa no PJe-Calc ↗” no cabeçalho de cada etapa |
| Funções do PJe-Calc (geral) | `#/original/<tela>` | Novo Cálculo Externo, Relatório Consolidado, Buscar e as 13 Tabelas |
| Cálculo | `#/caso/<id>/<etapa>` | Quatro fases com subetapas: **Caso** (Partes e processo, Contrato) → **Dados e verbas** (Histórico salarial, Jornada, Verbas, Reflexos e FGTS, Correção e juros) → **Conferência** (Revisar tudo, Enviar e calcular) → **Resultado** (Resultado, Documentos) |
| Resultado | `#/caso/<id>/resultado[/<execução>]` | Líquido em destaque, bruto, descontos e total do reclamado; detalhamento por verba; créditos/descontos e débitos por credor; valores mês a mês; critérios; documentos oficiais (PDF, .PJC, HTML) e o relatório oficial isolado em `iframe` sem scripts |
| Versões e alterações | `#/caso/<id>/historico-auditoria` | Trilha de auditoria por revisão |
| Comparar cenários | `#/comparar?a=&b=` | Entradas alteradas, motor e tabelas, resumo, créditos/descontos, débitos e diferenças por verba × competência |
| Modelos | `#/modelos` | Modelos iniciais (13) e do escritório (versões, nota, autor) |
| Configurações e diagnóstico | `#/config` | Usuário (auditoria), URL e pasta do PJe-Calc, escritório/logotipo, diagnóstico, backups, atalhos |

Elementos globais: barra superior (pesquisa `Ctrl+K`, status do PJe-Calc, modo Guiado/Avançado,
tamanho do texto, tema claro/escuro). Dentro do cálculo: cabeçalho com identificação, os três estados
do trabalho e os botões **Enviar ao PJe-Calc** e **Calcular** (sempre no mesmo lugar); navegação lateral
por fases com o estado real de cada etapa; barra de continuidade no rodapé da área de trabalho
(etapa anterior, “Continuar: próxima etapa” e o estado do rascunho).

## 3.2 Fluxo principal

```
Novo/Modelo/Importar/Trazer ─► Caso e Dados e verbas (rascunho salvo a cada alteração; revisão + auditoria)
        │                          │
        │        Revisar tudo: resumo por seção com “Alterar” (leva direto ao campo),
        │        itens que impedem o envio × alertas, pendências do PJe-Calc, critérios por verba
        ▼                          ▼
  Enviar ao PJe-Calc ── telas oficiais: Dados → Históricos (CSV oficial) → Verbas (Expresso/Manual)
        │                → Parâmetros/Bases (+ Regerar) → Ocorrências → Reflexos → FGTS → Correção/Juros → Pendências
        ▼
  Calcular ──────────── Pendências oficiais → Liquidar → Relatório HTML/PDF → Exportar .PJC
        ▼
  Resultado (transcrito do oficial) ─► Documentos (.PJC, PDF, HTML, CSV, resumo complementar)
        ▼
  Duplicar como cenário ─► Calcular ─► Comparar
```

## 3.3 Estados exibidos

Sempre visíveis no cabeçalho do cálculo, como três itens separados:

- **Rascunho**: “salvo às HH:MM” (só depois que o servidor confirmou exatamente o que está na tela),
  “salvando…”, “alterações ainda não salvas”, “não salvo (motivo)” com **Tentar salvar de novo**, ou
  “não salvo: o cálculo mudou em outra janela” com **Resolver**.
- **PJe-Calc**: “dados ainda não enviados”, “dados enviados (cálculo nº X)” ou “há alterações não enviadas”.
- **Resultado**: “ainda não calculado”, “atualizado” ou “desatualizado: os dados mudaram depois do cálculo”.
- **Etapas** (navegação lateral): pronta (critério real de preenchimento), em andamento, opcional usando
  o padrão do PJe-Calc, não iniciada, aguardando etapa anterior, com pendência ou com alertas. Visitar
  uma etapa não a marca como pronta.
- **Situação do trabalho**: Rascunho, Em conferência, Calculado, Concluído (revisão do escritório;
  não significa homologação). Editar um cálculo “Calculado/Concluído” volta para “Em conferência”.

## 3.4 Salvamento e conflitos

- Cada edição incrementa uma versão local. Uma gravação só marca “salvo” se nenhuma edição tiver
  acontecido durante a requisição; caso contrário grava de novo. A cópia de recuperação neste
  computador só é apagada quando o servidor confirmou o que está na tela.
- “Enviar ao PJe-Calc” e “Calcular” só prosseguem com o rascunho salvo: nunca enviam ao PJe-Calc uma
  versão diferente da exibida.
- Conflito de revisão (cálculo alterado em outra janela): nada é descartado sem escolha explícita —
  salvar como novo cálculo, substituir pela versão desta janela (a outra fica no histórico) ou
  descartar (com confirmação). Ao reabrir o cálculo, uma cópia pendente de revisão antiga é oferecida
  com as mesmas opções em vez de ser apagada.

## 3.5 Ajuda contextual

Botão “?” junto ao rótulo de cada campo, com nome acessível específico (“Ajuda sobre última
remuneração”); abre por clique, toque, Enter/Espaço ou `F1` no campo. No computador, abre ao lado do
formulário (em telas médias ocupa o lugar da navegação, nunca cobre o campo); em telas estreitas,
como folha inferior, com o campo rolado para o alto. Fecha com o “×” ou `Esc` e devolve o foco ao botão.
A instrução essencial fica sempre visível sob o campo. O painel segue a ordem: resposta direta, o que
é, quando preencher, como preencher, exemplo preenchido, outro exemplo (expansível), erro comum,
vazio × zero × não se aplica, valor automático, efeito no cálculo (só o verificado no PJe-Calc 2.16.0),
ponto não confirmado (quando houver) e referências (expansível, com o texto oficial do PJe-Calc quando
a pasta de instalação está configurada). Conteúdo em `web/ajuda.js`.

## 3.6 Acessibilidade e teclado

Marcos (`header`, `nav`, `main`, `aside`), link “Pular para o conteúdo”, rótulos associados a todos
os campos, `aria-describedby` com a instrução e o erro, `aria-invalid`, mensagens de formato junto ao
campo (“o que está errado, como corrigir, se foi salvo”), região `aria-live` para avisos e estados,
foco no título a cada troca de tela, foco visível de alto contraste, contraste mínimo 4,5:1 nos dois
temas, tabela com `role="grid"` e `aria-activedescendant`, respeito a `prefers-reduced-motion`,
escala de texto 80–150% e layout sem rolagem horizontal a 200% de zoom.

Atalhos: `Ctrl+K` pesquisa; `Ctrl+S` salvar; `Alt+→/←` etapas; `Ctrl+Enter` calcular; `F1` ajuda do
campo; `Esc` fecha ajuda, menu ou diálogo. Na tabela: setas, `Shift`+setas, `Enter`/`F2`, `Tab`,
`Espaço`, `Delete`, `Ctrl+C`, `Ctrl+V` (colar de planilhas), `Ctrl+D` (repetir o primeiro valor), `Ctrl+A`.
