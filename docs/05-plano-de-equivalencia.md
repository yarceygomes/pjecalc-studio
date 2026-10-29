# 5. Plano de verificação da equivalência

**Objetivo:** demonstrar que um cálculo feito pela nova interface produz exatamente os mesmos
resultados que o mesmo cálculo feito à mão na interface original, com a mesma versão do PJe-Calc e as
mesmas tabelas auxiliares.

Por construção, a nova interface não calcula: ela envia ao PJe-Calc as mesmas requisições que o
navegador enviaria. A verificação confirma que os **dados chegam íntegros** (nenhum campo perdido,
arredondado ou interpretado de outra forma) e que **os resultados lidos** são transcritos sem erro.

## 5.1 Condições de cada rodada

- Mesma instalação (ou cópia idêntica, conferida por MD5 do instalador) e mesma **versão/build**.
- Tabelas auxiliares atualizadas **no mesmo dia** (registrar a página “Versão das Tabelas”).
- Mesma **data de liquidação** e mesma opção de época própria.
- Dados fictícios ou anonimizados.

## 5.2 Casos de referência (mínimo por versão)

| # | Caso | Recursos exercitados |
|---|---|---|
| 1 | Rescisão sem justa causa, histórico único | dados, aviso calculado/projetado, verbas expressas, multa 40% |
| 2 | Histórico com reajustes e FGTS parcialmente recolhido | CSV oficial, deduções de FGTS |
| 3 | Dois históricos e bases distintas por verba | bases, pendência oficial de base |
| 4 | Prescrição quinquenal (contrato > 5 anos) | prescrição, limites de período |
| 5 | Horas extras com reflexos (após Fase 2) | ocorrências, reflexos, DSR |
| 6 | Critérios de atualização combinados | índice + combinação “a partir de”, juros, base de juros |
| 7 | Pedido de demissão e acordo 484-A | aviso não apurado, multa 20% |
| 8 | `.PJC` importado de outro escritório | importação, dados regionais |

## 5.3 Procedimento

1. Na interface **original**, preencher o caso e liquidar; exportar o `.PJC` e o relatório HTML
   (“Imprimir” › HTML) → `referencia.pjc`, `referencia.html`.
2. Na **nova interface**, preencher o mesmo caso e executar; baixar o `.PJC` e o relatório HTML da
   execução → `nova.pjc`, `nova.html`.
3. Executar:
   ```bash
   py -I tests/equivalencia.py referencia.pjc nova.pjc referencia.html nova.html
   ```
   O script compara versão, data de liquidação, época própria, **cada verba e cada ocorrência**
   (base, divisor, multiplicador, quantidade, devido, pago, índice acumulado), os históricos mês a mês
   e, nos relatórios, resumo, créditos/descontos, débitos do reclamado e critérios. Sai com código 0
   somente se tudo for idêntico.
4. **Reabertura**: `py -I tests/reabertura_pjc.py nova.pjc <URL>` importa o arquivo na tela oficial,
   reliquida e confirma 0 divergências.
5. Registrar o resultado (versão, build, data das tabelas, casos, saída dos scripts) em
   `docs/equivalencia-<versão>.md`.

## 5.4 Resultado já obtido (15/10/2026, PJe-Calc 2.16.0, instância de teste)

| Verificação | Resultado |
|---|---|
| Fluxo completo pela nova interface (caso 2 + bases do caso 3) | Liquidado sem pendências; relatório e `.PJC` gerados |
| Reabertura do `.PJC` exportado (importar → reliquidar → reexportar) | **0 divergências** em 7 verbas, 9 ocorrências e 2 históricos (72 competências); totais idênticos |
| Fase 2 (16/10/2026): HE 50% com quantidades mensais + verbas manuais calculada e informada (`tests/ocorrencias_verbas_manuais.py`) | Liquidado sem pendências de erro; quantidades e valores devidos idênticos no `.PJC`; reabertura com **0 divergências** em 8 verbas e 18 ocorrências, líquido idêntico (a contagem de 15/10 é anterior à correção que passou a ler verbas principais aninhadas em reflexos) |
| Fase 2 (22/10/2026): + verba com HE como base, reflexos manuais, alteração de parâmetros com regeração | Adicional = 10% de HE e reflexo = HE ÷ divisor em todas as competências; após alterar divisor/multiplicador as ocorrências refletem os parâmetros novos e as quantidades informadas; reabertura com **0 divergências** em 11 verbas e 31 ocorrências |
| Cenário com maior remuneração alterada | Diferenças apenas nas verbas cuja fórmula oficial usa a maior remuneração |
| Coerência interna do relatório lido | Soma das verbas = total bruto |
| Prova manual × nova interface (5.3) | **Pendente**: depende de preencher os casos de referência na interface original com as tabelas atualizadas |

## 5.5 Conferência jurídica

A equivalência garante que o PJe-Calc calculou o que recebeu. Ela não valida as **escolhas jurídicas**
(base, divisor, reflexos, índices). Por isso a interface marca essas escolhas como “decisão do
usuário”, guarda o fundamento e mostra o quadro de critérios com a fórmula oficial para revisão.
