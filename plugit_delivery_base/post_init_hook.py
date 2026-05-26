def post_init_hook(env):
    lwh = env["stock.warehouse"].search([("code", "=", "LWH")], limit=1)
    wh = env["stock.warehouse"].search([("code", "=", "WH")], limit=1)
    if not lwh or not wh:
        return
    lwh.write({
        "delivery_steps": "pick_pack_ship",
        "resupply_wh_ids": [(6, 0, [wh.id])],
    })
    if lwh.int_type_id and wh.lot_stock_id:
        lwh.int_type_id.write({
            "default_location_src_id": lwh.lot_stock_id.id,
            "default_location_dest_id": wh.lot_stock_id.id,
        })
        remote_route = env["stock.route"].search(
            [("name", "=", "Віддалений: Поставити товар з Лавіна")],
            limit=1,
        )
        if remote_route:
            rule_vals = {
                "name": "LWH -> WH/Stock",
                "action": "pull",
                "picking_type_id": lwh.int_type_id.id,
                "location_src_id": lwh.lot_stock_id.id,
                "location_dest_id": wh.lot_stock_id.id,
                "procure_method": "make_to_stock",
                "company_id": lwh.company_id.id,
                "route_id": remote_route.id,
            }
            internal_rule = remote_route.rule_ids.filtered(
                lambda rule: rule.picking_type_id == lwh.int_type_id
            )[:1]
            if internal_rule:
                internal_rule.write(rule_vals)
            else:
                internal_rule = env["stock.rule"].create(rule_vals)
            (remote_route.rule_ids - internal_rule).write({"active": False})
