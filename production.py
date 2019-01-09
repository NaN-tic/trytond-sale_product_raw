# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from functools import wraps

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError

__all__ = ['Production']


def process_sale(func):
    @wraps(func)
    def wrapper(cls, productions):
        pool = Pool()
        Sale = pool.get('sale.sale')
        with Transaction().set_user(0, set_context=True):
            sales = [p.sale for p in cls.browse(productions) if p.sale]
        func(cls, productions)
        with Transaction().set_user(0, set_context=True):
            Sale.process(sales)
    return wrapper


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    sale_exception_state = fields.Function(fields.Selection([
                ('', ''),
                ('ignored', 'Ignored'),
                ('recreated', 'Recreated'),
                ], 'Exception State'),
        'get_sale_exception_state')
    sale = fields.Function(fields.Many2One('sale.sale', 'Sale'),
        'get_sale', searcher='search_sale')

    @classmethod
    def _get_origin(cls):
        origins = super(Production, cls)._get_origin()
        if 'sale.line' not in origins:
            origins.append('sale.line')
        return origins

    def get_sale_exception_state(self, name):
        SaleLine = Pool().get('sale.line')
        if not isinstance(self.origin, SaleLine):
            return ''
        if self in self.origin.productions_recreated:
            return 'recreated'
        if self in self.origin.productions_ignored:
            return 'ignored'
        return ''

    @property
    def started(self):
        return self.state == 'running'

    def get_sale(self, name):
        SaleLine = Pool().get('sale.line')
        if isinstance(self.origin, SaleLine):
            return self.origin.sale.id

    @classmethod
    def search_sale(cls, name, clause):
        return [('origin.sale.id',) + tuple(clause[1:]) + ('sale.line',)]

    @classmethod
    @process_sale
    def cancel(cls, productions):
        super(Production, cls).cancel(productions)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        SaleLine = Pool().get('sale.line')
        for production in productions:
            if (production.state == 'cancel'
                    and production.sale):
                raise UserError(gettext(
                    'sale_product_raw.reset_production'))
        return super(Production, cls).draft(productions)

    @classmethod
    @process_sale
    def wait(cls, productions):
        super(Production, cls).wait(productions)

    @classmethod
    @process_sale
    def assign(cls, productions):
        super(Production, cls).assign(productions)

    @classmethod
    @process_sale
    def run(cls, productions):
        super(Production, cls).run(productions)

    @classmethod
    @process_sale
    def done(cls, productions):
        super(Production, cls).done(productions)

    @classmethod
    @process_sale
    def delete(cls, productions):
        super(Production, cls).delete(productions)
