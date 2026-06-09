# Copyright 2024 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)

from odoo.tests import Form

from odoo.addons.base.tests.common import BaseCommon


class TestStockException(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.StockPicking = cls.env["stock.picking"]
        cls.StockMove = cls.env["stock.move"]
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env.ref("product.product_product_4")
        cls.picking_type = cls.env.ref("stock.picking_type_out")
        cls.stock_exception_confirm = cls.env["stock.exception.confirm"]
        cls.exception_no_partner = cls.env.ref("stock_exception.sp_excep_no_partner")
        cls.exception_qty_check = cls.env.ref(
            "stock_exception.sm_excep_product_uom_qty_check"
        )
        cls.picking_vals = {
            "name": "Test Picking With Exceptions 2",
            "location_id": cls.stock_location.id,
            "location_dest_id": cls.customer_location.id,
            "picking_type_id": cls.picking_type.id,
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test Move",
                        "product_id": cls.product.id,
                        "product_uom_qty": 1.0,
                        "product_uom": cls.product.uom_id.id,
                        "location_id": cls.stock_location.id,
                        "location_dest_id": cls.customer_location.id,
                    },
                )
            ],
        }

    def test_stock_exception(self):
        self.exception_no_partner.active = True
        self.exception_qty_check.active = True
        # Test 1: Picking without partner (triggers sp_excep_no_partner)
        picking = self.StockPicking.create(self.picking_vals.copy())
        res = picking.action_confirm()
        self.assertEqual(res.get("res_model"), "stock.exception.confirm")
        self.assertEqual(picking.state, "draft")

        # Test all draft picking
        picking2 = self.StockPicking.create(self.picking_vals.copy())
        self.StockPicking.test_all_draft_pickings()
        self.assertEqual(picking2.state, "draft")

        # Set ignore_exception flag (Done after ignore is selected at wizard)
        picking.ignore_exception = True
        picking.action_confirm()
        # After confirm, it should be in 'confirmed' or 'assigned' state
        self.assertIn(picking.state, ["confirmed", "assigned"])

        # If we change move_ids, ignore_exception should become False
        with Form(picking) as picking_form:
            for i in range(len(picking_form.move_ids)):
                with picking_form.move_ids.edit(i) as line_form:
                    line_form.name = "Another Move"
                    line_form.product_id = self.product
                    line_form.product_uom_qty = 2
                    line_form.product_uom = self.product.uom_id
                    line_form.location_id = self.stock_location
                    line_form.location_dest_id = self.customer_location
            picking = picking_form.save()
        self.assertFalse(picking.ignore_exception)

        # Simulation of the opening of the wizard stock_exception_confirm and
        # set ignore_exception to True
        picking.button_validate()
        confirm_wizard = self.stock_exception_confirm.with_context(
            active_id=picking.id,
            active_ids=[picking.id],
            active_model=picking._name,
        ).create({"ignore": True})
        confirm_wizard.action_confirm()
        self.assertTrue(picking.ignore_exception)

    def test_exception_qty_check_blocking(self):
        # No allow ignoring exceptions if the "is_blocking" field is checked
        self.exception_qty_check.active = True
        self.exception_qty_check.is_blocking = True
        vals = self.picking_vals.copy()
        vals["move_ids"][0][2]["product_uom_qty"] = 0
        picking = self.StockPicking.create(vals)
        confirm_wizard = self.stock_exception_confirm.with_context(
            active_id=picking.id,
            active_ids=[picking.id],
            active_model=picking._name,
        ).create({"ignore": True})
        confirm_wizard.exception_ids = self.exception_qty_check
        # If it's blocking, action_confirm should probably raise or return something
        # in purchase it just calls action_confirm.
        # Let's see what it does in stock.
        confirm_wizard.action_confirm()
        self.assertTrue(picking.state == "draft")
