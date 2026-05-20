/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async fiscalizeInCheckbox() {
        const order = this.currentOrder;
        const pos = this.pos || this.env.services.pos;

        const session = pos.session || pos.pos_session;
        const config = pos.config;

        let token = session ? session.checkbox_access_token : null;
        const licenseKey = config ? config.checkbox_license_key : null;

        // ==========================================
        // НОВИЙ БЛОК: Синхронізація токена з бекендом
        // Якщо токена немає, але зміна відкрита, запитуємо його з БД
        // ==========================================
        if (!token && session && session.id) {
            try {
                const sessionData = await this.env.services.orm.read('pos.session', [session.id], ['checkbox_access_token']);
                if (sessionData && sessionData.length > 0 && sessionData[0].checkbox_access_token) {
                    token = sessionData[0].checkbox_access_token;
                    session.checkbox_access_token = token; // Зберігаємо в пам'яті браузера
                }
            } catch (e) {
                console.warn("Помилка синхронізації токена з бекенду:", e);
            }
        }

        if (!token || !licenseKey) {
            console.warn("Checkbox токен або ключ ліцензії відсутні. Фіскалізація пропущена.");
            return true;
        }

        const orderlines = order.lines || (typeof order.get_orderlines === 'function' ? order.get_orderlines() : []);

        const goods = orderlines.map(line => {
            const product = line.product_id || (typeof line.getProduct === 'function' ? line.getProduct() : {});
            const rawCode = product.default_code || product.id?.toString() || '000';
            const cleanCode = rawCode.replace(/[^a-zA-Z0-9]/g, '');

            // Використовуємо знайдений метод getQuantity()
            const quantity = typeof line.getQuantity === 'function' ? line.getQuantity() : (line.qty || 1);

            let unitPriceWithTax = 0;

            // 1. Спершу намагаємося дістати фінальну суму з ПДВ з об'єкта prices (який ми знайшли в getTip)
            if (line.prices) {
                const totalWithTax = line.prices.total_included_currency || line.prices.total_included || line.prices.total_with_tax || 0;
                if (totalWithTax) {
                    unitPriceWithTax = totalWithTax / quantity;
                }
            }

            // 2. Якщо об'єкта prices немає, використовуємо displayPriceUnit (знайдено в getTotalDiscount)
            if (!unitPriceWithTax && line.displayPriceUnit) {
                unitPriceWithTax = line.displayPriceUnit;
            }

            // 3. Базовий фоллбек на чисту ціну (знайдено в setUnitPrice)
            if (!unitPriceWithTax) {
                unitPriceWithTax = line.price_unit || 0;
            }

            // Залізобетонний захист: Checkbox викидає помилку 422, якщо ціна <= 0
            if (unitPriceWithTax <= 0) {
                unitPriceWithTax = 0.01;
            }

            return {
                good: {
                    code: cleanCode,
                    name: product.display_name || product.name || "Товар",
                    // Переводимо у копійки для Checkbox
                    price: Math.round(unitPriceWithTax * 100)
                },
                quantity: Math.round(quantity * 1000)
            };
        });

        const paymentLines = order.payment_ids || (typeof order.get_paymentlines === 'function' ? order.get_paymentlines() : []);
        const payments = paymentLines.map(p => {
            const method = p.payment_method_id || p.payment_method;
            const isCash = method?.is_cash_count;
            const amount = typeof p.get_amount === 'function' ? p.get_amount() : (p.amount || 0);

            return {
                type: isCash ? "CASH" : "CARD",
                value: Math.round(amount * 100)
            };
        });

        const cashierName = (pos.get_cashier && pos.get_cashier().name) || (pos.cashier && pos.cashier.name) || "Касир";
        const partner = order.partner_id || (typeof order.get_partner === 'function' ? order.get_partner() : null);

        const payload = {
            goods: goods,
            payments: payments,
            cashier_name: cashierName,
            email: partner ? partner.email : null
        };

        try {
            const response = await fetch("https://api.checkbox.ua/api/v1/receipts/sell", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`,
                    "X-License-Key": licenseKey
                },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                const result = await response.json();
                console.log("Чек успішно фіскалізовано в Checkbox. ID чека:", result.id);

                order.checkbox_receipt_url = `https://check.checkbox.ua/${result.id}`;
                order.checkbox_receipt_id = result.id;

                return true;
            } else {
                const errText = await response.text();
                alert("Помилка фіскалізації ПРРО: " + errText);
                return false;
            }
        } catch (error) {
            console.error("Критична помилка зв'язку з Checkbox ПРРО", error);
            alert("Відсутній зв'язок з сервером ПРРО Checkbox: " + error.message);
            return false;
        }
    },

    async validateOrder(isForceValidate) {
        const isFiscalized = await this.fiscalizeInCheckbox();
        if (isFiscalized) {
            return await super.validateOrder(...arguments);
        }
    }
});

patch(PosOrder.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.checkbox_receipt_url = this.checkbox_receipt_url;
        json.checkbox_receipt_id = this.checkbox_receipt_id;
        return json;
    },
    export_for_printing() {
        const json = super.export_for_printing(...arguments);
        json.checkbox_receipt_url = this.checkbox_receipt_url;
        json.checkbox_receipt_id = this.checkbox_receipt_id;
        return json;
    }
});