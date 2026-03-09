from odoo.tests import TransactionCase


class TestAccountMoveLine(TransactionCase):
    
    def test_storno_readonly_fields(self):
        """Test that price fields are readonly when is_storno is True"""
        
        # Create a customer invoice
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.env.ref('base.res_partner_2').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test Product',
                'price_unit': 100.0,
                'quantity': 1.0,
            })],
        })
        
        # Create a credit note (refund)
        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.env.ref('base.res_partner_2').id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Test Product Refund',
                'price_unit': 100.0,
                'quantity': 1.0,
            })],
        })
        
        # Check that refund lines are automatically marked as storno
        for line in refund.invoice_line_ids:
            self.assertTrue(line.is_storno, "Refund lines should be marked as storno")
        
        # Test that editing price on storno line raises error
        with self.assertRaises(Exception):
            refund.invoice_line_ids[0].write({'price_unit': 150.0})
        
        print("All tests passed!")
