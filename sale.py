# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Sale', 'SaleLine', 'Production']
__metaclass__ = PoolMeta


class Sale:
    __name__ = 'sale.sale'

    productions = fields.Function(fields.One2Many('production', None,
            'Productions'),
        'get_productions')

    def get_productions(self, name):
        productions = []
        for line in self.lines:
            if line.production:
                productions.append(line.production.id)
        return productions

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['productions'] = None
        return super(Sale, cls).copy(sales, default=default)

    @classmethod
    def process(cls, sales):
        super(Sale, cls).process(sales)
        for sale in sales:
            if sale.state in ('done', 'cancel'):
                continue
            sale.create_productions()

    def create_productions(self):
        for line in self.lines:
            with Transaction().set_user(0, set_context=True):
                production = line.get_production()
                if production:
                    production.save()
                    line.production = production
                    line.save()


class SaleLine:
    __name__ = 'sale.line'

    production = fields.Many2One('production', 'Production', readonly=True)

    def get_production(self):
        pool = Pool()
        Production = pool.get('production')

        if self.production or not self.product or not self.product.raw_product:
            return None

        inputs = self._get_production_inputs()
        outputs = self._get_production_outputs()

        if not inputs or not outputs:
            return None

        production = Production()
        production.product = self.product
        production.warehouse = self.sale.warehouse
        production.location = self.sale.warehouse.production_location
        production.reference = self.rec_name
        production.company = self.sale.company
        production.inputs = inputs
        production.outputs = outputs
        production.notes = self.note
        production.state = 'draft'
        return production

    def _get_production_operations(self):
        return []

    def _get_production_inputs(self):
        pool = Pool()
        Move = pool.get('stock.move')
        defaults = {
            'from_location': self.warehouse.storage_location.id,
            'to_location': self.warehouse.production_location.id,
            'origin': None,
            'shipment': None,
            }
        moves = []
        to_write = []
        for move in Move.copy(self.moves, defaults):
            if move.product.has_raw_products and move.product.raw_product:
                to_write.extend(([move], {
                            'product': move.product.raw_product.id,
                        }))
            moves.append(move)
        if to_write:
            Move.write(*to_write)
        return moves

    def _get_production_outputs(self):
        pool = Pool()
        Move = pool.get('stock.move')
        if not self.moves:
            return []
        return Move.copy(self.moves, {
                'from_location': self.warehouse.production_location.id,
                'to_location': self.warehouse.storage_location.id,
                'origin': None,
                'shipment': None,
                })

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['production'] = None
        return super(SaleLine, cls).copy(lines, default=default)


class Production:
    __name__ = 'production'

    sale_lines = fields.One2Many('sale.line', 'production', 'Sale Line',
        readonly=True)
