# TaskTeam Connector for Odoo

Odoo module that prepares access for TaskTeam, an external task and chat app for field
teams run by Task Team Tech, S.L.: read access to employees, companies and contacts and,
only if the administrator allows it, the right to create draft sale orders.

The module has **no business logic and makes no outbound connection**. It only creates,
inside the customer's database and after an explicit consent, what an administrator would
otherwise create by hand.

## Branches

One branch per Odoo version, as required by the Odoo Apps store:

| Branch | Module version |
|--------|----------------|
| `17.0` | `17.0.1.0.0`   |
| `18.0` | `18.0.1.0.0`   |
| `19.0` | `19.0.1.0.0`   |
| `20.0` | `20.0.1.0.0`   |

## What it does

*Settings › TaskTeam* opens the **Connect TaskTeam** assistant (administrators only). After
the administrator ticks the consent box, one click:

1. creates the internal user **TaskTeam** (login `taskteam`, no password, no invitation
   email) with *Internal User* and *Employees › Officer* (`hr.group_hr_user`), restricted to
   the selected companies (default: all companies the administrator can access); an archived
   TaskTeam user is reactivated instead of duplicated;
2. generates an API key for that user with
   `env['res.users.apikeys'].with_user(user)._generate('rpc', name)` and shows it once
   together with the Odoo address. Odoo stores only the key hash; the module stores nothing.

**Odoo 17 has no API key expiry** (`expiration_date` and the groups' `api_key_duration`
arrived in Odoo 18), so on this branch the key does not expire and no *TaskTeam API* group is
created. The key stays valid until it is revoked (for example with **Disconnect**).

Running it again creates a new key; old keys keep working until revoked. **Disconnect**
(with confirmation) revokes every key of the TaskTeam user and archives it.

Creating a key goes through Odoo's `check_identity` (the administrator may be asked for
their password), like Odoo's own *New API Key* button.

## What TaskTeam does with the key

Through Odoo's external API, with the TaskTeam user's rights only, it reads:

- `hr.employee`: name, company, job, work phone/mobile, work email, `identification_id` when
  allowed by the TaskTeam settings;
- `res.company`;
- `res.partner` with `customer_rank` / `supplier_rank`;
- `res.users.apikeys`: the key's own record (no expiry date on Odoo 17).

Only if the administrator ticks *Allow TaskTeam to create draft sale orders* (shown when the
Sales app is installed; `sale` is not a dependency), the user also gets
*Sales › User: Own Documents Only* (`sales_team.group_sale_salesman`). TaskTeam then creates
`sale.order` records in draft, with their lines and the signed delivery note PDF as an
`ir.attachment`, for the office to review and invoice. It never confirms, changes or deletes
anything. Unticking the option and creating a new key removes the group again.

Note: *Employees › Officer* is the smallest standard group that can read employees' private
fields; technically it can also edit employees. *Own Documents Only* can also edit the orders
TaskTeam created and orders without a salesperson. TaskTeam does neither.

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
docker run --rm --network tt-odoo -v "$PWD":/mnt/extra-addons odoo:17.0 \
  odoo --db_host=tt-odoo-db --db_user=odoo --db_password=odoo -d tt_test \
  -i taskteam_connector --test-enable --stop-after-init --without-demo=all
docker rm -f tt-odoo-db && docker network rm tt-odoo
```

Use the image that matches the branch (`odoo:17.0` on this branch).

## License

LGPL-3. See [LICENSE](LICENSE).
