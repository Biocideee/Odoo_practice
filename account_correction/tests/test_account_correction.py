from odoo.tests.common import TransactionCase
from odoo.tests import tagged

# Тег означає, що тест запуститься після встановлення модуля
@tagged('post_install', '-at_install')
class TestAccountCorrection(TransactionCase):

    def setUp(self):
        super(TestAccountCorrection, self).setUp()
        # 1. Створюємо тестового клієнта і товар
        self.partner = self.env['res.partner'].create({'name': 'Test Partner'})
        self.product = self.env['product.product'].create({'name': 'Test Product', 'list_price': 100.0})
        
        # 2. Створюємо тестовий рахунок
        self.invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2,
                'price_unit': 100.0,
            })]
        })

    def test_action_create_correction(self):
        """Тестуємо, чи правильно працює кнопка Скорегувати"""
        
        # 1. Запускаємо твою функцію
        action_result = self.invoice.action_create_correction()
        
        # 2. Отримуємо ID нового (скорегованого) рахунку
        new_invoice_id = action_result.get('res_id')
        new_invoice = self.env['account.move'].browse(new_invoice_id)
        
        # 3. Перевіряємо, чи створився рахунок взагалі
        self.assertTrue(new_invoice, "Новий рахунок не був створений!")
        
        # 4. Знаходимо сторно-рядок (той, де кількість мінусова)
        storno_line = new_invoice.invoice_line_ids.filtered(lambda l: l.quantity < 0)
        
        # 5. ГОЛОВНА ПЕРЕВІРКА: Чи збереглася наша галочка в базі?
        self.assertTrue(storno_line.is_correction_line, "БЕКЕНД ЗЛАМАВСЯ: Галочка is_correction_line не збереглася!")
        
        # 6. Перевіряємо математику
        self.assertEqual(storno_line.quantity, -2, "Кількість не стала мінусовою")