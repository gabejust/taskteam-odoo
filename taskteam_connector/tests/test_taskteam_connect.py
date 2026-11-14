# Part of TaskTeam Connector. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.taskteam_connector.wizard.taskteam_connect_wizard import TASKTEAM_LOGIN


@tagged('post_install', '-at_install')
class TestTaskteamConnect(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref('base.user_admin')
        cls.company_a = cls.env.ref('base.main_company')
        cls.company_b = cls.env['res.company'].create({'name': 'TaskTeam Test Company B'})
        cls.admin.write({'company_ids': [(4, cls.company_b.id)]})
        cls.admin_env = cls.env(user=cls.admin)
        cls.Wizard = cls.admin_env['taskteam.connect.wizard']

    # Helpers ---------------------------------------------------------------

    def _wizard(self, **vals):
        vals.setdefault('consent', True)
        return self.Wizard.create(vals)

    def _connect(self, **vals):
        action = self._wizard(**vals)._connect()
        return action, action['context']['default_key']

    def _taskteam_users(self):
        return self.env['res.users'].with_context(active_test=False).search(
            [('login', '=', TASKTEAM_LOGIN)])

    def _keys(self, user):
        return self.env['res.users.apikeys'].search([('user_id', '=', user.id)])

    # Tests -----------------------------------------------------------------

    def test_consent_required(self):
        wizard = self._wizard(consent=False)
        with self.assertRaises(UserError):
            wizard._connect()
        # The button refuses before asking for the administrator's password.
        with self.assertRaisesRegex(UserError, 'consent'):
            wizard.action_connect()
        self.assertFalse(self._taskteam_users())

    def test_default_companies_are_all_allowed(self):
        wizard = self.Wizard.create({})
        self.assertEqual(wizard.company_ids, self.admin.company_ids)
        self.assertIn(self.company_b, wizard.company_ids)

    def test_no_api_group_on_odoo_17(self):
        """Odoo 17 has no api_key_duration, so no «TaskTeam API» group is made."""
        self.assertNotIn('api_key_duration', self.env['res.groups']._fields)
        groups_before = self.env['res.groups'].search_count([])
        self._connect()
        self.assertEqual(self.env['res.groups'].search_count([]), groups_before)

    def test_user_rights_and_no_password(self):
        self._connect(company_ids=[(6, 0, self.company_b.ids)])
        user = self._taskteam_users()
        self.assertEqual(len(user), 1)
        self.assertTrue(user.active)
        self.assertEqual(user.name, 'TaskTeam')
        self.assertTrue(user._is_internal())
        self.assertTrue(user.has_group('base.group_user'))
        self.assertTrue(user.has_group('hr.group_hr_user'))
        self.assertFalse(user.has_group('base.group_system'))
        self.assertFalse(user.has_group('base.group_erp_manager'))
        self.assertFalse(user.has_group('hr.group_hr_manager'))
        self.assertEqual(user.company_ids, self.company_b)
        self.assertEqual(user.company_id, self.company_b)
        self.env.cr.execute('SELECT password FROM res_users WHERE id = %s', [user.id])
        self.assertFalse(self.env.cr.fetchone()[0])

    def test_user_can_read_employees_companies_partners(self):
        employee = self.env['hr.employee'].create({
            'name': 'Field Worker', 'identification_id': 'X123', 'company_id': self.company_a.id})
        self._connect()
        user_env = self.env(user=self._taskteam_users())
        read = user_env['hr.employee'].browse(employee.id).read(
            ['name', 'company_id', 'job_id', 'work_phone', 'mobile_phone', 'work_email',
             'identification_id'])
        self.assertEqual(read[0]['identification_id'], 'X123')
        self.assertTrue(user_env['res.company'].search([]))
        partners = user_env['res.partner']
        if 'customer_rank' in partners._fields:
            # customer_rank / supplier_rank come with Invoicing (account).
            partners.search_read(
                [('customer_rank', '>', 0)], ['name', 'customer_rank', 'supplier_rank'])
        else:
            partners.search_read([('is_company', '=', True)], ['name', 'email', 'phone'])

    def test_key_without_expiry_and_shown_once(self):
        action, key = self._connect()
        user = self._taskteam_users()
        self.assertEqual(action['res_model'], 'taskteam.connect.key')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_login'], TASKTEAM_LOGIN)
        self.assertTrue(action['context']['default_odoo_url'].startswith('http'))
        # The key authenticates the TaskTeam user on the external API.
        self.assertEqual(
            self.env['res.users.apikeys']._check_credentials(scope='rpc', key=key), user.id)
        keys = self._keys(user)
        self.assertEqual(len(keys), 1)
        # Odoo 17 API keys have no expiry date.
        self.assertNotIn('expiration_date', keys._fields)
        self.assertNotIn('default_expiration_date', action['context'])
        # Odoo stores only a hash, and the wizard has no field holding the key.
        self.env.cr.execute('SELECT key FROM res_users_apikeys WHERE user_id = %s', [user.id])
        self.assertNotEqual(self.env.cr.fetchone()[0], key)
        self.assertNotIn('key', self.Wizard._fields)
        self.assertNotIn(key, str(self.Wizard.create({}).read()))

    def test_key_dialog_shows_key(self):
        """The dialog gets its values from the action context, as in the UI."""
        action, key = self._connect()
        spec = {name: {} for name in ('key', 'odoo_url', 'database', 'login')}
        values = self.admin_env['taskteam.connect.key'].with_context(
            action['context']).onchange({}, [], spec)['value']
        self.assertEqual(values['key'], key)
        self.assertEqual(values['login'], TASKTEAM_LOGIN)
        self.assertEqual(values['database'], self.env.cr.dbname)

    def test_rerun_creates_new_key_without_duplicates(self):
        _action, key1 = self._connect()
        wizard = self._wizard()
        self.assertTrue(wizard.connected)
        key2 = wizard._connect()['context']['default_key']
        self.assertNotEqual(key1, key2)
        user = self._taskteam_users()
        self.assertEqual(len(user), 1)
        self.assertEqual(len(self._keys(user)), 2)
        apikeys = self.env['res.users.apikeys']
        self.assertEqual(apikeys._check_credentials(scope='rpc', key=key1), user.id)
        self.assertEqual(apikeys._check_credentials(scope='rpc', key=key2), user.id)

    def test_disconnect_revokes_keys_and_archives_user(self):
        _action, key = self._connect()
        user = self._taskteam_users()
        self._wizard(consent=False).action_disconnect()
        self.assertFalse(user.active)
        self.assertFalse(self._keys(user))
        self.assertFalse(self.env['res.users.apikeys']._check_credentials(scope='rpc', key=key))
        self.assertFalse(self.Wizard.create({}).connected)
        # Connecting again reactivates the same user.
        self._connect()
        self.assertEqual(self._taskteam_users(), user)
        self.assertTrue(user.active)
        self.assertEqual(len(self._keys(user)), 1)

    def test_action_connect_requires_interactive_identity_check(self):
        with self.assertRaises(UserError):
            self._wizard().action_connect()
        self.assertFalse(self._taskteam_users())

    def test_only_admins(self):
        officer = self.env['res.users'].create({
            'name': 'HR Officer', 'login': 'hr_officer_tt',
            'groups_id': [(6, 0, [self.env.ref('hr.group_hr_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env(user=officer)['taskteam.connect.wizard'].create({'consent': True})
