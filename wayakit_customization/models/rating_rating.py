# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RatingRating(models.Model):
    _inherit = 'rating.rating'

    @api.model_create_multi
    def create(self, vals_list):
        ratings = super().create(vals_list)
        for rating in ratings:
            try:
                rating._wayakit_grant_review_coupon()
            except Exception:
                # A coupon failure must never block the review itself.
                _logger.exception("Review coupon failed for rating %s", rating.id)
        return ratings

    def _wayakit_grant_review_coupon(self):
        """Mint a 10% coupon the first time a customer reviews a product of an order.

        Closes the loop started by the "Feedback Generic" email (mail.template 106),
        which is sent ~2 weeks after delivery and links to
        ksasystem.wayakit.com<product website_url>#o_product_page_reviews — so every
        review lands here as a rating.rating on product.template.

        One coupon per SALE ORDER: reviewing 3 products of the same order gives 1
        coupon, reviewing only 1 gives it too. Re-posting/"editing" a review creates
        a brand new rating.rating (message_id is dropped by
        portal/controllers/mail.py:162) — the same order dedup absorbs it.
        """
        self.ensure_one()
        if self.res_model != 'product.template' or not self.partner_id or self.rating < 1:
            return
        program = self.env.ref(
            'wayakit_customization.loyalty_program_review_feedback',
            raise_if_not_found=False,
        )
        if not program or not program.active:
            _logger.warning("Review coupon skipped: program 'feedback' missing or archived")
            return
        # Same order the feedback email pointed at: newest confirmed KSA-website
        # order containing the reviewed product. No order -> the reviewer never
        # bought it here, no coupon.
        order = self.env['sale.order'].sudo().search([
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ('sale', 'done')),
            ('website_id', '=', program.website_id.id),
            ('order_line.product_id.product_tmpl_id', '=', self.res_id),
        ], order='date_order desc', limit=1)
        if not order or self.env['loyalty.card'].sudo().search_count([
            ('program_id', '=', program.id),
            ('order_id', '=', order.id),
        ]):
            return
        # points == reward.required_points (1) is what makes the coupon single-use
        # (sale_loyalty/models/sale_order.py:1083). Program-wide "Limit Usage" must
        # stay OFF or the first redemption kills the program for everyone.
        card = self.env['loyalty.card'].sudo().create({
            'program_id': program.id,
            'partner_id': self.partner_id.id,
            'order_id': order.id,
            'points': 1,
            'expiration_date': fields.Date.context_today(self) + timedelta(days=60),
            'wayakit_review_product_id': self.res_id,
        })
        _logger.info(
            "Review coupon %s granted to %s for order %s (review on %s)",
            card.code, self.partner_id.display_name, order.name, self.res_name,
        )