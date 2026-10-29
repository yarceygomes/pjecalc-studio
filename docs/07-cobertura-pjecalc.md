# 7. Cobertura das funções do PJe-Calc Cidadão 2.16.0

Princípio: **nenhuma função do PJe-Calc deixa de existir, e nenhuma aparece com o visual antigo**. Cada função
ou é feita pelos formulários do Studio (que preenchem as telas oficiais), ou é exibida pelo Studio a partir da
própria tela do PJe-Calc (“Funções do PJe-Calc”): o servidor abre a tela oficial numa sessão própria, lê os
grupos, abas, campos, tabelas e botões (`ponte/tela.py`) e o Studio os desenha com o seu visual. Cada valor
digitado e cada botão voltam para a mesma tela oficial, que valida e grava. O Studio nunca grava no banco H2
nem reimplementa regras de cálculo.

Legenda: **Studio** = formulário próprio do Studio · **Parcial** = os campos mais usados nas etapas do Studio,
todos os campos na função do PJe-Calc redesenhada · **Redesenhada** = a tela do PJe-Calc exibida pelo Studio.

Inventário levantado do menu da instalação de teste (identificadores `li_*` do menu oficial), 22/10/2026.

## 7.1 Cálculo

| Função do PJe-Calc | Onde fazer | Observação |
|---|---|---|
| Novo | Studio | “Novo cálculo” (em branco ou modelo) |
| Buscar | Studio + Redesenhada | Lista do Studio; “Trazer do PJe-Calc” (busca por nº ou reclamante) liga ao Studio um cálculo existente sem duplicá-lo; busca do PJe-Calc em “Buscar cálculos no PJe-Calc” |
| Importar | Studio | Pela tela oficial “Importar” |
| Novo Cálculo Externo | Redesenhada | |
| Relatório Consolidado | Redesenhada | |
| Dados do Cálculo | Parcial | Advogados, exceções de carga horária e de sábado, pontos facultativos: função do PJe-Calc |
| Faltas | Redesenhada | |
| Férias | Redesenhada | |
| Histórico Salarial | Studio (Parcial) | Valores mês a mês, CSV oficial; proporcionalização e grade completa: função do PJe-Calc |
| Verbas — Expresso | Studio | |
| Verbas — Manual (principal e reflexo, verba como base) | Studio | |
| Verbas — Parâmetros | Parcial | Base, incidências, divisor, multiplicador; os demais: função do PJe-Calc |
| Verbas — Ocorrências | Studio (Parcial) | Grade da verba principal; ocorrências de reflexos: função do PJe-Calc |
| Verbas — Regerar | Studio (automático) | Após alterar parâmetros, com “Manter alterações realizadas nas ocorrências” |
| Cartão de Ponto | Redesenhada | |
| Salário-família | Redesenhada | |
| Seguro-desemprego | Redesenhada | |
| FGTS | Parcial | Destino, multa, incidência, contribuições; ocorrências do FGTS: função do PJe-Calc |
| Contribuição Social | Redesenhada | |
| Previdência Privada | Redesenhada | |
| Pensão Alimentícia | Redesenhada | |
| Imposto de Renda | Redesenhada | |
| Multas e Indenizações | Redesenhada | |
| Honorários | Redesenhada | |
| Custas Judiciais | Redesenhada | |
| Correção, Juros e Multa | Parcial | Índice, juros, combinações, base de juros, FGTS; demais abas: função do PJe-Calc |

## 7.2 Operações

| Função | Onde fazer | Observação |
|---|---|---|
| Liquidar | Studio + Redesenhada | “Calcular” no Studio; a tela Liquidar também está disponível |
| Imprimir | Studio (Parcial) | Relatório consolidado HTML/PDF no Studio; demais relatórios e opções: função do PJe-Calc |
| Exportar | Studio + Redesenhada | |
| Fechar | Não se aplica | O Studio abre e fecha o cálculo em cada operação |
| Excluir | Redesenhada | A “lixeira” do Studio não exclui o cálculo do PJe-Calc |

## 7.3 Atualização de pagamentos

Dados do Pagamento, Pensão Alimentícia, Multas e Indenizações, Honorários, Custas Judiciais, Liquidar
Atualização e Imprimir Atualização: **Redesenhada** (todas).

## 7.4 Tabelas

Salário Mínimo, Pisos Salariais, Salário-família, Seguro-desemprego, Vale-transporte, Feriados e Pontos
Facultativos, Verbas, Contribuição Social, Imposto de Renda, Custas Judiciais, Correção Monetária, Juros de
Mora e Atualização de Tabelas e Índices: **Redesenhada** (todas), no menu lateral “Tabelas do PJe-Calc”.

## 7.5 Convivência entre o Studio e as telas oficiais

O Studio só reenvia o que foi alterado nele (hash por item) e nunca apaga o que não criou:

- **Dados do Cálculo**: reenvia apenas os campos preenchidos no Studio; os demais ficam como estão no PJe-Calc.
  Um campo preenchido nos dois lugares assume o valor do Studio no próximo envio.
- **Históricos**: um histórico já existente é atualizado no lugar (“Alterar” + CSV oficial), mantendo o vínculo
  com as verbas que o usam como base. O PJe-Calc recusa excluir um histórico vinculado (“Registro possui vínculo”);
  antes desta revisão o Studio tentava excluir e recriar, e a gravação parava.
