# Part of TaskTeam Connector. See LICENSE file for full copyright and licensing details.
"""One-screen assistant that prepares read access for TaskTeam.

This module has no business logic and never contacts any external server.
It only creates, inside this database, what an administrator would otherwise
create by hand: a group allowing 1-year API keys, a dedicated internal user
with minimal rights, and an API key for that user. The key is shown once and
is never stored in clear text (Odoo stores only its hash).
"""

import datetime

from odoo import Command, _, api, fields, models
from odoo.addons.base.models.res_users import check_identity
from odoo.exceptions import UserError

TASKTEAM_LOGIN = 'taskteam'
TASKTEAM_USER_NAME = 'TaskTeam'
TASKTEAM_GROUP_NAME = 'TaskTeam API'
# Odoo caps the lifetime of API keys of non-admin users with the highest
# ``api_key_duration`` among their groups.
KEY_DURATION_DAYS = 365
# Odoo 17 to 19 accept keys with scope NULL or 'rpc' for the external API;
# Odoo 20 requires a scope and uses 'rpc'. 'rpc' works on all of them.
KEY_SCOPE = 'rpc'
# Sales › User: Own Documents Only. Lets TaskTeam create draft sale orders
# (and attach the signed delivery note to them) without seeing or changing
# anybody else's orders. Only offered when the Sales app is installed.
SALES_GROUP_XMLID = 'sales_team.group_sale_salesman'


