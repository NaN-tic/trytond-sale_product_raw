# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import sale
from . import production
from . import purchase_request

def register():
    Pool.register(
        production.Production,
        sale.Sale,
        sale.SaleLine,
        sale.SaleLineIgnoredProduction,
        sale.SaleLineRecreatedProduction,
        sale.HandleProductionExceptionAsk,
        module='sale_product_raw', type_='model')
    Pool.register(
        purchase_request.PurchaseRequest,
        depends=['stock_supply'],
        module='sale_product_raw', type_='model')
    Pool.register(
        sale.HandleProductionException,
        module='sale_product_raw', type_='wizard')
