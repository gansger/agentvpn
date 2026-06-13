# Stage 1 Owner Actions

## Required Before 3x-ui Adapter Development

1. Assign a fixed public IP to the AGentVPN application server.
2. Restrict the 3x-ui panel to that AGentVPN server IP.
3. Keep only the required public VPN ports available to VPN users.
4. Ensure the panel uses a valid HTTPS certificate.
5. Fill local `.env` values for `XUI_BASE_URL` and the supported authentication method.
6. Fill `XUI_HYSTERIA2_INBOUND_ID` and `XUI_VLESS_REALITY_INBOUND_ID`.
7. Run `python infrastructure/scripts/fetch_xui_openapi.py`.
8. Review `docs/3x-ui-openapi.json` for the installed version and confirm it contains no
   secrets or live client data.
9. Run the contract test.

Do not send passwords, API tokens, webhook keys, or bot tokens in chat.

## Required Before Payment Development

1. Configure the public domain.
2. Configure Telegram bot token locally.
3. Configure ENOT shop ID and secrets locally.
4. Confirm the active SBP method for the shop and set its actual code.
5. Configure Happ Provider ID only if owned and required.
