
import logging
from django.conf import settings

from django.core.exceptions import MultipleObjectsReturned
from django.http import HttpResponseServerError
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from rest_framework.views import APIView
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.generic import View
from oscar.apps.partner import strategy
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

    def post(self, request):
        data = request.body
        logger.info("wechatpay callback header: %s", request.headers)
        logger.info("wechatpay callback data: %s", data)
        result = self.payment_processor.wechatpay_api.callback(request.headers, data)
        if result and result.get('event_type') == 'TRANSACTION.SUCCESS':
            resp = result.get('resource')
            transaction_id = resp.get('transaction_id')
            trade_state = resp.get('trade_state')
            out_trade_no = resp.get('out_trade_no')
            self.handle_pay_success(request, data, transaction_id, out_trade_no, trade_state)
            res = {
                'code': 'SUCCESS',
                'message': '成功'
            }
            return JsonResponse(res)
        else:
            res = {
                'code': 'FAILED',
                'message': '失败'
            }
            response = HttpResponseServerError(JsonResponse(res))
            response['Content-Type'] = 'application/json'
            return response

    def get(self, request):
        responses = request.GET
        basket_id = request.GET.get('basket_id')
        out_trade_no = request.GET.get('out_trade_no')
        payment = self.payment_processor.get_payment_by_out_trade_no(out_trade_no)

        trade_state = payment["trade_state"]
        receipt_url = ''
        res = {
            'trade_state': trade_state,
            'redirect_url': receipt_url
        }

        if trade_state == 'SUCCESS':
            transaction_id = payment["transaction_id"]
            res = self.handle_pay_success(request, responses, transaction_id, out_trade_no, trade_state)

            # 下面代码用于测试
            # paymentRes, basket = self._get_basket(None, transaction_id)
            # if basket is not None:
            #     res = {
            #         'trade_state': trade_state,
            #         'redirect_url': receipt_url
            #     }
            # else:
            #     res = {
            #         'trade_state': 'NOTPAY',
            #         'redirect_url': receipt_url
            #     }
        return JsonResponse(res)

    def handle_pay_success(self, request, responses, transaction_id, out_trade_no, trade_state):
        process_result = True
        has_paid = False
        with transaction.atomic():
            paymentRes, basket = self._get_basket(None, transaction_id, True)
            if basket is None:
                paymentRes, basket = self._get_basket(out_trade_no, None, True)
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
                self.handle_payment(responses, basket)
            except:  # pylint: disable=bare-except
                logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
                # trade_state = 'ERROR'
                process_result = False

            order = None
            try:
                order = self.create_order(request, basket)
            except Exception:  # pylint: disable=broad-except
                logger.exception('Attempts to create order for basket [%d] failed.', basket.id)
                # trade_state = 'ERROR'
                process_result = False

            try:
                if order is not None:
                    self.handle_post_order(order)
            except Exception:  # pylint: disable=broad-except
                self.log_order_placement_exception(basket.order_number, basket.id)
                process_result = False

        res = {
            'trade_state': trade_state,
            'redirect_url': receipt_url,
            'process_result': process_result
        }
        return res

    def _get_basket(self, out_trade_no, transaction_id, for_update=False):
        """
        Retrieve a basket using a payment ID.

        Arguments:
            payment_id: payment_id received from PayPal.

        Returns:
            It will return related basket or log exception and return None if
            duplicate payment_id received or any other exception occurred.

        """
        try:
            payObj = PaymentProcessorResponse.objects
            if for_update:
                payObj = payObj.select_for_update()
            if transaction_id is not None:
                paymentRes = payObj.get(
                    processor_name=self.payment_processor.NAME,
                    transaction_id=transaction_id
                )
            elif out_trade_no is not None:
                paymentRes = payObj.get(
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