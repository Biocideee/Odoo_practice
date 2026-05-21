{
    'name': 'Plugit Checkbox POS',
    'version': '1.0', 'category': 'Point of Sale',
    'summary': 'Integration of Odoo POS with Checkbox (Cloud Signature)',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_config_views.xml',
        'views/res_users_views.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'plugit_checkbox/static/src/js/pos_order_patch.js',
            'plugit_checkbox/static/src/xml/pos_receipt_patch.xml'
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
