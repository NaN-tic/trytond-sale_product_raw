# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Sale', 'SaleLine',
    'SaleLineIgnoredProduction', 'SaleLineRecreatedProduction',
    'HandleProductionExceptionAsk', 'HandleProductionException']


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    production_state = fields.Selection([
            ('none', 'None'),
            ('waiting', 'Waiting'),
            ('started', 'Started'),
            ('produced', 'Produced'),
            ('exception', 'Exception'),
            ], 'Production State', readonly=True, required=True)
    productions = fields.Function(fields.Many2Many('production', None, None,
            'Productions'),
        'get_productions', searcher='search_productions')

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls._buttons.update({
                'handle_production_exception': {
                    'invisible': ((Eval('production_state') != 'exception')
                        | (Eval('state') == 'cancel')),
                    'readonly': ~Eval('groups', []).contains(
                        Id('sale', 'group_sale')),
                    },
                })

    @staticmethod
    def default_production_state():
        return 'none'

    def get_productions(self, name):
        productions = []
        for line in self.lines:
            for production in line.productions:
                productions.append(production.id)
        return productions

    @classmethod
    def search_productions(cls, name, clause):
        return [('lines.productions.id',) + tuple(clause[1:])]

    def get_production_state(self):
        '''
        Return the production state for the sale.
        '''
        if self.productions:
            if any(l.productions_exception for l in self.lines):
                return 'exception'
            elif all(l.productions_done for l in self.lines):
                return 'produced'
            if any(p.started for p in self.productions):
                return 'started'
            else:
                return 'waiting'
        return 'none'

    def set_production_state(self):
        '''
        Set the production state.
        '''
        state = self.get_production_state()
        if self.production_state != state:
            self.write([self], {
                    'production_state': state,
                    })

    @classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['production_state'] = 'none'
        default['productions'] = None
        return super(Sale, cls).copy(sales, default=default)

    @classmethod
    @ModelView.button_action(
        'sale_product_raw.wizard_production_handle_exception')
    def handle_production_exception(cls, sales):
        pass

    @classmethod
    def process(cls, sales):
        for sale in sales:
            if sale.state not in ('confirmed', 'processing', 'done'):
                continue
            sale.create_productions()
            sale.set_production_state()
        super(Sale, cls).process(sales)

    def create_productions(self):
        production_by_line = {}
        for line in self.lines:
            production = line.get_production()
            if production:
                production.save()
                production_by_line[line] = production
        return production_by_line


class SaleLine(metaclass=PoolMeta):
    __name__ = 'sale.line'

    productions = fields.One2Many('production', 'origin', 'Productions',
        readonly=True)
    productions_ignored = fields.Many2Many('sale.line-ignored-production',
        'sale_line', 'production', 'Ignored Productions', readonly=True)
    productions_recreated = fields.Many2Many('sale.line-recreated-production',
        'sale_line', 'production', 'Recreated Productions', readonly=True)
    productions_done = fields.Function(fields.Boolean('Productions Done'),
        'get_production_done')
    productions_exception = fields.Function(
        fields.Boolean('Productions Exception'),
        'get_production_exception')

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()

    def get_rec_name(self, name):
        return "%s (%s, %s)" % (super(SaleLine, self).get_rec_name(name),
                self.sale.get_rec_name(name),
                self.sale.party.get_rec_name(name))

    def get_production_done(self, name):
        Uom = Pool().get('product.uom')
        done = True
        if not self.product:
            return True
        if self.quantity < 0.0:
            return True
        if not self.product.raw_product:
            return True
        skip_ids = set(x.id for x in self.productions_ignored)
        skip_ids.update(x.id for x in self.productions_recreated)
        quantity = self.quantity
        for production in self.productions:
            if production.state != 'done' \
                    and production.id not in skip_ids:
                done = False
                break
            quantity -= Uom.compute_qty(production.uom, production.quantity,
                self.unit)
        if done:
            if quantity > 0.0:
                done = False
        return done

    def get_production_exception(self, name):
        skip_ids = set(x.id for x in self.productions_ignored)
        skip_ids.update(x.id for x in self.productions_recreated)
        for production in self.productions:
            if production.state == 'cancel' \
                    and production.id not in skip_ids:
                return True
        return False

    def get_production(self):
        pool = Pool()
        Production = pool.get('production')
        Uom = pool.get('product.uom')

        if (self.type != 'line' or not self.product or self.quantity < 0.0 or
                not self.product.raw_product):
            return

        if self.sale.shipment_method == 'order':
            quantity = abs(self.quantity)
        else:
            quantity = 0.0
            for invoice_line in self.invoice_lines:
                if invoice_line.invoice.state == 'paid':
                    quantity += Uom.compute_qty(invoice_line.unit,
                        invoice_line.quantity, self.unit)

        skip_ids = set(x.id for x in self.productions_recreated)
        for production in self.productions:
            if production.id not in skip_ids:
                quantity -= Uom.compute_qty(production.uom,
                    production.quantity, self.unit)
        if quantity <= 0.0:
            return

        if not self.sale.warehouse.production_location:
            raise UserError(gettext(
                'sale_product_raw.production_location_required',
                    warehouse=self.sale.warehouse.rec_name,
                    sale=self.sale.rec_name,
                    ))

        inputs = self._get_production_inputs(quantity)
        outputs = self._get_production_outputs(quantity)

        if not inputs or not outputs:
            return

        with Transaction().set_user(0, set_context=True):
            production = Production()
        production.product = self.product
        production.uom = self.unit
        production.quantity = quantity
        production.warehouse = self.sale.warehouse
        production.location = self.sale.warehouse.production_location
        production.reference = self.rec_name
        production.company = self.sale.company
        production.inputs = inputs
        production.outputs = outputs
        production.notes = self.note
        production.state = 'draft'
        production.origin = self
        return production

    def _get_production_inputs(self, quantity):
        pool = Pool()
        Move = pool.get('stock.move')

        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product.raw_product
        move.from_location = self.warehouse.storage_location
        move.to_location = self.warehouse.production_location
        move.state = 'draft'
        move.company = self.sale.company
        move.currency = self.sale.currency
        return [move]

    def _get_production_outputs(self, quantity):
        pool = Pool()
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Template = pool.get('product.template')

        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.warehouse.production_location
        move.to_location = (getattr(self.warehouse,
                'production_output_location', None) or
            self.warehouse.storage_location)
        move.state = 'draft'
        move.company = self.sale.company
        move.currency = self.sale.currency

        cost = Decimal(str(quantity)) * self.product.cost_price
        if hasattr(Product, 'cost_price'):
            digits = Product.cost_price.digits
        else:
            digits = Template.cost_price.digits
        move.unit_price = Decimal(cost / Decimal(str(quantity))
            ).quantize(Decimal(str(10 ** -digits[1])))

        return [move]

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default['productions'] = None
        default['productions_ignored'] = None
        default['productions_recreated'] = None
        return super(SaleLine, cls).copy(lines, default=default)


