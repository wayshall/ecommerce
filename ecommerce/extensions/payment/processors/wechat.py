""" PayPal payment processing. """
import json
import logging
import re
import uuid
from decimal import Decimal
from urllib.parse import urljoin

import paypalrestsdk
import waffle
from django.conf import settings
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import get_language
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.constants import PAYPAL_LOCALES
from ecommerce.extensions.payment.models import PaypalProcessorConfiguration, PaypalWebProfile
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.utils import get_basket_program_uuid, middle_truncate
# from .wechatpay_v3 import WeChatPayV3
# from .wechatpay_utils import *
from wechatpayv3 import WeChatPay, WeChatPayType

logger = logging.getLogger(__name__)


class WechatPay(BasePaymentProcessor):
    """
    """

    NAME = 'wechatpay'
    TITLE = 'WechatPay'
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self, site):
        """
        Constructs a new instance of the PayPal processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        super(WechatPay, self).__init__(site)

        # Number of times payment execution is retried after failure.
        self.retry_attempts = 3

    @cached_property
    def wechatpay_api(self):
        """
        """
        notify_url = urljoin(get_ecommerce_url(), 'wechat/notify')
        # wx_pay = WeChatPayV3(
        #     mchid=self.configuration['merchant_id'],
        #     appid=self.configuration['app_id'],
        #     v3key=self.configuration['v3_key'],
        #     apiclient_key=self.configuration['apiclient_key'], # 私钥证书路径
        #     serial_no=self.configuration['serial_no'], # 商户号证书序列号
        #     notify_url=notify_url,
        #     pay_type="h5"
        # )
        merchant_id = str(self.configuration['merchant_id'])
        cert_dir = self.configuration['cert_dir']
        apiclient_key_path = self.configuration['apiclient_key']
        # 商户证书私钥，此文件不要放置在下面设置的CERT_DIR目录里。
        PRIVATE_KEY = None
        with open(apiclient_key_path) as f:
            PRIVATE_KEY = f.read()
        wx_pay = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=merchant_id,
            private_key=PRIVATE_KEY, # 商户证书私钥
            cert_serial_no=self.configuration['serial_no'],
            apiv3_key=self.configuration['v3_key'],
            appid=self.configuration['app_id'],
            notify_url=notify_url,
            cert_dir=cert_dir,
            logger=logger,
            partner_mode=False, # 接入模式:False=直连商户模式，True=服务商模式
            timeout=(30, 60)
        )
        return wx_pay

    def get_payment_by_transaction_id(self, transaction_id):
        wxpay = self.wechatpay_api
        code, message = wxpay.query(transaction_id=transaction_id)
        if code != 200:
            return None
        payment = json.loads(message)
        return payment

    def get_payment_by_out_trade_no(self, out_trade_no):
        wxpay = self.wechatpay_api
        code, message = wxpay.query(out_trade_no=out_trade_no)
        if code != 200:
            return None
        payment = json.loads(message)
        return payment

    def get_payment(self, basket):
        order_number = basket.order_number
        return self.get_payment_by_out_trade_no(order_number)

    def get_trade_state(self, basket):
        payment = self.get_payment(basket)
        trade_state = payment["trade_state"]
        # return trade_state == "SUCCESS"
        return trade_state

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Create a new wechat payment.

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which is used to construct PayPal's `return_url`.
            use_client_side_checkout (bool, optional): This value is not used.
            **kwargs: Additional parameters; not used by this method.

        """
        # PayPal requires that item names be at most 127 characters long.
        PAY_FREE_FORM_FIELD_MAX_SIZE = 127

        available_attempts = 1
        if waffle.switch_is_active('WECHATPAY_RETRY_ATTEMPTS'):
            available_attempts = self.retry_attempts

        order_number = basket.order_number

        # 拼接商品描述
        desc_list = [self.get_courseid_title(line) for line in basket.all_lines()]
        desc = ",".join(d for d in desc_list)
        desc = middle_truncate(desc, PAY_FREE_FORM_FIELD_MAX_SIZE)
        usd_rmb_exchage_rate = request.site.siteconfiguration.usd_rmb_exchage_rate
        usd_rmb_exchage_rate = int(usd_rmb_exchage_rate * 10000) # 汇率一般4位小数
        price = int(basket.total_incl_tax * 100) # 美元保留两位小数
        total = int(price * usd_rmb_exchage_rate * 100 / 10000 / 100) # 商品原单位是美元，微信支付单位是人民币：分
        logger.info('WechatPay price: %s, usd_rmb_exchage_rate: %s, total: %s', price, usd_rmb_exchage_rate, total)

        site_configuration = basket.site.siteconfiguration
        notify_url = site_configuration.build_ecommerce_url('/payment/wechatpay/query')
        # notify_url = 'http://gptdev.nps.wayfish.cn/payment/wechatpay/query/'

        message = None
        for i in range(1, available_attempts + 1):
            try:
                wx_pay = self.wechatpay_api
                code, message = wx_pay.pay(
                    out_trade_no=order_number,
                    amount={'total': total},
                    description=desc,
                    pay_type=WeChatPayType.NATIVE,
                    notify_url=notify_url
                )
                logger.info("Wechat payment result, code: %s, message: %s", code, message)
                if code == 200:
                    break
                if i < available_attempts:
                    logger.warning(
                        u"Creating WechatPay payment for basket [%d] was unsuccessful. Will retry.",
                        basket.id,
                        exc_info=True
                    )
                else:
                    error = message
                    # pylint: disable=unsubscriptable-object
                    entry = self.record_processor_response(
                        error,
                        transaction_id=order_number, #error['debug_id'],
                        basket=basket
                    )
                    logger.error(
                        u"%s [%d], %s [%d].",
                        "Failed to create WechatPay payment for basket",
                        basket.id,
                        "WechatPay's response recorded in entry",
                        entry.id,
                        exc_info=True
                    )
                    raise GatewayError(error)

            except:  # pylint: disable=bare-except
                if i < available_attempts:
                    logger.warning(
                        u"Creating WechatPay payment for basket [%d] resulted in an exception. Will retry.",
                        basket.id,
                        exc_info=True
                    )
                else:
                    logger.exception(
                        u"After %d retries, creating WechatPay payment for basket [%d] still experienced exception.",
                        i,
                        basket.id
                    )
                    raise

        message = json.loads(message)
        # 成功创建后立即查询
        payment = self.get_payment(basket)
        # entry = self.record_processor_response(payment, transaction_id=payment.transaction_id, basket=basket)
        entry = self.record_processor_response(payment, transaction_id=payment['out_trade_no'], basket=basket)
        logger.info("Successfully created WechatPay payment [%s] for basket [%d].", order_number, basket.id)

        parameters = {
            'payment_page_url': message['code_url'],
            'out_trade_no': payment['out_trade_no']
        }

        return parameters

    def get_courseid_title(self, line):
        """
        Get CourseID & Title from basket item

        Arguments:
            line: basket item

        Returns:
             Concatenated string containing course id & title if exists.
        """
        courseid = ''
        line_course = line.product.course
        if line_course:
            courseid = "{}|".format(line_course.id)
        return courseid + line.product.title

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        try:
            # reference_number 为支付交易id，对应payment_source.reference字段
            wx_pay = self.wechatpay_api
            payment = wx_pay.query(out_trade_no=reference_number, mchid=self.configuration['merchant_id'])
            if not payment:
                logger.error('Unable to find a Sale associated with wechat pay order [%s].', reference_number)
            out_refund_no = payment.out_trade_no
            amount = payment.amount.payer_total
            refund = wx_pay.refund(out_refund_no=out_refund_no, amount=amount)
            logger.info('issued a refund for order [%s].', refund)
        except:
            msg = 'An error occurred while attempting to issue a credit (via PayPal) for order [{}].'.format(
                order_number)
            logger.exception(msg)
            raise GatewayError(msg)  # pylint: disable=raise-missing-from

        if refund.success():
            transaction_id = refund.refund_id
            self.record_processor_response(refund.to_dict(), transaction_id=transaction_id, basket=basket)
            return transaction_id

        error = refund.error
        entry = self.record_processor_response(error, transaction_id=reference_number, basket=basket)

        msg = "Failed to refund WechatPay payment [{sale_id}]. " \
              "WechatPay's response was recorded in entry [{response_id}].".format(sale_id=reference_number,
                                                                                response_id=entry.id)
        raise GatewayError(msg)

    def handle_processor_response(self, response, basket=None):
        logger.info('wechat resposne: %s', response)
        logger.info('wechat basket: %s', basket)
        payment = self.get_payment(basket)
        transaction_id = payment['transaction_id'] if 'transaction_id' in payment else payment['out_trade_no']
        # self.record_processor_response(payment.to_dict(), transaction_id=payment.id, basket=basket)
        self.record_processor_response(payment, transaction_id=transaction_id, basket=basket)
        logger.info("Successfully executed PayPal payment [%s] for basket [%d].", transaction_id, basket.id)

        currency = payment['amount']['currency']
        total = Decimal(payment['amount']['total'])

        label = 'WechatPay Account'
        if 'payer' in payment and 'openid' in payment['payer']:
            openid = payment['payer']['openid']
            label = 'WechatPay Account ({})'.format(openid)

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=label,
            card_type=None
        )
