

import logging

import mock
import stripe
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.tests.testcases import TestCase
from ecommerce.core.models import BusinessClient
from ecommerce.extensions.basket.constants import PAYMENT_INTENT_ID_ATTRIBUTE
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.processors.webhooks import WebhooksPayment
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.extensions.test.factories import create_basket, create_order

log = logging.getLogger(__name__)

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')


class WebhooksPaymentTests(PaymentProcessorTestCaseMixin, TestCase):
    """ Tests WebhooksPayments """
    processor_class = WebhooksPayment
    processor_name = 'stripe_webhooks'

    def setUp(self):
        super(WebhooksPaymentTests, self).setUp()
        self.site.siteconfiguration.client_side_payment_processor = 'stripe'
        self.site.siteconfiguration.save()
        self.payment_intent = {
            "id": "pi_3OzUOMH4caH7G0X114tkIL0X",
            "object": "payment_intent",
            "status": "succeeded",
            "amount": 14900,
            "amount_capturable": 0,
            "amount_details": {
                "tip": {
                }
            },
            "amount_received": 14900,
            "automatic_payment_methods": {
                "allow_redirects": "always",
            },
            "capture_method": "automatic",
            "charges": {
                "object": "list",
                "data": [
                {
                    "id": "py_3OzUOMH4caH7G0X11OOKbfIk",
                    "object": "charge",
                    "amount": 14900,
                    "amount_captured": 14900,
                    "amount_refunded": 0,
                    "balance_transaction": "txn_3OzUOMH4caH7G0X11flKf5U4",
                    "billing_details": {
                    "address": {
                        "city": "Beverly Hills",
                        "country": "US",
                        "line1": "Amsterdam Ave",
                        "line2": "Apt 214",
                        "postal_code": "10024",
                        "state": "NY"
                    },
                    "email": "customer@email.us",
                    "name": "Test Person-us",
                    },
                    "created": 1711676524,
                    "currency": "usd",
                    "description": "EDX-100001",
                    "fraud_details": {
                    },
                    "metadata": {
                    "courses": "[{'course_id': 'course-v1:edX+DemoX+Demo_Course', 'course_name': 'edX Demonstration Course'}]",
                    "order_number": "EDX-100001"
                    },
                    "outcome": {
                    "network_status": "approved_by_network",
                    "risk_level": "not_assessed",
                    "seller_message": "Payment complete.",
                    "type": "authorized"
                    },
                    "payment_intent": "pi_3OzUOMH4caH7G0X114tkIL0X",
                    "payment_method": "pm_1OzURzH4caH7G0X19vH5rGBT",
                    "payment_method_details": {
                    "afterpay_clearpay": {
                        "order_id": "JCkYW6Afa0hELU0p1Urf",
                    },
                    "type": "afterpay_clearpay"
                    },
                    "radar_options": {
                    },
                    "receipt_url": "https://pay.stripe.com/receipts/payment/CAcaFwoVYWNjdF8xTHM3UVNINGNhSDdHMFgxKOy4mLAGMgYXtd9MJi06LBZw14jVkz0vKozsqk2_q6lLrskTm5gm4anP-pVGppcQYWwfthMZIPXhKyn5",
                    "shipping": {
                    "address": {
                        "city": "Beverly Hills",
                        "country": "US",
                        "line1": "Amsterdam Ave",
                        "line2": "Apt 214",
                        "postal_code": "10024",
                        "state": "NY"
                    },
                    "name": "Test Person-us",
                    },
                    "status": "succeeded",
                }
                ],
                "total_count": 2,
                "url": "/v1/charges?payment_intent=pi_3OzUOMH4caH7G0X114tkIL0X"
            },
            "client_secret": "pi_3OzUOMH4caH7G0X114tkIL0X_secret_SYz2fcAkT2hIWhpdRTqUwRFHF",
            "confirmation_method": "automatic",
            "created": 1711676282,
            "currency": "usd",
            "description": "EDX-100001",
            "latest_charge": "py_3OzUOMH4caH7G0X11OOKbfIk",
            "metadata": {
                "courses": "[{'course_id': 'course-v1:edX+DemoX+Demo_Course', 'course_name': 'edX Demonstration Course'}]",
                "order_number": "EDX-100001"
            },
            "payment_method": "pm_1OzURzH4caH7G0X19vH5rGBT",
            "payment_method_configuration_details": {
                "id": "pmc_1LspDWH4caH7G0X1LXrN8QMJ",
            },
            "payment_method_options": {
                "affirm": {
                    "preferred_locale": "en"
                },
                "afterpay_clearpay": {
                    "preferred_locale": "en"
                },
                "card": {
                    "request_three_d_secure": "automatic"
                },
                "klarna": {
                    "preferred_locale": "en"
                }
            },
            "payment_method_types": [
                "card",
                "afterpay_clearpay",
                "klarna",
                "affirm"
            ],
            "secret_key_confirmation": "required",
            "shipping": {
                "address": {
                "city": "Beverly Hills",
                "country": "US",
                "line1": "Amsterdam Ave",
                "line2": "Apt 214",
                "postal_code": "10024",
                "state": "NY"
                },
                "name": "Test Person-us",
            },
        }
        self.basket = create_basket(owner=self.create_user(), site=self.site, price='149.0')
        basket_attribute_type, _ = BasketAttributeType.objects.get_or_create(name=PAYMENT_INTENT_ID_ATTRIBUTE)
        basket_attribute_type.save()
        BasketAttribute.objects.get_or_create(
            basket=self.basket,
            attribute_type=basket_attribute_type,
            value_text=self.payment_intent['id'],
        )
    
    def test_configuration(self):  # pylint: disable=arguments-differ
        """
        Tests configuration.
        """
        self.skipTest('WebhooksPayments processor does not currently require configuration.')

    def test_name(self):
        """
        Test that the name constant on the processor class is correct.
        """
        self.assertEqual(self.processor.NAME, self.processor_name)

    def test_handle_processor_response(self):
        """
        Tests handle_processor_response.
        """
        self.skipTest('WebhooksPayments processor does not currently implement handle_processor_response.')

    def test_get_transaction_parameters(self):
        """
        Tests transaction parameters.
        """
        self.skipTest('WebhooksPayments processor does not currently implement get_transaction_parameters.')

    def test_issue_credit(self):
        """
        Test issue credit.
        """
        self.assertRaises(NotImplementedError, self.processor_class(self.site).issue_credit, None, None, None, 0, 'USD')

    def test_issue_credit_error(self):
        """
        Tests that Webhooks payments processor does not support issuing credit.
        """
        self.skipTest('Webhooks payments processor does not yet support issuing credit.')

    def test_handle_webhooks_payment(self):
        """
        Verify a payment received via Stripe webhooks is processed, an order is created and fulfilled.
        """
        with mock.patch('ecommerce.extensions.basket.models.track_segment_event') as mock_track:
            self.processor_class(self.site).handle_webhooks_payment(self.payment_intent)
            properties = {
                'basket_id': self.basket.id,
                'processor_name': 'stripe',
                'stripe_enabled': True,
                'total': self.basket.total_incl_tax,
                'success': True,
            }
            mock_track.assert_called_once_with(self.basket.site, self.basket.owner, 'Payment Processor Response', properties)
