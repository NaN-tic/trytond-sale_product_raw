
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.tests.test_tryton import ModuleTestCase


class SaleProductRawTestCase(CompanyTestMixin, ModuleTestCase):
    'Test SaleProductRaw module'
    module = 'sale_product_raw'
    extras = ['purchase', 'sale_pos', 'stock_supply', 'production_output_location']


del ModuleTestCase