- **Verbas**: só exclui as que ele mesmo incluiu; verbas criadas na tela oficial ficam intactas.
- **Ocorrências**: só digita as células informadas no Studio. Depois de alterar parâmetros, regera com “Manter
  alterações realizadas nas ocorrências”: os parâmetros novos valem e as edições manuais (inclusive as feitas na
  tela oficial) são preservadas. Antes desta revisão o Studio usava “Sobrescrever”, que as apagava.
- **Reflexos**: só altera os reflexos marcados ou desmarcados no Studio.
- **FGTS e Correção/Juros**: só grava os campos definidos no Studio; as combinações de índices e juros só são
  substituídas quando a opção “Definir os critérios por esta interface” está marcada.
- **Telas sem formulário no Studio** (faltas, férias, cartão de ponto, contribuição social, IR, honorários,
  custas, multas, pensão, previdência, salário-família, seguro-desemprego, atualização de pagamentos): o Studio
  nunca as altera.
- **Resultado**: quando o cálculo é aberto numa tela oficial depois do último cálculo, o Studio passa a mostrar
  “Resultado: pode estar desatualizado” até que se calcule de novo.

- **Trazer do PJe-Calc**: o Studio identifica históricos pelo nome; se o PJe-Calc tiver dois com o mesmo nome,
  traz o primeiro, avisa, e nunca toca nos demais.

## 7.6 Verificação (22/10/2026, instância de teste, dados fictícios)

- **44 telas oficiais abertas pelo Studio**, uma a uma, conferindo a migalha do próprio PJe-Calc (“Cálculo >
  Faltas”, “Atualização > Custas Judiciais”, “Tabelas > Juros de Mora”…) e o nº do cálculo: as 27 do cálculo
  nº 41 e as 17 gerais. Todas abriram no lugar certo, sem “Erro Interno no Servidor”.
- “Imprimir Atualização” no cálculo de teste nº 41 (nenhuma atualização liquidada): o PJe-Calc responde “Erro inesperado… Erro: 33”
  (o log dele mostra `NullPointerException` em `RelatorioPagamentoEnum.isRendered`). É a resposta do próprio
  PJe-Calc; o Studio mostra a mensagem em vez de ficar esperando.
- “Trazer do PJe-Calc” com o cálculo de teste nº 69 (dois históricos “SALARIO BASE”, uma verba com cinco reflexos):
  trazer → alterar uma competência no Studio → enviar. Só o primeiro histórico mudou; o homônimo, a verba e os
  reflexos ficaram iguais (comparação antes/depois lendo cada histórico pela posição na lista).
- Correções feitas na verificação: (1) a tela de busca do PJe-Calc guarda o resultado anterior; clicar em
  “Abrir” na lista antiga com a busca nova em andamento fazia o PJe-Calc responder “Erro Interno no Servidor”
  (`ArrayIndexOutOfBoundsException` em `emModoListagem`). Agora o Studio abre direto se o cálculo já está na
  lista, senão espera a lista ser refeita; se ainda assim vier a página de erro, tenta de novo uma vez.
  (2) Quando o PJe-Calc recusa abrir uma tela, a mensagem dele aparece no status em segundos.

## 7.7 Como as telas são redesenhadas (23/10/2026)

- **Leitura** (`ponte/tela.py`): a área de conteúdo da página oficial vira grupos (`fieldset`, painéis), abas
  (as trocadas no navegador vêm todas; as trocadas no servidor viram uma barra de abas que aciona o PJe-Calc),
  campos (texto, data, lista, rádio, marcação, área de texto, arquivo) com rótulo, obrigatoriedade, texto de ajuda
  oficial e erro de validação, tabelas com as ações de cada linha, paginação e botões.
- **Atualização parcial**: cada resposta AJAX do PJe-Calc lista as regiões refeitas (`Ajax-Update-Ids`); a ponte
  substitui só essas regiões na sua cópia da página, como o navegador faria (`Page.dom`).
- **Arquivos**: relatórios e `.PJC` que a tela oficial baixaria sozinha (script de envio automático) são baixados
  pela sessão e entregues ao navegador com o nome dado pelo PJe-Calc.
- **Verificação** (instância de teste, cálculo fictício nº 41): as 43 funções abriram pelo Studio; incluir e
  excluir falta, incluir honorário, liquidar, imprimir o relatório (PDF), exportar o `.PJC`, trocar de aba no
  servidor (Juros de Mora) e de página (Salário Mínimo) funcionaram, com as mensagens de sucesso e de validação do
  próprio PJe-Calc.

## 7.8 Limitações conhecidas

- Janelas modais do PJe-Calc que usam outro formulário (ex.: árvore de assuntos CNJ da tela Verbas) não são
  desenhadas; nas verbas manuais, o Studio escolhe o assunto CNJ pela etapa Verbas.
- Comportamentos só de navegador (ex.: sugerir a data final ao sair da data inicial) não acontecem; o PJe-Calc
  continua validando ao salvar.
- Cada tela aberta usa uma sessão própria do PJe-Calc; se o Studio enviar dados enquanto uma tela estiver aberta,
  use “Recarregar” antes de salvar nela, para não gravar por cima com valores antigos.
- A abertura depende dos identificadores do menu oficial (`li_*`) da versão 2.16.0; em outra versão, se um item
  mudar, o Studio informa que a função não está no menu do PJe-Calc instalado.
