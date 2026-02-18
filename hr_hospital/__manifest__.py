{
    'name': 'Hospital',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'depends': ['base', 'mail', 'hr', 'account'],
    'data' : [
        'security/ir.model.access.csv',
        'views/hr_hospital_menus.xml',
        'views/account_move_view.xml'
    ],
}