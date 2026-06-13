# Stitch Design Source

- Project: `AGentVPN: Telegram Mini App Design`
- Project ID: `6308198388609058396`
- Design system: `Kinetic Shield`
- Design system asset: `assets/cac6a5207113449aa1deea24335419a6`
- Primary viewport: 390 px mobile

## Available Screens

| Screen | Stitch screen ID |
|---|---|
| Главная (Нет подписки) | `d64a90ac804c4e6a8ef382290886e730` |
| Подключение (Активно) | `7d0e76d70af04aafb1b8b41bf671ef02` |
| Тарифы | `945f6596410946a29e3ca0e59ad9197b` |
| Оформление заказа | `33b9c40180ff453fbd0051cb20cbd8d3` |
| Ожидание оплаты | `4089e57497f64b9597c49c0489ef6a94` |
| Профиль | `b9e71374de8046c8ba81dced3cd5d349` |
| Инструкция по подключению | `c05e448a45154bdbb0a6fedaed76d8df` |
| Admin Dashboard (Desktop) | `9a62f28031e04ade90c9fcca9ebe6824` |

## Implementation Notes

- Reuse the Stitch layouts and Kinetic Shield tokens for frontend implementation.
- Map colors to Telegram theme variables with documented fallbacks.
- Preserve 48 px minimum touch targets and 16 px mobile safe margins.
- The product protocols are Hysteria2/TLS and VLESS/TCP/REALITY. Generic design-system
  references to WireGuard or OpenVPN are not product requirements.

