# -*- coding: utf-8 -*-
from odoo import fields, models


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    # order_id already exists (sale_loyalty/models/loyalty_card.py:10) and is the
    # dedup key — not redeclared here. Only the reviewed product is missing, and
    # the coupon email needs to name it.
    wayakit_review_product_id = fields.Many2one(
        'product.template', string="Reviewed Product", readonly=True, copy=False,
        help="Product whose website review generated this coupon.",
    )

    def _send_creation_communication(self, force_send=False):
        # ponytail: core hardcodes email_layout_xmlid='mail.mail_notification_light'
        # (loyalty/models/loyalty_card.py:148) and the caller's value always wins over
        # the template's own (mail/models/mail_template.py:615) — so our fully branded
        # template would get double-framed with Odoo's grey wrapper and a
        # "Powered by Odoo | Unfollow" footer. Only our program's coupons go out bare.
        program = self.env.ref(
            'wayakit_customization.loyalty_program_review_feedback',
            raise_if_not_found=False,
        )
        ours = self.filtered(lambda c: program and c.program_id == program)
        if not self.env.context.get('loyalty_no_mail') and not self.env.context.get('action_no_send_mail'):
            for coupon in ours:
                template = coupon.program_id.communication_plan_ids.filtered(
                    lambda c: c.trigger == 'create').mail_template_id
                if template and coupon._get_mail_partner():
                    template.send_mail(
                        coupon.id, force_send=force_send, email_layout_xmlid=False)
                # Second channel, same coupon. Deliberately after the email: the
                # helper swallows its own errors, so a WhatsApp outage can never
                # cost the customer the coupon mail.
                coupon._wayakit_send_coupon_whatsapp()
        return super(LoyaltyCard, self - ours)._send_creation_communication(force_send=force_send)

    def _wayakit_send_coupon_whatsapp(self):
        """Push the coupon code over WhatsApp too (template customer_coupon_code_2).

        That template carries a single Free Text -- the code. The redeem link
        /coupon/<code> stays email-only: the Meta-approved body has no room for a
        URL. Dedup is untouched and still lives in rating_rating.py: this runs
        only on card CREATION, so 3 reviews of one order = 1 card = 1 message.
        """
        self.ensure_one()
        template = self.env.ref(
            'wayakit_customization.whatsapp_template_review_coupon',
            raise_if_not_found=False,
        )
        if self.partner_id:
            self.partner_id._wayakit_send_whatsapp(template, [self.code])