# IPTV dinâmica

Verificador de disponibilidade e failover para uma lista M3U. Usa somente URLs que você tem autorização para utilizar e redistribuir.

## Como funciona
- Lê `input/canais.m3u`.
- Testa a URL atual e alternativas cadastradas em `sources.json`.
- Para HLS, testa também o primeiro recurso filho encontrado.
- Escolhe a fonte válida de menor latência.
- Gera `docs/playlist.m3u` e `docs/status.json`.
- GitHub Actions agenda verificações a cada 30 minutos (minutos 07 e 37 UTC).

**Importante:** este sistema não descobre fontes na internet, não renova tokens privados e não contorna DRM, login ou geobloqueio. O repositório atual é público. Não coloque nele listas privadas, URLs com tokens, credenciais ou fontes sem autorização de redistribuição. O arquivo M3U inicial foi deixado como modelo vazio por segurança.

## Configuração
1. Edite `input/canais.m3u` e adicione sua lista autorizada.
2. Edite `sources.json` para cadastrar alternativas por nome exato do canal.
3. Em Settings → Pages, selecione Deploy from a branch, branch `main`, pasta `/docs`.
4. Em Actions, execute manualmente **Atualizar playlist IPTV** uma vez.

Playlist: `https://SEU-USUARIO.github.io/iptv-dinamica/playlist.m3u`

O GitHub pode atrasar execuções agendadas. HTTP 200 não garante áudio/vídeo perfeito.
