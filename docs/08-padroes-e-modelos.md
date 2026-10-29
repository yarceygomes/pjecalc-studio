# 8. Padrões e modelos do escritório

Objetivo: o que se repete de um cálculo para outro é preenchido **uma vez** e reaproveitado. O motor do
PJe-Calc continua fazendo todas as validações e cálculos: padrões e modelos só preenchem as telas por você.

## 8.1 Padrões (funções do PJe-Calc)

Um padrão guarda o preenchimento de uma função do PJe-Calc — honorários de sucumbência, custas, imposto de
renda, contribuição social, correção e juros, pensão, cartão de ponto, pisos salariais… — como uma sequência de
campos e botões (`ponte/padroes.py`).

| Como | Onde |
|---|---|
| Criar | Abra a função num cálculo (Funções do PJe-Calc › Honorários), preencha como de costume (se quiser que o padrão grave sozinho, use também o botão Salvar da tela) e clique em **Salvar como padrão**. Desmarque o que é só daquele caso; datas já vêm desmarcadas. |
| Aplicar numa tela | **Aplicar padrão ▾** na barra da função. O resultado aparece na hora; dá para ajustar antes de salvar. |
| Aplicar num cálculo | Menu lateral do cálculo › **Aplicar padrões do escritório** (vários de uma vez; cada um na sua função). |
| Automático | Marque “Aplicar automaticamente em todo cálculo novo”: entra logo depois do primeiro envio ao PJe-Calc. |
| Gerenciar | Escritório › **Padrões do escritório**: renomear, ligar/desligar o automático, excluir (vai para `dados/lixeira/padroes`). |

Robustez: cada campo é procurado pelo id do PJe-Calc e, se o id mudou (outra versão), pelo rótulo; cada botão
pelo id e, depois, pelo texto. Se um campo ou botão não existir mais, a aplicação **para antes do botão
seguinte** (nada é salvo pela metade) e a tela mostra o que foi feito e onde parou.

O cálculo registra os padrões aplicados (`pjecalc.padroesAplicados`, com data e resultado). Aplicar de novo um
padrão que cria registros (ex.: honorários) cria um registro repetido; o Studio avisa isso antes.

## 8.2 Modelos (ponto de partida de um tipo de trabalho)

Tipos: Liquidação de sentença, Execução, Atualização de cálculo, Petição inicial, Acordo, Rescisórias, Outros.

- **Novo modelo** (Modelos de cálculo): em branco, a partir de um cálculo do escritório ou de outro modelo.
  O modelo abre **nas mesmas etapas de um cálculo** (faixa “Editando o modelo…” no alto); preencha verbas,
  critérios, FGTS, liquidação e use **Salvar modelo**. Cada gravação vira uma nova versão.
- O modelo pode incluir **padrões**: um cálculo criado a partir dele aplica esses padrões no primeiro envio.
- Partes, processo, documentos, observações e trechos de decisões **nunca** entram no modelo
  (`armazenamento.sem_dados_pessoais`).
- **Usar como padrão em “Novo cálculo”**: o modelo já vem marcado; criar um cálculo vira dar um título e Enter.
  O diálogo mostra as premissas do modelo e todos os padrões que serão aplicados.
- Modelos iniciais podem ser **personalizados** (vira um modelo do escritório; o original fica intacto).

## 8.3 Retrabalho evitado

- Cenário duplicado: no PJe-Calc ele é um cálculo novo, então recebe de novo os padrões do original e os automáticos.
- “Trazer do PJe-Calc”: só as verbas do lançamento expresso entram na lista do Studio; as lançadas
  manualmente no PJe-Calc continuam lá e nunca são excluídas (antes, uma cópia do cálculo falhava ao enviar).
- Conferência antes do envio: verba fora do lançamento expresso é apontada antes de ir ao PJe-Calc.

## 8.4 Ajuda nas funções do PJe-Calc

Todo campo das funções tem o mesmo “?” das etapas (painel lateral, F1) e cada função tem um “?” no título.
Ordem de preferência do texto: ajuda própria (`web/ajuda-pjecalc.js`), a ajuda do mesmo campo nas etapas do
Studio, o texto de ajuda oficial que o PJe-Calc mostra na tela e, por fim, o que a própria tela informa
(formato, opções, obrigatoriedade). Referências legais são listadas para conferência; a interface não decide teses.

## 8.5 Verificação (23/10/2026, instância de teste, dados fictícios)

- Padrão “Honorários de sucumbência 15% — reclamado” gravado na tela Honorários e aplicado com ids
  propositalmente desatualizados (achou campos pelo rótulo e botões pelo texto): o PJe-Calc gravou.
- Cenário duplicado do cálculo nº 41, enviado: criou o cálculo nº 77 e aplicou o padrão automático sozinho; o
  honorário aparece na lista oficial do cálculo 77.
- Modelo “Liquidação de sentença — escritório” criado a partir de um cálculo (sem o nome do reclamante), salvo em
  duas versões, marcado como padrão; “Novo cálculo” já o traz marcado e lista o padrão que será aplicado.
- Testes automáticos: `tests/test_unidades.py` (classes `Padroes`, `Armazenamento`, `Servidor`).
