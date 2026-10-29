# 1. Diagnóstico técnico

Investigação feita em 14–15/10/2026 sobre o instalador oficial e uma cópia de teste executada em
portas alternativas. A instalação de trabalho do usuário (em `Downloads\pjecalc-windows64-2.16.0`)
**não foi aberta nem alterada**.

## 1.1 Distribuição oficial

| Item | Evidência |
|---|---|
| Origem | `https://www.trt8.jus.br/sites/portal/files/roles/pje-calc/pjecalc-2.16.0-instalador-x64.exe` (metadado *Zone.Identifier* do download) |
| Integridade | MD5 `A3795D4074563CE36B39B209C2C6F207` — **idêntico** ao publicado pelo TRT8 na página “Instalando o PJe-Calc Cidadão” |
| Assinatura digital | O executável **não é assinado** (Authenticode: *NotSigned*). A conferência por MD5 é a única verificação oficial disponível |
| Versão / data | 2.16.0, publicada em 25/06/2026 (página oficial e `versao.html`: “Build 25/06/2026 - 09:05”) |
| Plataformas | Windows 7/8/8.1/10/11, 32 e 64 bits (página oficial) |
| Manuais | Página “Manuais”: Manual de Instalação, Manual do Usuário, Tutorial de Uso |
| Orientação oficial relevante | “Após a primeira instalação do sistema, é imprescindível que o usuário atualize as Tabelas Auxiliares” |
| Condições de uso | O sistema é desenvolvido pela SETIN/TRT8 a pedido do CSJT e distribuído gratuitamente (Recomendação CGJT nº 4/2018). **Não foi localizado termo de licença** nas páginas consultadas nem na distribuição (só há licenças do JRE e do Tomcat). Recomenda-se consultar o TRT8/CSJT antes de redistribuir qualquer pacote que inclua o PJe-Calc. A solução proposta **não modifica nem redistribui** arquivos do PJe-Calc |

## 1.2 Estrutura da instalação

O “instalador” é um executável autoextraível com um ZIP anexado (`pjecalc-windows64-2.16.0/`):

- `bin/pjecalc.jar` — lançador (`br.jus.trt8.pjecalcsa.container.Lancador`): sobe um **Tomcat 7.0.67
  embutido**, ícone na bandeja (Salvar Tudo / Restaurar Tudo / Sair) e abre um **Firefox Portable**;
- `bin/jre` — Java 8 próprio; `iniciarPjeCalc.bat` usa `-Duser.timezone=GMT-3 -Dfile.encoding=ISO-8859-1`;
- `tomcat/webapps/pjecalc` — aplicação web **JSF 1.2 + Facelets + JBoss Seam 2.2 + RichFaces 3.3 +
  Hibernate 3.3 + Drools 5.5 + JasperReports 3.7** (`pjecalc-negocio-2.16.0.jar` contém o motor);
- `.dados/pjecalc.h2.db` — banco **H2 1.3.154** embarcado (acesso exclusivo do processo);
- Conectores somente em `127.0.0.1`: HTTP **9257**, *shutdown* 9256, AJP 9258;
- Acesso local sem senha: identidade automática “offline” com perfis `CALCULISTA` e `OFFLINE`.

## 1.3 O que existe — e o que não existe — para integração

