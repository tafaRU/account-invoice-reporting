# -*- coding: utf-8 -*-
# Copyright 2011 Domsense s.r.l. <http://www.domsense.com>
# Copyright 2013 Lorenzo Battistini <lorenzo.battistini@agilebg.com>
# Copyright 2017 Vicent Cubells <vicent.cubells@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools.misc import formatLang


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    order_line_ids = fields.Many2many(
        comodel_name='sale.order.line',
        relation='sale_order_line_invoice_rel',
        column1='invoice_line_id',
        column2='order_line_id',
        string='Order Lines',
        readonly=True,
    )

    prod_lot_ids = fields.Many2many(
        comodel_name='stock.production.lot',
        compute='_compute_prod_lots',
        string="Production Lots",
    )

    lot_formatted_note = fields.Html(
        string='Formatted Note',
        compute='_compute_line_lots',
    )

    @api.multi
    def _compute_prod_lots(self):
        for line in self:
            # Get the moves from the procurement: same approach of
            # sale.order.line._get_delivered_qty, in module sale_stock.
            moves = line.order_line_ids.mapped('procurement_ids.move_ids')
            moves = moves.filtered(
                lambda move:
                move.state == 'done'
                and not move.scrapped)

            # We only want the moves that:
            # 1. Haven't been returned.
            #
            # Note that every time a move move_0 is returned by move_1,
            # we have move_1.origin_returned_move_id = move_0.
            # As far as I know, there is no clue
            # in move_0 to signal that it has been returned,
            # so we have to search through all the moves.
            return_moves = moves.search([
                ('origin_returned_move_id', 'in', moves.ids)]) \
                .mapped('origin_returned_move_id')
            moves -= return_moves

            # 2. Have been sent to a customer
            moves = moves.filtered(
                lambda move:
                move.location_dest_id.usage == 'customer')

            line.prod_lot_ids = moves.mapped('quant_ids.lot_id')

    @api.multi
    def _compute_line_lots(self):
        for line in self:
            if line.prod_lot_ids:
                res = line.quantity_by_lot()
                note = u'<ul>'
                lot_strings = []
                for lot in line.prod_lot_ids:
                    lot_string = u'<li>S/N %s%s</li>' % (
                        lot.name, u' (%s)' % res[lot] if res.get(lot) else '')
                    lot_strings.append(lot_string)
                note += u' '.join(lot_strings)
                note += u'</ul>'
                line.lot_formatted_note = note

    @api.multi
    def quantity_by_lot(self):
        self.ensure_one()
        move_ids = self.move_line_ids
        res = {}
        for move in move_ids:
            for quant in move.quant_ids:
                if (
                    quant.lot_id and
                    quant.location_id.id == move.location_dest_id.id
                ):
                    if quant.lot_id not in res:
                        res[quant.lot_id] = quant.qty
                    else:
                        res[quant.lot_id] += quant.qty
        for lot in res:
            if lot.product_id.tracking == 'lot':
                res[lot] = formatLang(self.env, res[lot])
            else:
                # If not tracking By lots or not By Unique Serial Number,
                # quantity is not relevant
                res[lot] = False
        return res
