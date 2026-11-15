# Part of TaskTeam Connector. See LICENSE file for full copyright and licensing details.
{
    'name': 'TaskTeam Connector',
    'version': '18.0.1.1.0',
    'summary': 'Connect TaskTeam to Odoo: a dedicated user and API key so both stay '
               'in sync (people, contacts, time off, attendance, draft sale orders)',
    'category': 'Productivity',
    'author': 'Task Team Tech, S.L.',
    'support': 'support@taskteam.app',
    'website': 'https://taskteam.app',
    'license': 'LGPL-3',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/taskteam_connect_wizard_views.xml',
    ],
    'images': ['static/description/cover_screenshot.png'],
    'installable': True,
    'application': False,
}