| Caminho | Situação verificada |
|---|---|
| API pública para cálculos | **Não existe.** Os únicos serviços REST (`/servico/...`) são `atualizacao/selic`, `atualizacao/precatorios`, `sip/...` e `sincronizacao/...` (tabelas), protegidos por token. Nenhum cria, preenche ou liquida cálculos |
| Código-fonte | Não distribuído. Apenas classes compiladas (inspecionadas somente para identificar nomes de serviços e formatos) |
| Interface web local (JSF) | **Existe e é estável por versão**: formulários com ids legíveis (`formulario:dataAdmissaoInputDate`, `formulario:salvar`…), eventos AJAX declarados nos atributos (`A4J.AJAX.Submit`), mensagens com marcador “Erro./Alerta./Sucesso.” |
| Arquivo `.PJC` | ZIP com **um XML ISO-8859-1** (`CALCULO_<id>_DATA_<data>.PJC`) contendo todo o grafo do cálculo: entradas, `versaoDoSistema`, `hashCodeLiquidacao` e as **ocorrências calculadas por verba/competência** (base, divisor, multiplicador, quantidade, devido, pago, índice acumulado) |
| Importação oficial de `.PJC` | Tela “Importar” (upload RichFaces + “Confirmar”), com as validações do programa |
| Importação de histórico salarial | CSV oficial (`templateHistoricoSalarial/ExemploHistoricoSalarial.csv`): `MES_ANO;VALOR;FGTS;FGTS_REC.;CONTRIBUICAO_SOCIAL;CONTRIBUICAO_SOCIAL_REC.` — também há modelos para cartão de ponto, faltas e férias |
| Relatório oficial | Tela “Imprimir”: **HTML** (Jasper; corpo em UTF-8 apesar do cabeçalho ISO-8859-1) ou **PDF**, com rodapé “Cálculo liquidado por … na versão … em … às …” |
| Ajuda oficial dos campos | 44 textos de *tooltip* nas telas da 2.16.0 (extraídos dos `.xhtml`, sem alteração) |
| Banco H2 | Gravação direta **descartada**: contornaria as validações e regras do motor. O banco nunca é aberto pela nova interface |

## 1.4 Fluxo funcional demonstrado (instância de teste, 15/10/2026)

Pela nova interface, sem tocar o banco:

1. **Criar** cálculo (dados do processo, partes com CPF/CNPJ, local, contrato) → “Operação realizada com sucesso”;
2. **Histórico salarial** de 36 competências com duas faixas de valor e FGTS recolhido em 2022 → importado pelo CSV oficial;
3. **Verbas** (lançamento expresso) e **bases** por verba; **multa de 40%** do FGTS;
4. **Pendências** oficiais (“Não foram encontradas pendências para liquidação”) → **Liquidar**;
5. Relatório oficial **HTML e PDF**, **exportação do `.PJC`** e painel com o resumo transcrito;
6. **Reabertura**: o `.PJC` foi importado pela tela oficial, reliquidado e reexportado — **0 divergências**
   em verbas, ocorrências e históricos; mesmos totais (bruto R$ 38.175,63; líquido R$ 27.503,58);
7. **Cenário**: cópia com maior remuneração alterada, processada pelo motor; a comparação mostrou
   diferenças somente nas verbas cuja fórmula oficial usa “MAIOR REMUNERAÇÃO”.

Validações do próprio PJe-Calc observadas e exibidas fielmente: prescrição quinquenal recusada para
contrato < 5 anos; dígito verificador CNJ; exigência de histórico como base quando há mais de um;
recusa de base de histórico em verba cuja base é “Maior Remuneração”; alerta de exportação sem dados
para o PJe.

## 1.5 Limitações e riscos

- **Dependência das telas por versão.** Ids `j_idNN` mudam entre versões; a ponte localiza menus e
  botões pelo texto visível e por ids nomeados. Cada nova versão do PJe-Calc exige rodar o roteiro
  de equivalência antes do uso (a interface alerta quando a versão não foi validada).
- **Uso simultâneo.** O PJe-Calc Cidadão é monousuário. A ponte serializa suas operações, mas editar
  o mesmo cálculo ao mesmo tempo na interface original pode gerar conflito de versão.
- **Cobertura atual.** Mapeadas: dados do cálculo, histórico salarial, verbas expressas, bases,
  reflexos, incidências, FGTS, correção/juros, liquidação, relatório, exportação e importação.
  Ainda na interface original: verbas manuais, ocorrências mês a mês das verbas, cartão de ponto,
  faltas/férias, contribuição social, IRPF, honorários, custas, multas, pensão, previdência privada,
  atualização de pagamentos. (Ver `04-funcionalidades-priorizadas.md`.)
- **Tabelas auxiliares.** Valores dependem da atualização das tabelas na instalação. A instância de
  teste, recém-extraída, usava tabelas antigas (o relatório informava “última taxa IPCA-E relativa a
  07/2016”); os números dos testes servem para validar a integração, não como cálculo real.
- **Ambiente de desenvolvimento.** Este computador virtualiza pastas para aplicativos empacotados;
  por isso os testes usaram espelhos em `%TEMP%` e `%USERPROFILE%\PJeCalcStudio-teste`. Em uso normal
  basta descompactar o projeto numa pasta comum.
