
import logging
import os
from io import StringIO

from django.core.exceptions import MultipleObjectsReturned
from django.core.management import call_command
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from rest_framework.views import APIView
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.processors.wechat import WechatPay
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse


logger = logging.getLogger(__name__)
Applicator = get_class('offer.applicator', 'Applicator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

class WechatPaymentQueryView(EdxOrderPlacementMixin, APIView):

    @property
    def payment_processor(self):
        return WechatPay(self.request.site)
    def get(self, request):
        responses = request.GET
        basket_id = request.GET.get('basket_id')
        out_trade_no = request.GET.get('out_trade_no')
        payment = self.payment_processor.get_payment_by_out_trade_no(out_trade_no)

        trade_state = payment["trade_state"]
        receipt_url = ''
        has_paid = False

        if trade_state == 'SUCCESS':
            transaction_id = payment["transaction_id"]
            paymentRes, basket = self._get_basket(None, transaction_id)
            if basket is None:
                paymentRes, basket = self._get_basket(out_trade_no, None)
            else:
                has_paid = True
            receipt_url = get_receipt_page_url(
                self.request,
                order_number=basket.order_number,
                site_configuration=basket.site.siteconfiguration,
                disable_back_button=True
            )

            if has_paid:
                return {
                    'trade_state': trade_state,
                    'redirect_url': receipt_url
                }
            try:
                with transaction.atomic():
                    self.handle_payment(responses, basket)
            except:  # pylint: disable=bare-except
                logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
                # trade_state = 'ERROR'

            order = None
            try:
                order = self.create_order(request, basket)
            except Exception:  # pylint: disable=broad-except
                logger.exception('Attempts to create order for basket [%d] failed.', basket.id)
                # trade_state = 'ERROR'

            try:
                if order is not None:
                    self.handle_post_order(order)
            except Exception:  # pylint: disable=broad-except
                self.log_order_placement_exception(basket.order_number, basket.id)

        res = {
            'trade_state': trade_state,
            'redirect_url': receipt_url
        }
        return JsonResponse(res)

    def _get_basket(self, out_trade_no, transaction_id):
        """
        Retrieve a basket using a payment ID.

        Arguments:
            payment_id: payment_id received from PayPal.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_id received or any other exception occurred.

        """
        try:
            if transaction_id is not None:
                paymentRes = PaymentProcessorResponse.objects.get(
                    processor_name=self.payment_processor.NAME,
                    transaction_id=transaction_id
                )
            elif out_trade_no is not None:
                paymentRes = PaymentProcessorResponse.objects.get(
                    processor_name=self.payment_processor.NAME,
                    transaction_id=out_trade_no
                )
            else:
                return None, None
            basket = paymentRes.basket
            basket.strategy = strategy.Default()

            Applicator().apply(basket, basket.owner, self.request)

            basket_add_organization_attribute(basket, self.request.GET)
            return paymentRes, basket
        except MultipleObjectsReturned:
            logger.warning(u"Duplicate payment ID [%s] received from PayPal.", transaction_id)
            return None, None
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(u"Unexpected error during basket retrieval while executing PayPal payment. %s", e)
            return None, None