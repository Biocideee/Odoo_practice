# -*- coding: utf-8 -*-
{
    "name": "Plugit Укрпошта",
    "version": "19.0.1.0.0",
    "author": "Plugit",
    "company": "Plugit",
    "website": "https://plugit.com.ua",
    "summary": "Інтеграція з Укрпоштою",
    "description": (
        "Додає інтеграцію з Укрпоштою: створення накладних (ТТН), "
        "синхронізацію клієнтів, перевірку статусів відправлень."
    ),
    "category": "Inventory/Delivery",
    "depends": [
        "plugit_delivery_base",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_jobs.xml",
        "views/ukrposhta_ttn_action_form.xml",
        "views/ukrposhta_ttn_tree_view.xml",
        "views/view_partner_form.xml",
        "views/view_order_form.xml",
        "views/view_picking_form.xml",
        "views/delivery_carrier_form.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
