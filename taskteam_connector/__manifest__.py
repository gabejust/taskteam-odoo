# Part of TaskTeam Connector. See LICENSE file for full copyright and licensing details.
{
    'name': 'TaskTeam Connector',
    'version': '19.0.1.0.0',
    'summary': 'Create a dedicated read-only API user and key so TaskTeam '
               'can read your employees, companies and contacts',
    'category': 'Productivity',
    'author': 'Task Team Tech, S.L.',
    'support': 'support@taskteam.app',
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
