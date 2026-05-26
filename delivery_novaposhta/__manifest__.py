{
    "name": "Plugit Нова Пошта",
    "version": "19.0.1.0.0",
    "author": "Vadym Serdiuk",
    "company": "Plugit",
    "website": "https://plugit.com.ua",
    "depends": ["plugit_delivery_base", "kw_phone_number_ua", "queue_job", "mail", "queue_job_cron_jobrunner"],
    "summary": "Інтеграція з Новою Поштою",
    "description": "Додай інструмент взаємодії з Новою Поштою. "
    "Отримай актуальний список відділень та поштоматів кожного дня. "
    "Створюй накладні, отримай розрахунок вартості відправлень",
    "category": "Inventory/Delivery",
    "data": [
        "security/ir.model.access.csv",
        "views/np_warehouse_views.xml",
        "views/np_street_views.xml",
        "views/np_settlement_views.xml",
        "data/cron_jobs.xml",
        "views/novaposhta_ttn_list.xml",
        "views/novaposhta_ttn_form.xml",
        "views/novaposhta_menus.xml",
        "views/res_partner_form.xml",
        "views/res_partner_list.xml",
        "views/stock_picking_form_view.xml",
        "views/delivery_carrier_form.xml",
    ],
    "license": "LGPL-3",
}
