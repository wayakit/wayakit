from odoo import models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_post_processing_values(self):
        res = super()._get_post_processing_values()
        res.update({'tracking_order_id': self.sale_order_ids[0].id if self.sale_order_ids else False})
        return res
