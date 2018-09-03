# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from sql import Asc
from sql.conditionals import Coalesce
from sql.operators import Exists

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['PurchaseRequest']


class PurchaseRequest(metaclass=PoolMeta):
    __name__ = 'purchase.request'

    @classmethod
    def generate_requests(cls, products=None, warehouses=None):
        """
        Never buy a main product.
        """
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        ProductRaw = pool.get('product.product-product.raw_product')

        if products is None:
            product = Product.__table__()
            template = Template.__table__()
            product_raw = ProductRaw.__table__()
            cursor = Transaction().connection.cursor()
            # Use query to speedup the process
            # fetch goods and assets not consumable and purchasable
            # skip main variants
            # ordered by ids to speedup reduce_ids in products_by_location
            cursor.execute(*product.join(template,
                    condition=((template.id == product.template) &
                        (template.type.in_(['goods', 'assets'])) &
                        template.purchasable &
                        ~Coalesce(template.consumable, False))).select(
                    product.id,
                    where=(product.active & ~Exists(product_raw.select(
                                product_raw.product,
                                where=(product_raw.product == product.id)))),
                    order_by=(Asc(product.id))))

            products = Product.browse([r[0] for r in cursor.fetchall()])
        else:
            products = [p for p in products if not p.raw_product]
        return super(PurchaseRequest, cls).generate_requests(products=products,
            warehouses=warehouses)
