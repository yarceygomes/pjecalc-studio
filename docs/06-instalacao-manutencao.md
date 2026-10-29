# 6. Instalação, manutenção e atualização

## 6.1 Instalação

1. Instale o **PJe-Calc Cidadão** pelo instalador oficial do TRT8. Confira o MD5 publicado na página
   “Instalando o PJe-Calc Cidadão” (PowerShell: `Get-FileHash <arquivo> -Algorithm MD5`).
2. Abra o PJe-Calc uma vez e faça a **atualização das Tabelas Auxiliares** (Tabelas › Atualização de
   Tabelas e Índices), como orienta o TRT8.
3. Baixe e execute o **PJeCalcStudio-Instalador.exe** da página de versões do projeto no GitHub (passo a passo
   no README). Ele instala só para o usuário, sem pedir administrador, já com o Python embutido.
   Para rodar pelo código-fonte, veja `docs/DESENVOLVIMENTO.md`.
4. Abra o PJe-Calc pelo atalho oficial e, em seguida, o **PJe-Calc Studio** pelo menu Iniciar.
5. Em **Configurações**: informe seu nome (registro de alterações), confirme o endereço do PJe-Calc
   (`http://127.0.0.1:9257/pjecalc/`) e a **pasta de instalação** (habilita o diagnóstico e os textos
   de ajuda oficiais). Execute o **Diagnóstico**.

Opções de linha de comando (código-fonte): `iniciar.bat --porta 8765 --dados D:\Escritorio\calculos --pjecalc http://127.0.0.1:9257/pjecalc/ --sem-navegador`.

Se o Studio já estiver aberto, abri-lo de novo só abre o navegador nele. Se a porta estiver ocupada por
outro programa, o Studio avisa e encerra (antes, no Windows, uma segunda cópia ocupava a mesma porta em
silêncio e o navegador continuava falando com a primeira).

## 6.2 Onde ficam os dados

- **Nova interface**: `%LOCALAPPDATA%\PJeCalcStudio\dados` na versão instalada (`dados/` no código-fonte, ou a pasta indicada em `--dados`): rascunhos, revisões, auditoria,
  execuções (relatórios e `.PJC` oficiais), modelos e backups. Somente neste computador.
- **PJe-Calc**: banco `.dados/pjecalc.h2.db` da instalação, nunca aberto pela nova interface.

## 6.3 Cópias de segurança

- Nova interface: **Configurações › Criar cópia de segurança** (ZIP com manifesto SHA-256, verificado
  ao criar). A restauração só ocorre se o pacote passar na verificação, e o estado atual é guardado
  antes em outro backup.
- PJe-Calc: ícone da bandeja › **Salvar Tudo** (gera `.dados/backup.sql`) e exportação dos cálculos
  em `.PJC`. Faça os dois **antes de qualquer atualização**.

## 6.4 Atualização do PJe-Calc

1. Backup da nova interface e “Salvar Tudo” + exportação `.PJC` no PJe-Calc atual.
2. Instale a nova versão conforme o manual oficial e atualize as tabelas.
3. Abra o PJe-Calc Studio: o status mostrará “versão não validada” se for uma versão nova.
4. Rode o roteiro de equivalência (`05-plano-de-equivalencia.md`) com os casos de referência e
   `py -I tests/fluxo_completo.py`. Só então inclua a versão em `VERSOES_TESTADAS` (`servidor.py`).
5. Se alguma tela mudou (botão ou campo não encontrado), a ponte informa a ação ausente; ajuste
   `ponte/pjecalc.py` e rode os testes de novo.

## 6.5 Atualização do PJe-Calc Studio

Substitua os arquivos do programa mantendo a pasta `dados/`. Faça um backup antes.

## 6.6 Recuperação e continuidade

- Rascunhos não salvos (janela fechada, servidor indisponível) são oferecidos para recuperação ao
  reabrir o cálculo.
- Exclusões vão para `dados/lixeira/` (recuperáveis); cálculos no PJe-Calc nunca são apagados por
  essa ação.
- Todas as funções do PJe-Calc continuam disponíveis no Studio (“Funções do PJe-Calc” no menu lateral, abertas no
  cálculo certo e com o visual do Studio), e o próprio programa PJe-Calc pode ser usado a qualquer momento; o
  número do cálculo gravado aparece na etapa Documentos.

## 6.7 Desenvolvimento e testes

- `tools/iniciar-instancia-teste.ps1 -Instalador <exe>` sobe uma cópia de teste em portas +10000
  (19257), sem interferir na instalação de trabalho.
- `py -I tests/test_unidades.py [relatorio.html]` — testes sem o PJe-Calc (inclui a API do servidor numa
  porta livre, com um PJe-Calc inexistente).
- Ao testar a interface com o PJe-Calc de trabalho aberto, use outra porta e outra pasta de dados
  (`--porta 8799 --dados <pasta de teste>`) e aponte o Studio de teste para a instância de teste (`--pjecalc
  http://127.0.0.1:19257/pjecalc/`): com a URL padrão, o Studio de teste enviaria dados ao PJe-Calc de trabalho.
- `py -I tests/fluxo_completo.py <URL>` — fluxo completo contra uma instância.
- `py -I tests/reabertura_pjc.py <arquivo.pjc> <URL>` — reabertura e comparação.
- `py -I tests/equivalencia.py ref.pjc nova.pjc [ref.html nova.html]` — prova de equivalência.
