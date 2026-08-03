# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.osv import expression


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _trigger_assign(self):
        """Re-reserva los moves pendientes cuando entra stock.

        Core (stock/models/stock_move.py:2241) compara la ubicacion origen del move
        pendiente contra el destino del move terminado con igualdad EXACTA. Las reglas
        de putaway de Wayakit dejan el producto de las ordenes de produccion en
        WH/Stock/Rack*/Module*, asi que las entregas que salen de WH/Stock nunca hacian
        match y se quedaban sin reservar hasta que alguien apretaba Check Availability.

        Unico cambio vs. core: 'parent_of' en lugar de '='. Matchea cualquier ancestro
        del destino, que es exactamente el stock que _action_assign() puede consumir.
        """
        if not self or self.env['ir.config_parameter'].sudo().get_param('stock.picking_no_auto_reserve'):
            return

        domains = []
        for move in self:
            domains.append([('product_id', '=', move.product_id.id),
                            ('location_id', 'parent_of', move.location_dest_id.id)])
        static_domain = [('state', 'in', ['confirmed', 'partially_available']),
                         ('procure_method', '=', 'make_to_stock'),
                         '|',
                            ('reservation_date', '<=', fields.Date.today()),
                            ('picking_type_id.reservation_method', '=', 'at_confirm')]
        moves_to_reserve = self.env['stock.move'].search(
            expression.AND([static_domain, expression.OR(domains)]),
            order='priority desc, date asc, id asc')
        moves_to_reserve._action_assign()
