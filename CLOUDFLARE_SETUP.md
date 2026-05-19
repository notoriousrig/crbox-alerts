# Cloudflare Setup — alerts.crbox.ca

One-time wiring of DNS, Cloudflare Tunnel ingress, and Cloudflare Access
for `alerts.crbox.ca`. All three are done via the Cloudflare API.

Reference values (the secret token and the account/zone/tunnel IDs are
in `home_network/MEMORY.md` — never commit them to this repo):

- API token: `$CF_API_TOKEN`
- Account ID: `$CF_ACCOUNT_ID`
- Zone ID (crbox.ca): `$CF_ZONE_ID`
- Tunnel UUID: `$CF_TUNNEL_UUID`
- Team domain: `crbox.cloudflareaccess.com`
- `Allow-Chris` policy ID: `$CF_ACCESS_POLICY_ID`

Export them in your shell before running the snippets below:

```bash
export CF_API_TOKEN=...
export CF_ACCOUNT_ID=...
export CF_ZONE_ID=...
export CF_TUNNEL_UUID=...
export CF_ACCESS_POLICY_ID=...
```

## 1. DNS — CNAME `alerts.crbox.ca` to the tunnel

```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
  -d "{\"type\":\"CNAME\",\"name\":\"alerts\",\"content\":\"$CF_TUNNEL_UUID.cfargotunnel.com\",\"proxied\":true}"
```

## 2. Tunnel ingress — insert before the 404 catch-all

```bash
# Pull current config:
curl -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/cfd_tunnel/$CF_TUNNEL_UUID/configurations" > current.json
# Edit ingress[] to insert (before the http_status:404 entry):
#   { "hostname": "alerts.crbox.ca", "service": "http://traefik:8443" }
# Then PUT the modified config back:
curl -X PUT \
  -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
  --data @new-config.json \
  "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/cfd_tunnel/$CF_TUNNEL_UUID/configurations"
```

## 3. Access app + policy

```bash
curl -X POST "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/access/apps" \
  -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "crbox-alerts",
    "domain": "alerts.crbox.ca",
    "type": "self_hosted",
    "session_duration": "24h",
    "app_launcher_visible": true,
    "policies": ["'"$CF_ACCESS_POLICY_ID"'"]
  }'
```

Take the returned `aud` from `data.aud` and put it into the Portainer
stack's env vars as `CF_ACCESS_AUD`. Redeploy the stack.

## Verifying

```bash
# Should redirect to Cloudflare Access login, not the app
curl -I https://alerts.crbox.ca

# Once authenticated in browser, /api/me should return your email
```
