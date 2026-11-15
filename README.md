# TaskTeam Connector for Odoo

Odoo module that prepares access for TaskTeam, an external task and chat app for teams run
by Task Team Tech, S.L. TaskTeam **reads and writes** the data the office chooses to sync,
so each person keeps working in the program they know and both stay the same: people, job
positions, contacts, time off, attendances and, only if the administrator allows it, draft
sale orders. TaskTeam never deletes anything in Odoo: it archives or cancels instead.

The module has **no business logic and makes no outbound connection**. It only creates,
inside the customer's database and after an explicit consent, what an administrator would
otherwise create by hand.

## Branches

One branch per Odoo version, as required by the Odoo Apps store:

| Branch | Module version |
|--------|----------------|
| `17.0` | `17.0.1.1.0`   |
| `18.0` | `18.0.1.1.0`   |
| `19.0` | `19.0.1.1.0`   |
| `20.0` | `20.0.1.1.0`   |

Odoo 17 has no expiry for API keys, so on `17.0` the key and the «TaskTeam API» group
below do not apply: the key stays valid until it is revoked.

## What it does

*Settings › TaskTeam* opens the **Connect TaskTeam** assistant (administrators only). After
the administrator ticks the consent box, one click:

1. creates the group **TaskTeam API** with `api_key_duration = 365` (or reuses it and raises
   it to 365 days);
2. creates the internal user **TaskTeam** (login `taskteam`, email `taskteam@<company email domain>`,
   no password, no invitation email), restricted to the selected companies (default: all
   companies the administrator can access), with the groups below; an archived TaskTeam user
   is reactivated instead of duplicated;
3. generates an API key for that user valid for 365 days with
   `env['res.users.apikeys'].with_user(user)._generate('rpc', name, expiration_date)`
   (runs without sudo, so Odoo checks the duration against the user's groups), and shows it
   once together with the Odoo address. Odoo stores only the key hash; the module stores
   nothing.

Running it again creates a new key; old keys keep working until revoked. **Disconnect**
(with confirmation) revokes every key of the TaskTeam user and archives it.

### Groups of the TaskTeam user

Each group is given only when its app is installed.

| Group | Why |
|-------|-----|
| *Internal User* (`base.group_user`) | Use the external API. |
| *Employees › Officer* (`hr.group_hr_user`) | Read and write employees and job positions. |
| *Contacts › Creation* (`base.group_partner_manager`) | Create and edit customers and suppliers. |
| *Time Off › Administrator* (`hr_holidays.group_hr_holidays_manager`) | Approve, refuse and validate anybody's time off, and create or archive time off types (*Officer* can only read the types). |
| *Attendances › Officer: Manage all attendances* (`hr_attendance.group_hr_attendance_user`) | Create and edit everybody's attendances. |
| *Sales › User: Own Documents Only* (`sales_team.group_sale_salesman`) | Only if the administrator ticks it: create draft sale orders. |
| *TaskTeam API* | API keys valid for 1 year. |

On Odoo 17 and 18 the attendances group is *Attendances › Administrator*
(`hr_attendance.group_hr_attendance_manager`), because there *Officer* only sees the employees
it manages.

**Upgrading the module** (from 1.0.0) gives an existing TaskTeam user the new groups; the key
does not change. If Time Off or Attendances is installed later, *Settings › TaskTeam* shows
**Update permissions**, which does the same.

Creating a key goes through Odoo's `check_identity` (the administrator may be asked for
their password), like Odoo's own *New API Key* button.

## What TaskTeam does with the key

Through Odoo's external API, with the TaskTeam user's rights only, and only for what the office
turns on in TaskTeam:

- `hr.employee` and `hr.job`: reads and writes name, company, job position, work phone and
  mobile, work email. `identification_id` is only read, to recognise each person;
- `res.partner`: reads and writes customers and suppliers;
- `hr.leave` and the time off types: reads and writes requests, approves or refuses them, and
  creates or archives types (Time Off installed);
- `hr.attendance`: reads and writes check-in and check-out times (Attendances installed);
- `res.company` and `res.users.apikeys` (the key's own expiry date): only reads.

Only if the administrator ticks *Allow TaskTeam to create draft sale orders* (shown when the
Sales app is installed; `sale` is not a dependency), TaskTeam creates `sale.order` records in
draft, with their lines and the signed delivery note PDF as an `ir.attachment`, for the office
to review and invoice. It never confirms them. Unticking the option and creating a new key
removes the group again.

TaskTeam never deletes anything (`unlink`) in Odoo: what is removed in TaskTeam is archived, or
cancelled for time off.

## Layout

```
taskteam_connector/
├── __manifest__.py
├── security/ir.model.access.csv      # wizard: base.group_system only
├── wizard/                           # taskteam.connect.wizard + taskteam.connect.key (shown once)
├── migrations/                       # 1.1.0: new groups for an existing TaskTeam user
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

Use the image that matches the branch (`odoo:17.0` … `odoo:20.0`). Run it a second time with
`-i hr_holidays,hr_attendance,sale,taskteam_connector` (and another database name) to test
the time off, attendances and sales rights too.

## License

LGPL-3. See [LICENSE](LICENSE).