class SaleLineIgnoredProduction(ModelSQL):
    'Sale Line - Ignored Production'
    __name__ = 'sale.line-ignored-production'
    _table = 'sale_line_productions_ignored_rel'
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
        select=True, required=True)
    production = fields.Many2One('production', 'Production',
        ondelete='RESTRICT', select=True, required=True)


class SaleLineRecreatedProduction(ModelSQL):
    'Sale Line - Recreated Production'
    __name__ = 'sale.line-recreated-production'
    _table = 'sale_line_productions_recreated_rel'
    sale_line = fields.Many2One('sale.line', 'Sale Line', ondelete='CASCADE',
        select=True, required=True)
    production = fields.Many2One('production', 'Production',
        ondelete='RESTRICT', select=True, required=True)


class HandleProductionExceptionAsk(ModelView):
    'Handle Production Exception'
    __name__ = 'sale.handle.production.exception.ask'
    recreate_productions = fields.Many2Many('production', None, None,
        'Recreate Productions', domain=[
            ('id', 'in', Eval('domain_productions')),
            ], depends=['domain_productions'])
    domain_productions = fields.Many2Many('production', None, None,
        'Domain Productions')


class HandleProductionException(Wizard):
    'Handle Production Exception'
    __name__ = 'sale.handle.production.exception'
    start_state = 'ask'
    ask = StateView('sale.handle.production.exception.ask',
        'sale_product_raw.handle_production_exception_ask_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Ok', 'handle', 'tryton-ok', default=True),
            ])
    handle = StateTransition()

    def default_ask(self, fields):
        Sale = Pool().get('sale.sale')
        sale = Sale(Transaction().context.get('active_id'))

        productions = []
        for line in sale.lines:
            skips = set(line.productions_ignored)
            skips.update(line.productions_recreated)
            for production in line.productions:
                if production.state == 'cancel' and production not in skips:
                    productions.append(production.id)
        return {
            'recreate_productions': productions,
            'domain_productions': productions,
            }

    def transition_handle(self):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        sale = Sale(Transaction().context['active_id'])

        for line in sale.lines:
            productions_ignored = []
            productions_recreated = []
            skips = set(line.productions_ignored)
            skips.update(line.productions_recreated)
            for production in line.productions:
                if (production not in self.ask.domain_productions or
                        production in skips):
                    continue
                if production in self.ask.recreate_productions:
                    productions_recreated.append(production.id)
                else:
                    productions_ignored.append(production.id)

            SaleLine.write([line], {
                    'productions_ignored': [('add', productions_ignored)],
                    'productions_recreated': [('add', productions_recreated)],
                    })
        Sale.process([sale])
        return 'end'
