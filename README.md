# IPTV dinâmica

Verificador de disponibilidade e failover para uma lista M3U com fontes cadastradas pelo usuário.

## Como funciona
- Lê os canais de `input/canais.m3u`.
- Testa o endereço informado em cada entrada e alternativas cadastradas em `sources.json`.
- Para HLS, testa também o primeiro recurso filho encontrado.
- Escolhe a fonte válida de menor latência.
- Gera `docs/playlist.m3u` e `docs/status.json`.
- GitHub Actions agenda verificações a cada 30 minutos (minutos 07 e 37 UTC).

**Segurança:** o sistema não busca retransmissões aleatórias na internet, não renova tokens privados e não contorna DRM, login ou geobloqueio. Cadastre apenas fontes que você tem autorização para usar e redistribuir. Não coloque URLs privadas, tokens ou credenciais em um repositório público.

## Configuração
1. Edite `input/canais.m3u` e adicione seus canais autorizados.
2. Edite `sources.json` para cadastrar alternativas autorizadas por nome exato do canal.
3. Em Settings → Pages, selecione Deploy from a branch, branch `main`, pasta `/docs`.
4. Em Actions, execute manualmente **Atualizar playlist IPTV**.

Playlist: `https://talleslim4.github.io/iptv-dinamica/playlist.m3u`

O GitHub pode atrasar execuções agendadas. HTTP 200 não garante áudio/vídeo perfeito.
