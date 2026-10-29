# 4. Funcionalidades — situação e prioridades

Legenda: ✅ implementado e testado contra o PJe-Calc 2.16.0 · 🟡 implementado, teste parcial · ⬜ planejado

## Fase 1 — fluxo completo (entregue)

| Funcionalidade | Situação |
|---|---|
| Criar/abrir cálculo, dados do processo, partes, local, contrato, aviso, prescrição | ✅ |
| Histórico salarial mês a mês, importado pelo CSV oficial; substituição e exclusão | ✅ |
| Verbas do lançamento expresso; inclusão e remoção | ✅ (remoção 🟡) |
| Bases por verba (histórico), conforme a base que o PJe-Calc define | ✅ |
| Reflexos (ativar/desativar) e incidências por verba | ✅ reflexos · 🟡 incidências |
| FGTS (destino, multa 20/40%, incidência, art. 467, contribuições) | ✅ multa · 🟡 demais |
| Correção, juros e combinações “a partir de” | 🟡 (leitura ✅; gravação testada para índice) |
| Data de liquidação e época própria | ✅ |
| Pendências oficiais, liquidação, relatório HTML/PDF, exportação `.PJC` | ✅ |
| Importação de `.PJC` pela tela oficial e leitura de volta | ✅ |
| Reabertura do `.PJC` exportado no PJe-Calc com 0 divergências | ✅ |
| Painel de resultados (resumo, créditos/descontos, débitos, ocorrências, critérios, memória oficial) | ✅ |
| Rascunho automático, revisões, auditoria, recuperação de sessão, confirmação ao descartar | ✅ |
| Conferência preventiva (datas, CNJ, CPF/CNPJ, lacunas, duplicidades, vazio × zero × desconhecido) | ✅ |
| Quadro de critérios por verba com a fórmula montada pelo PJe-Calc e fundamentos | ✅ |
| Ajuda contextual com fontes e textos oficiais do PJe-Calc | ✅ |
| Modelos iniciais (13) e modelos do escritório com versões (sem dados pessoais) | ✅ |
| Cenários (duplicar, executar, comparar entradas e resultados por verba/competência) | ✅ |
| Tabela editável (teclado, seleção, colar de planilhas, repetir valor, importação CSV/XLSX com prévia) | ✅ |
| Painel do escritório (pesquisa, filtros, favoritos, etiquetas, situação, retomar) | ✅ |
| CSV de conferência e resumo complementar com logotipo (identificados como não oficiais) | ✅ |
| Diagnóstico da instalação, alerta de versão não validada, backups com verificação e restauração | ✅ |
| Temas claro/escuro, fonte ajustável, modo guiado/avançado, pesquisa de funções, atalhos | ✅ |

## Fase 2 — ampliar a cobertura do motor (em andamento)

Ordem sugerida pelo impacto nas liquidações:

1. ✅ **Ocorrências da verba** (quantidades e valores mês a mês) — essencial para horas extras e adicionais.
   Etapa Verbas › “Ocorrências mês a mês” de cada verba (expressa ou manual), na tabela editável (colar de
   planilhas, repetir valor, Ativa/Inativa). Colunas: quantidade, devido, pago e, no modo avançado, divisor e
   multiplicador; célula vazia mantém o valor gerado pelo PJe-Calc. “Carregar do PJe-Calc” lê a grade gerada
   pelo motor e mostra seus valores em colunas de referência. A gravação digita os valores na tela oficial
   *Ocorrências da Verba* (`parametrizar-ocorrencia.xhtml`), disparando os mesmos eventos de saída de campo do
   navegador, e confere a mensagem de sucesso. Reenvio só quando as ocorrências da verba mudam (hash por verba);
   alterar parâmetros da verba força o reenvio. A conferência preventiva aponta competência inválida,
   repetida ou valor em formato inválido.