class TaskteamConnectWizard(models.TransientModel):
    _name = 'taskteam.connect.wizard'
    _description = 'Connect TaskTeam'

    consent = fields.Boolean(
        string='I agree',
        help='TaskTeam is an external service. Tick this box to allow it to '
             'read the data listed above with the key created here.',
    )
    company_ids = fields.Many2many(
        'res.company',
        string='Companies',
        default=lambda self: self.env.user.company_ids,
        domain=lambda self: [('id', 'in', self.env.user.company_ids.ids)],
        help='TaskTeam will only read data from these companies.',
    )
    odoo_url = fields.Char(string='Odoo address', compute='_compute_odoo_url')
    taskteam_user_id = fields.Many2one(
        'res.users', string='TaskTeam user', compute='_compute_connection')
    connected = fields.Boolean(compute='_compute_connection')
    api_key_ids = fields.Many2many(
        'res.users.apikeys', string='Existing keys', compute='_compute_connection')
    sales_available = fields.Boolean(compute='_compute_sales_available')
    allow_sale_orders = fields.Boolean(
        string='Allow TaskTeam to create draft sale orders',
        default=lambda self: self._default_allow_sale_orders(),
        help='TaskTeam creates sale orders in draft with the signed delivery '
             'note PDF attached. It never confirms, changes or deletes anything. '
             'Untick it and create a new key to take this permission away.',
    )

    def _compute_odoo_url(self):
        for wizard in self:
            wizard.odoo_url = wizard.get_base_url()

    def _compute_sales_available(self):
        available = bool(self._sales_group())
        for wizard in self:
            wizard.sales_available = available

    @api.model
    def _default_allow_sale_orders(self):
        group = self._sales_group()
        user = self._find_taskteam_user()
        return bool(group and user and group in user.sudo().groups_id)

    def _compute_connection(self):
        user = self._find_taskteam_user()
        keys = self._find_api_keys(user) if user else self.env['res.users.apikeys']
        for wizard in self:
            wizard.taskteam_user_id = user if user.active else False
            wizard.connected = bool(user.active)
            wizard.api_key_ids = keys

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    @api.model
    def _find_taskteam_user(self):
        """Return the TaskTeam user, archived or not (empty recordset if none)."""
        return self.env['res.users'].sudo().with_context(active_test=False).search(
            [('login', '=', TASKTEAM_LOGIN)], limit=1)

    @api.model
    def _find_taskteam_group(self):
        return self.env['res.groups'].sudo().with_context(lang='en_US').search(
            [('name', '=', TASKTEAM_GROUP_NAME)], limit=1)

    @api.model
    def _sales_group(self):
        """The Sales «Own Documents Only» group, only when Sales is installed."""
        installed = self.env['ir.module.module'].sudo().search_count(
            [('name', '=', 'sale'), ('state', '=', 'installed')])
        if not installed:
            return self.env['res.groups']
        return self.env.ref(SALES_GROUP_XMLID, raise_if_not_found=False) or self.env['res.groups']

    @api.model
    def _find_api_keys(self, user):
        return self.env['res.users.apikeys'].sudo().search(
            [('user_id', '=', user.id)], order='id desc')

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    @api.model
    def _get_or_create_group(self):
        group = self._find_taskteam_group()
        if not group:
            group = self.env['res.groups'].sudo().with_context(lang='en_US').create({
                'name': TASKTEAM_GROUP_NAME,
                'api_key_duration': KEY_DURATION_DAYS,
                'comment': 'Members can create API keys valid for up to 1 year. '
                           'Created by the TaskTeam Connector module.',
            })
        elif group.api_key_duration < KEY_DURATION_DAYS:
            group.api_key_duration = KEY_DURATION_DAYS
        return group

    def _get_or_create_user(self, group):
        self.ensure_one()
        companies = self.company_ids
        main_company = self.env.company if self.env.company in companies else companies[:1]
        required_groups = (
            self.env.ref('base.group_user')
            | self.env.ref('hr.group_hr_user')
            | group
        )
        user = self._find_taskteam_user()
        if user:
            user.write({
                'active': True,
                'company_ids': [Command.set(companies.ids)],
                'company_id': main_company.id,
                'groups_id': [Command.link(g.id) for g in required_groups],
            })
            return user
        return self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': TASKTEAM_USER_NAME,
            'login': TASKTEAM_LOGIN,
            'company_ids': [Command.set(companies.ids)],
            'company_id': main_company.id,
            # Set explicitly so the default groups of new users are not added.
            'groups_id': [Command.set(required_groups.ids)],
        })

    def _apply_sales_permission(self, user):
        """Give or take away the right to create draft sale orders."""
        self.ensure_one()
        group = self._sales_group()
        if not group:
            return
        if self.allow_sale_orders:
            user.write({'groups_id': [Command.link(group.id)]})
        elif group in user.groups_id:
            user.write({'groups_id': [Command.unlink(group.id)]})

    @api.model
    def _generate_api_key(self, user):
        """Generate an API key owned by ``user`` and return it in clear text.

        ``res.users.apikeys._generate`` creates the key for ``env.user``, so it
        runs as the TaskTeam user. It runs without sudo on purpose: Odoo then
        checks the expiry against the user's groups (``api_key_duration``),
        which proves the «TaskTeam API» group does its job.
        """
        expiration_date = fields.Datetime.now() + datetime.timedelta(days=KEY_DURATION_DAYS)
        name = 'TaskTeam %s' % fields.Date.to_string(fields.Date.context_today(self))
        key = self.env['res.users.apikeys'].with_user(user)._generate(
            KEY_SCOPE, name, expiration_date)
        return key, expiration_date

    def _check_can_connect(self):
        self.ensure_one()
        if not self.env.is_system():
            raise UserError(_('Only administrators can connect TaskTeam.'))
        if not self.consent:
            raise UserError(_(
                'Please tick the consent box first: TaskTeam is an external '
                'service and will read the data listed on this screen.'))
        if not self.company_ids:
            raise UserError(_('Select at least one company.'))

    def _connect(self):
        """Create (or reuse) the group and the user, then return a new key.

        Returns the window action that shows the key once.
        """
        self._check_can_connect()
        group = self._get_or_create_group()
        user = self._get_or_create_user(group)
        self._apply_sales_permission(user)
        key, expiration_date = self._generate_api_key(user)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'taskteam.connect.key',
            'name': _('Your TaskTeam key'),
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_key': key,
                'default_odoo_url': self.odoo_url,
                'default_database': self.env.cr.dbname,
                'default_login': user.login,
                'default_expiration_date': fields.Datetime.to_string(expiration_date),
            },
        }

    def action_connect(self):
        # Check consent before Odoo asks for the administrator's password.
        self._check_can_connect()
        return self.action_connect_confirmed()

    @check_identity
    def action_connect_confirmed(self):
        return self._connect()

    def action_disconnect(self):
        """Revoke every API key of the TaskTeam user and archive the user."""
        self.ensure_one()
        if not self.env.is_system():
            raise UserError(_('Only administrators can disconnect TaskTeam.'))
        user = self._find_taskteam_user()
        if user:
            self._find_api_keys(user)._remove()
            user.active = False
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('TaskTeam is disconnected: its keys are revoked '
                             'and its user is archived.'),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class TaskteamConnectKey(models.AbstractModel):
    """Shows the new key once. Nothing is stored: the values only travel in
    the action context to this dialog, like Odoo's own «API Key Ready»."""
    _name = 'taskteam.connect.key'
    _description = 'TaskTeam key (shown once)'

    # Needed for the onchange that fills the defaults from the context.
    id = fields.Id()
    key = fields.Char(string='API key', readonly=True)
    odoo_url = fields.Char(string='Odoo address', readonly=True)
    database = fields.Char(readonly=True)
    login = fields.Char(readonly=True)
    expiration_date = fields.Datetime(string='Valid until', readonly=True)
