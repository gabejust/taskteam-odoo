# Part of TaskTeam Connector. See LICENSE file for full copyright and licensing details.
"""1.1.0: TaskTeam syncs both ways, so its user needs more rights.

When the module is upgraded, give an existing TaskTeam user the groups the
wizard now gives (Contacts › Creation and, when those apps are installed,
Time Off › Administrator and Attendances › Officer: Manage all attendances).
It also gets an email address if it has none (Odoo 17 needs one to
approve time off). The key does not change. A disconnected (archived)
user is left alone.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['taskteam.connect.wizard']._update_taskteam_user_rights()
