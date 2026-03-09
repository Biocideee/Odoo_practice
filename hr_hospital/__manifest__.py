{
    'name': 'Hospital',
    'version': '1.0.0',
    'category': 'Human Resources',
    'depends': ['base', 'mail', 'hr', 'account'],
    'data' : [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/visits_views.xml',
        'views/patients_views.xml',
        'views/doctor_views.xml',
        'views/hr_hospital_menus.xml',
        'views/account_move_line_views.xml',
    ],
    'application': True,
}