# Operação da Biblioteca do Ariel

## Iniciar

No diretório do projeto, execute `docker compose up -d --build`. A aplicação
fica no servidor em `127.0.0.1:8507`; pelo Windows, encaminhe essa porta na aba
**PORTS** do VS Code e abra a URL fornecida por ele.

## Cadastrar artista, CD e playlist

Cadastre as faixas esperadas em `music_library/catalog.py`, com artista, ano,
nome do CD e lista ordenada de faixas. Cadastre a URL de uma playlist de álbum
em `data/album_sources.json`. A URL apenas preenche o formulário: nenhum
download começa sem clique explícito em **Iniciar download**.

## Baixar músicas faltantes

Um CD **Incompleto** exibe **Baixar músicas faltantes (N)**. Um clique inicia a
ação: só as faixas sem MP3 correspondente são processadas, uma por vez e na
ordem do álbum. CDs **Sem catálogo** ou **Sem faixas** precisam de playlist e
catálogo antes de poderem ser completados.

## Resultado e locais

- **SUCESSO**: todos os itens solicitados foram criados.
- **PARCIAL**: parte foi criada e ao menos uma faixa falhou.
- **FALHA**: nenhum arquivo foi criado.

Os MP3s ficam em `downloads/`, os diagnósticos técnicos em `logs/` e o histórico
de tentativas em `data/library_history.sqlite`. Depois de uma falha, a mesma URL
só pode ser tentada novamente após 30 dias; uma fonte diferente pode ser usada
antes disso.