2. ✅ **Verbas manuais** (lançamento “Manual” da tela Verbas: nome, assunto CNJ, valor calculado ou informado,
   característica, ocorrência de pagamento, incidências, base — histórico salarial, maior remuneração, salário
   mínimo, piso —, divisor, multiplicador e quantidade). O assunto CNJ é escolhido na tabela oficial do modal
   do PJe-Calc (lida do próprio motor; 499 assuntos na 2.16.0). Verba manual alterada depois de gravada é
   excluída e incluída de novo pela tela oficial (hash por verba); uma verba de mesmo nome não lançada pela
   interface nunca é substituída.
   **Verba como base** (“Verba *” + “Adicionar Base”, com integralizar sim/não): uma verba principal pode ter
   outras verbas do cálculo na base (ex.: adicional de 10% sobre as horas extras).
   **Reflexos lançados manualmente** (Tipo = Reflexo): verba principal, comportamento (valor mensal ou médias,
   conforme a característica) e tratamento da fração de mês. O PJe-Calc nomeia o reflexo
   “<nome> SOBRE <principal>” e não oferece exclusão de reflexos: alterações vão pela ação “Parametrizar” e
   retirar o reflexo do rascunho o **desativa** na verba principal.
   **Regeração de ocorrências:** o PJe-Calc mantém as ocorrências calculadas com os parâmetros antigos (“O
   parâmetro … foi alterado após a geração das ocorrências”) até que sejam regeradas. Após alterar parâmetros
   de uma verba (inclusive pela etapa Reflexos/Critérios da Fase 1) ou de um reflexo manual, a gravação aciona
   “Regerar” só daquela verba/reflexo, com **“Manter alterações realizadas nas ocorrências”** (os parâmetros novos
   valem e as edições manuais, inclusive as feitas na tela oficial, são preservadas), e reaplica as ocorrências
   informadas na interface. Até 22/10/2026 a interface usava “Sobrescrever”, que apagava edições feitas na tela
   oficial.
   🟡 Ocorrências mês a mês de reflexos (grade do reflexo dentro da tela de ocorrências) continuam na interface
   original; verbas manuais que usam outra verba manual como base devem vir depois dela na lista.
   *Teste:* `tests/ocorrencias_verbas_manuais.py` (HE 50% com quantidades mensais, verba manual calculada,
   verba manual de valor informado, verba com HE como base e dois reflexos manuais) liquida sem pendências
   de erro e confere no `.PJC` quantidades, devidos, adicional = 10% de HE e reflexo = HE ÷ divisor;
   regravar sem mudanças não reenvia nada; alterar um mês reenvia só aquela verba; alterar o divisor do
   reflexo e o multiplicador de HE regera as ocorrências e mantém as quantidades informadas; retirar um
   reflexo o desativa. `tests/reabertura_pjc.py` sobre o `.PJC` final: 11 verbas, 31 ocorrências,
   0 divergências.
   *Correção associada:* a leitura do `.PJC` passou a incluir verbas principais serializadas dentro do
   primeiro reflexo (antes as ocorrências de verbas com reflexos ficavam fora da comparação).
**Revisão de cobertura (22/10/2026):** nenhuma função do PJe-Calc pode faltar. Os itens 3 a 7 já podem ser
usados em **Funções do PJe-Calc**: a tela oficial é lida pelo servidor e redesenhada pelo Studio (23/10/2026; antes
era a página do PJe-Calc embutida, com o visual antigo), aberta no cálculo e no menu certos;
o inventário completo, função por função, está em `docs/07-cobertura-pjecalc.md`. Formulários próprios do
Studio para esses itens continuam como evolução (marcados abaixo como 🟡).

3. 🟡 **Cartão de ponto** — tela do PJe-Calc redesenhada ✅; formulário próprio (CSV oficial e apuração de jornada) ⬜.
4. 🟡 **Faltas e férias** — telas do PJe-Calc redesenhadas ✅; formulário próprio ⬜.
5. 🟡 **Contribuição social, IRPF, custas, honorários, multas e indenizações** — telas do PJe-Calc redesenhadas ✅; formulários próprios ⬜.
6. 🟡 **Pensão alimentícia, previdência privada, salário-família, seguro-desemprego** — telas do PJe-Calc redesenhadas ✅; formulários próprios ⬜.
7. 🟡 **Atualização de pagamentos** (Dados do Pagamento, Pensão, Multas, Honorários, Custas, Liquidar e Imprimir
   Atualização) — telas do PJe-Calc redesenhadas ✅; formulário próprio ⬜.
8. ✅ **Trazer do PJe-Calc** (sincronização reversa): liga ao Studio um cálculo que já existe no PJe-Calc, sem
   duplicá-lo. Lê pelas telas oficiais os Dados do Cálculo, os históricos salariais mês a mês (“Visualizar”) e a
   lista de verbas; busca por nº do cálculo ou reclamante. Parâmetros, ocorrências e reflexos das verbas existentes
   continuam como estão no PJe-Calc e só mudam se forem alterados no Studio. Históricos com nome repetido: traz o
   primeiro e avisa; os demais não são tocados. *Teste (22/10/2026, cálculo de teste nº 69):* trazer, alterar uma
   competência no Studio e enviar atualizou só aquele histórico (“Alterar” + CSV), manteve o histórico homônimo,
   a verba e os reflexos.

## Fase 3 — produtividade

- ⬜ Prévia de duplicidade de reflexos com base nas fórmulas lidas do motor.
- ⬜ Vinculação de trechos de decisões em PDF (marcação no documento) ao quadro de critérios.
- ⬜ Extração assistida de contracheques, cartões de ponto e documentos digitalizados (OCR), sempre
  com revisão humana antes de qualquer uso.
- ⬜ Empacotamento como executável único com atualização automática.
- ⬜ Verificação automática de novas versões do PJe-Calc (página oficial) e das tabelas auxiliares.
- ⬜ Teste de equivalência automatizado por versão (suíte de casos de referência).
