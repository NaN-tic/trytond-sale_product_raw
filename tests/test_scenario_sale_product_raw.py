import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install account_invoice
        config = activate_modules('sale_product_raw')

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        config._context = User.get_preferences(True, config.context)

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create parties
        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        # Create category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name='Category')
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.salable = True
        template.producible = True
        template.list_price = Decimal('10')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.has_raw_products = True
        template.save()
        product.template = template
        product.save()
        template.reload()
        self.assertEqual(product, template.main_products[0])

        raw_product, = template.raw_products
        self.assertEqual(raw_product.main_product, product)

        service = Product()
        template = ProductTemplate()
        template.name = 'service'
        template.default_uom = unit
        template.type = 'service'
        template.salable = True
        template.list_price = Decimal('30')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        template.save()
        service.template = template
        service.save()

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Sale services
        Sale = Model.get('sale.sale')
        service_sale = Sale()
        service_sale.party = customer
        service_sale.payment_term = payment_term
        sale_line = service_sale.lines.new()
        sale_line.product = service
        sale_line.quantity = 1
        service_sale.save()
        service_sale.click('quote')
        service_sale.click('confirm')
        service_sale.click('process')
        self.assertEqual(service_sale.state, 'processing')
        self.assertEqual(service_sale.productions, [])

        # Sale 5 products
        SaleLine = Model.get('sale.line')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.invoice_method = 'order'
        sale_line = SaleLine()
        sale.lines.append(sale_line)
        sale_line.product = product
        sale_line.quantity = 5.0
        sale.save()
        sale.click('quote')
        sale.click('confirm')
        sale.click('process')
        self.assertEqual(sale.state, 'processing')

        sale.reload()
        self.assertEqual(len(sale.shipments), 1)
        self.assertEqual(len(sale.shipment_returns), 0)
        self.assertEqual(len(sale.productions), 1)

        production, = sale.productions
        self.assertEqual(production.state, 'draft')

        input, = production.inputs
        self.assertEqual(input.product, raw_product)

        production, = sale.productions
        output, = production.outputs
        self.assertEqual(output.product, product)
