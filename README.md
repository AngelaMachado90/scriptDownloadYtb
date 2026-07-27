# Biblioteca do Ariel — scriptDownloadYtb

Biblioteca pessoal de músicas para o Ariel, criada como presente de aniversário e pensada para uso em pendrive e som automotivo — inclusive quando a internet não estiver disponível.

O projeto combina:

* `youtubeVideos.py`: downloader com `yt-dlp`;
* Streamlit: interface local para organizar artista, álbum e download;
* Docker Compose: execução isolada, sem interferir nos demais serviços do server;
* testes automatizados: validação de regras, arquivos e interface sem baixar músicas reais.

> **Regra principal:** a biblioteca é organizada por artista e álbum. As músicas recebem prefixo numérico (`01 -`, `02 -`...) para o som do carro respeitar a ordem correta.

---

## Índice

* [Estrutura do projeto](#estrutura-do-projeto)
* [Início rápido](#início-rápido)
* [Acesso remoto pelo VS Code](#acesso-remoto-pelo-vs-code)
* [Como usar a interface](#como-usar-a-interface)
* [Uso pelo terminal](#uso-pelo-terminal)
* [Autenticação do YouTube](#autenticação-do-youtube)
* [Status dos downloads](#status-dos-downloads)
* [Testes automatizados](#testes-automatizados)
* [Solução de problemas](#solução-de-problemas)
* [Operação do container](#operação-do-container)
* [Segurança](#segurança)
* [Estado inicial da biblioteca](#estado-inicial-da-biblioteca)
* [Versionamento](#versionamento)

---

## Estrutura do projeto

```text
scriptDownloadYtb/
├── app.py                         # Interface Streamlit
├── youtubeVideos.py               # Downloader e regras de resultado
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── Makefile
├── README.md
├── downloads/                     # Biblioteca de músicas — não versionada
│   └── Disturbed/
│       └── 2000 - The Sickness/
├── logs/                          # Logs de execução — não versionados
├── tests/
│   ├── unit/
│   └── integration/
└── docs/
    └── operacao-e-solucao-de-problemas.md
```

A biblioteca deve seguir este padrão:

```text
downloads/
└── Artista/
    └── Ano - Álbum/
        ├── 01 - Nome da Faixa.mp3
        ├── 02 - Nome da Faixa.mp3
        └── ...
```

---

## Início rápido

Entre no projeto:

```bash
cd /home/server/projects/projeto-musicas/scriptDownloadYtb
```

Suba somente a aplicação de músicas:

```bash
docker compose up -d --build
```

Confirme o estado:

```bash
docker compose ps
```

Acompanhe os logs:

```bash
docker compose logs -f musica-library
```

Para parar apenas este serviço:

```bash
docker compose stop musica-library
```

> Não use `docker compose down` sem necessidade: o projeto deve operar sem afetar os demais containers do server.

---

## Acesso remoto pelo VS Code

A aplicação fica limitada ao servidor em:

```text
127.0.0.1:8507
```

Como o VS Code está conectado remotamente ao Pop!_OS, abra a aba **Ports** no VS Code e encaminhe a porta `8507`.

Depois, acesse no navegador local:

```text
http://127.0.0.1:8507
```

A aplicação não deve ser exposta publicamente sem uma decisão explícita de segurança.

---

## Como usar a interface

Na tela **Biblioteca do Ariel**:

1. Selecione ou crie o artista.
2. Selecione ou informe o álbum.
3. Informe o ano do álbum.
4. Cole a URL de um vídeo ou playlist do YouTube.
5. Mantenha habilitadas:

   * **Somente áudio**
   * **Numerar faixas para o carro**
6. Clique em **Iniciar download**.
7. Aguarde o resumo final.

A interface só pode criar arquivos dentro de:

```text
./downloads/Artista/Ano - Álbum/
```

Ela não aceita caminhos livres do sistema, evitando que arquivos sejam salvos fora da biblioteca.

---

## Uso pelo terminal

O downloader também funciona sem a interface:

```bash
python3 youtubeVideos.py
```

Informe:

1. Diretório de destino;
2. URL do vídeo ou playlist;
3. Se deseja apenas áudio;
4. Limite de itens, caso queira baixar somente parte de uma playlist;
5. Se deseja numerar as faixas.

Para um álbum do Disturbed:

```text
./downloads/Disturbed/2000 - The Sickness
```

Em playlists, as faixas são gravadas diretamente no diretório informado e recebem, por padrão:

```text
01 - Título.mp3
02 - Título.mp3
03 - Título.mp3
```

Os logs ficam em:

```text
./logs/
```

Nunca dentro da pasta do álbum.

---

## Autenticação do YouTube

O YouTube pode bloquear downloads não autenticados com mensagens como `HTTP 429` ou `Sign in to confirm you’re not a bot`.

O projeto usa um arquivo de cookies exportado da conta da própria Angela.

### Local seguro do arquivo

```text
/home/server/.config/scriptDownloadYtb/youtube-cookies.txt
```

Permissões obrigatórias:

```bash
chmod 700 /home/server/.config/scriptDownloadYtb
chmod 600 /home/server/.config/scriptDownloadYtb/youtube-cookies.txt
```

No container, ele é montado somente para leitura em:

```text
/run/secrets/youtube-cookies.txt
```

A variável utilizada é:

```text
YTDLP_COOKIES_FILE=/run/secrets/youtube-cookies.txt
```

### Regras de segurança

* Nunca enviar o arquivo de cookies pelo chat.
* Nunca salvar cookies em `downloads/`.
* Nunca versionar o arquivo no Git.
* Nunca colocar seu conteúdo em logs, prints ou documentação.
* Quando os cookies expirarem, exportar um novo arquivo e substituir o antigo.

---

## Status dos downloads

Ao final de cada execução, o downloader mostra um resumo.

| Status           | Significado                                                       | Próxima ação                                              |
| ---------------- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| `FINAL: SUCESSO` | Todos os itens foram baixados e os arquivos finais foram criados. | Conferir a ordem e seguir para o próximo álbum.           |
| `FINAL: PARCIAL` | Parte das faixas foi criada, mas uma ou mais falharam.            | Conferir as faixas faltantes antes de copiar ao pendrive. |
| `FINAL: FALHA`   | Nenhum arquivo foi criado ou a URL não pôde ser processada.       | Consultar logs e corrigir a causa antes de repetir.       |

`PARCIAL` e `FALHA` retornam código de saída `1`.

---

## Testes automatizados

Os testes não baixam músicas, não acessam o YouTube e não usam cookies reais.

Executar todos os testes e verificações:

```bash
make check
```

Executar somente testes unitários:

```bash
make test-unit
```

Executar somente testes de integração:

```bash
make test-integration
```

A suíte valida, entre outros pontos:

* criação segura de caminhos;
* bloqueio de path traversal;
* numeração correta de faixas;
* classificação `SUCESSO`, `PARCIAL` e `FALHA`;
* proteção dos logs e cookies;
* bloqueio de downloads concorrentes;
* importação da interface Streamlit;
* healthcheck do container;
* biblioteca simulada em diretórios temporários.

Antes de publicar alterações, execute:

```bash
make check
git diff --check
```

---

## Solução de problemas

| Mensagem ou sintoma                   | Causa provável                             | Ação                                                                 |
| ------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------- |
| `HTTP Error 429`                      | Bloqueio temporário do YouTube.            | Não repetir várias vezes; conferir cookies e aguardar.               |
| `Sign in to confirm you’re not a bot` | Cookies ausentes, inválidos ou expirados.  | Exportar um novo `youtube-cookies.txt`.                              |
| `Signature solving failed`            | Deno ou `yt-dlp-ejs` não está disponível.  | Reconstruir a imagem do container.                                   |
| `Only images are available`           | O desafio JavaScript não foi resolvido.    | Verificar Deno, `yt-dlp-ejs` e cookies.                              |
| `Private video`                       | Vídeo privado ou removido.                 | Usar outra fonte oficial da faixa.                                   |
| `FINAL: PARCIAL`                      | Uma ou mais músicas falharam.              | Comparar a lista do álbum e baixar apenas as faixas faltantes.       |
| Interface não abre                    | Container parado ou porta não encaminhada. | Executar `docker compose ps` e encaminhar a porta `8507` no VS Code. |
| Arquivos fora de ordem no carro       | Faixas sem prefixo numérico.               | Usar a opção de numeração automática.                                |

---

## Operação do container

Reconstruir após alteração de dependências ou Dockerfile:

```bash
docker compose up -d --build
```

Reiniciar somente a aplicação:

```bash
docker compose restart musica-library
```

Verificar healthcheck e estado:

```bash
docker compose ps
```

Ver logs recentes:

```bash
docker compose logs --tail=100 musica-library
```

---

## Segurança

Os itens abaixo não devem entrar no Git:

```text
downloads/
logs/
cookies.txt
youtube-cookies.txt
.env
secrets/
```

Antes de qualquer commit:

```bash
git status
git diff --check
```

Nunca use comandos destrutivos sobre `downloads/` sem confirmar o caminho e o conteúdo.

---

## Estado inicial da biblioteca

> Atualizado em 27/07/2026. Atualize esta seção quando a biblioteca crescer.

### Disturbed

Álbuns já existentes:

* `2005 - Ten Thousand Fists`
* `2008 - Indestructible`
* `2018 - Evolution`

Em preparação:

* `2000 - The Sickness`

O álbum *The Sickness* possui 12 faixas na edição original. Até este registro, faltam:

```text
01 - Voices.mp3
08 - Want.mp3
```

Antes de copiar o álbum ao pendrive, conferir se todas as 12 faixas estão presentes e na ordem correta.

---

## Versionamento

Após revisar este README, registre a documentação sem incluir arquivos de música, logs ou cookies:

```bash
git add README.md
git commit -m "docs: document Ariel music library operation"
```

Para consultar o histórico:

```bash
git log --oneline -- README.md
```

---

## Regra para a Angela do futuro

Se algo falhar:

1. Não repita várias tentativas seguidas.
2. Leia o `FINAL:` e o log correspondente.
3. Verifique cookies, Deno e `yt-dlp-ejs`.
4. Confirme se a faixa foi criada antes de tentar novamente.
5. Só copie ao pendrive quando o álbum estiver completo e numerado.

A organização correta agora evita dor de cabeça na estrada depois. 🎵
