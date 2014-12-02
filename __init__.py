# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .sale import *
from .production import *
from .purchase_request import *


def register():
    Pool.register(
        Production,
        PurchaseRequest,
        Sale,
        SaleLine,
        SaleLineIgnoredProduction,
        SaleLineRecreatedProduction,
        HandleProductionExceptionAsk,
        module='sale_product_raw', type_='model')
    Pool.register(
        HandleProductionException,
        module='sale', type_='wizard')
