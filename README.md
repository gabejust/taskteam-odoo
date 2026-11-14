# TaskTeam Connector for Odoo

Odoo module that prepares read-only access for TaskTeam, an
external task and chat app for field teams run by Task Team Tech, S.L.

The module has **no business logic and makes no outbound connection**. It only creates,
inside the customer's database and after an explicit consent, what an administrator would
otherwise create by hand.

## Branches

One branch per Odoo version, as required by the Odoo Apps store:

| Branch | Module version |
|--------|----------------|
| `19.0` | `19.0.1.0.0`   |
| `20.0` | `20.0.1.0.0`   |

## What it does

*Settings › TaskTeam* opens the **Connect TaskTeam** assistant (administrators only). After
the administrator ticks the consent box, one click:

1. creates the group **TaskTeam API** with `api_key_duration = 365` (or reuses it and raises
   it to 365 days);
2. creates the internal user **TaskTeam** (login `taskteam`, no password, no invitation
   email) with *Internal User*, *Employees › Officer* (`hr.group_hr_user`) and *TaskTeam API*,
   restricted to the selected companies (default: all companies the administrator can access);
   an archived TaskTeam user is reactivated instead of duplicated;
3. generates an API key for that user valid for 365 days with
   `env['res.users.apikeys'].with_user(user)._generate('rpc', name, expiration_date)`
   (runs without sudo, so Odoo checks the duration against the user's groups), and shows it
   once together with the Odoo address. Odoo stores only the key hash; the module stores
   nothing.

Running it again creates a new key; old keys keep working until revoked. **Disconnect**
(with confirmation) revokes every key of the TaskTeam user and archives it.

Creating a key goes through Odoo's `check_identity` (the administrator may be asked for
their password), like Odoo's own *New API Key* button.

## What TaskTeam reads

Through Odoo's external API, with the key:

- `hr.employee`: name, company, job, work phone/mobile, work email, `identification_id` when
  allowed by the TaskTeam settings;
- `res.company`;
- `res.partner` with `customer_rank` / `supplier_rank`;
- `res.users.apikeys`: the key's own expiry date.

Note: *Employees › Officer* is the smallest standard group that can read employees' private
fields; technically it can also edit employees. TaskTeam only reads.

## Layout

```
taskteam_connector/
├── __manifest__.py
├── security/ir.model.access.csv      # wizard: base.group_system only
├── wizard/                           # taskteam.connect.wizard + taskteam.connect.key (shown once)
├── tests/                            # TransactionCase tests
└── static/description/               # icon.png, cover_screenshot.png, index.html (store listing)
```

## Run the tests locally (Docker)

```sh
docker network create tt-odoo
docker run -d --name tt-odoo-db --network tt-odoo \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres postgres:16
docker run --rm --network tt-odoo -v "$PWD":/mnt/extra-addons odoo:19.0 \
  odoo --db_host=tt-odoo-db --db_user=odoo --db_password=odoo -d tt_test \
  -i taskteam_connector --test-enable --stop-after-init --without-demo=all
docker rm -f tt-odoo-db && docker network rm tt-odoo
```

Use `odoo:20.0` on the `20.0` branch.

## License

LGPL-3. See [LICENSE](LICENSE).
