# Operação e solução de problemas

Os testes unitários verificam funções isoladas, como validação de caminhos, classificação de resultados e tratamento de erros do yt-dlp. Não acessam rede nem serviços.

Os testes de integração combinam a interface, os fluxos simulados de playlist, o lock local e verificações locais de Compose/healthcheck. Usam somente `tmp_path`, mocks e arquivos falsos.

Download real é uma operação separada, iniciada somente pelo botão da Biblioteca do Ariel ou pelo CLI. Ele pode acessar o YouTube e gravar arquivos na biblioteca; por isso não faz parte da suíte de testes.
