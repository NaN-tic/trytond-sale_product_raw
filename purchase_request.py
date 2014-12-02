# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

__all__ = ['PurchaseRequest']
__metaclass__ = PoolMeta


class PurchaseRequest:
    __name__ = 'purchase.request'

    @classmethod
    def generate_requests(cls, products=None, warehouses=None):
        """
        Never buy a main product.
        """
        Product = Pool().get('product.product')

        if products is None:
            # fetch goods and assets
            # ordered by ids to speedup reduce_ids in products_by_location
            products = Product.search([
                    ('type', 'in', ['goods', 'assets']),
                    ('consumable', '=', False),
                    ('purchasable', '=', True),
                    ('raw_product', '=', None),
                    ], order=[('id', 'ASC')])
        else:
            products = [p for p in products if not p.raw_product]
        return super(PurchaseRequest, cls).generate_requests(products=products,
            warehouses=warehouses)
