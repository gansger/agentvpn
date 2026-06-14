# Reverse proxy

Caddy принимает внешний HTTP/HTTPS-трафик, автоматически получает TLS-сертификат и
проксирует запросы в API.

Проверка конфигурации использует одноразовый контейнер без production volumes:

```bash
PUBLIC_DOMAIN=example.com sh infrastructure/scripts/validate_caddy.sh
```

`PUBLIC_DOMAIN` должен содержать только домен без протокола и пути. Постоянный volume
`caddy_data` хранит сертификаты и не должен удаляться при обычном обновлении.
