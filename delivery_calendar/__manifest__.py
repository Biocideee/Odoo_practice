{
    "name": "Delivery Calendar",
    "summary": "A calendar to visualize deliveries.",
    "description": """
        This module provides a calendar view to track and manage deliveries.
    """,
    "category": "Inventory/Delivery",
    "version": "19.0.1.0.0",
    "depends": ["base", "account", "calendar"],
    "data": [
        "data/delivery_type.xml",
        "data/ir_cron_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
