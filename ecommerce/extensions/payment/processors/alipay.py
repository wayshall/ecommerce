""" PayPal payment processing. """
import json
import logging
import re
import uuid
from decimal import Decimal
from urllib.parse import urljoin

import waffle
from django.utils.functional import cached_property
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.utils import get_basket_program_uuid, middle_truncate
from alipay import AliPay, DCAliPay, ISVAliPay
from alipay.utils import AliPayConfig

logger = logging.getLogger(__name__)


class AliPayProcessor(BasePaymentProcessor):
    """
    """

    NAME = 'alipay'
    TITLE = 'AliPay'
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self, site):
        """
        Constructs a new instance of the PayPal processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        super(AliPayProcessor, self).__init__(site)

        # Number of times payment execution is retried after failure.
        self.retry_attempts = 3

    def wrap_private_key(self, key):
        txt = """-----BEGIN RSA PRIVATE KEY-----\n{}\n-----END RSA PRIVATE KEY-----""".format(key)
        return txt

    def wrap_public_key(self, key):
        txt = """-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----""".format(key)
        return txt

    @cached_property
    def alipay_api(self):
        """
        """
        notify_url = urljoin(get_ecommerce_url(), '/payment/alipay/query/')
        app_id = self.configuration['app_id']
        # 支付宝网页下载的证书不能直接被使用，需要加上头尾
        # 你可以在此处找到例子： tests/certs/ali/ali_private_key.pem
        # app_private_key_path = self.configuration['app_private_key']
        # ali_public_key_path = self.configuration['ali_public_key']
        # with open(app_private_key_path) as f:
        #     app_private_key_string = f.read()
        # with open(ali_public_key_path) as f:
        #     alipay_public_key_string = f.read()
        app_private_key_string = self.wrap_private_key(self.configuration['app_private_key'])
        alipay_public_key_string = self.wrap_public_key(self.configuration['ali_public_key'])
        debug = self.configuration['debug'] if 'debug' in self.configuration else False
        verbose = self.configuration['verbose'] if 'verbose' in self.configuration else False
        sign_type = self.configuration['sign_type'] if 'sign_type' in self.configuration else 'RSA2'

        alipay = AliPay(
            appid=app_id,
            app_notify_url=notify_url,  # 默认回调 url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type=sign_type,  # RSA 或者 RSA2
            debug=debug,  # 默认 False
            verbose=verbose,  # 输出调试数据
            config=AliPayConfig(timeout=30)  # 可选，请求超时时间
        )
        return alipay

    def get_payment_by_transaction_id(self, transaction_id):
        alipay = self.alipay_api
        code, message = alipay.api_alipay_trade_query(trade_no=transaction_id)
        if code != 200:
            return None
        payment = json.loads(message)
        return payment

    def get_payment_by_out_trade_no(self, out_trade_no):
        alipay = self.alipay_api
        payment = alipay.api_alipay_trade_query(out_trade_no=out_trade_no)
        return payment

    def get_payment(self, basket):
        order_number = basket.order_number
        return self.get_payment_by_out_trade_no(order_number)

    def get_trade_state(self, basket):
        payment = self.get_payment(basket)
        trade_state = payment["trade_status"]
        # return trade_state == "SUCCESS"
        return trade_state

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Create a new Ali payment.

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which is used to construct PayPal's `return_url`.
            use_client_side_checkout (bool, optional): This value is not used.
            **kwargs: Additional parameters; not used by this method.

        """
        # PayPal requires that item names be at most 127 characters long.
        PAY_FREE_FORM_FIELD_MAX_SIZE = 127

        available_attempts = 1
        if waffle.switch_is_active('AliPAY_RETRY_ATTEMPTS'):
            available_attempts = self.retry_attempts

        order_number = basket.order_number

        # 拼接商品描述
        desc_list = [self.get_courseid_title(line) for line in basket.all_lines()]
        desc = ",".join(d for d in desc_list)
        desc = middle_truncate(desc, PAY_FREE_FORM_FIELD_MAX_SIZE)
        usd_rmb_exchage_rate = request.site.siteconfiguration.usd_rmb_exchage_rate
        usd_rmb_exchage_rate = int(usd_rmb_exchage_rate * 10000) # 汇率一般4位小数
        price = int(basket.total_incl_tax * 100) # 美元保留两位小数
        total = float(price * usd_rmb_exchage_rate / 10000 / 100) # 商品原单位是美元，支付单位是人民币：元
        total = round(total, 2) # 四舍五入，保留两位小数
        logger.info('AliPay price: %s, usd_rmb_exchage_rate: %s, total: %s', price, usd_rmb_exchage_rate, total)

        site_configuration = basket.site.siteconfiguration
        notify_url = site_configuration.build_ecommerce_url('/payment/alipay/query/')
        notify_url = 'http://gptdev.nps.wayfish.cn/payment/alipay/query/'

        alipay = self.alipay_api
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_number,
            total_amount=total,
            subject=desc,
            return_url=notify_url,
            notify_url=notify_url
        )
        logger.info("Ali payment result: %s", order_string)

        # 成功创建后立即查询
        payment = {
            "order_string": order_string
        }
        # entry = self.record_processor_response(payment, transaction_id=payment.transaction_id, basket=basket)
        # entry = self.record_processor_response(payment, transaction_id=payment['out_trade_no'], basket=basket)
        entry = self.record_processor_response(payment, transaction_id=order_number, basket=basket)
        logger.info("Successfully created AliPay payment [%s] for basket [%d].", order_number, basket.id)

        parameters = {
            'payment_page_url': 'https://openapi.alipay.com/gateway.do?' + order_string,
            'out_trade_no': order_number
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
            alipay = self.alipay_api
            payment = alipay.api_alipay_trade_query(out_trade_no=reference_number)
            if not payment:
                logger.error('Unable to find a Sale associated with Ali pay order [%s].', reference_number)
            # out_refund_no = payment.out_trade_no
            trade_no = payment.trade_no
            amount = payment.amount.payer_total
            refund = alipay.api_alipay_trade_refund(trade_no=trade_no, refund_amount=amount)
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

        msg = "Failed to refund AliPay payment [{sale_id}]. " \
              "AliPay's response was recorded in entry [{response_id}].".format(sale_id=reference_number,
                                                                                response_id=entry.id)
        raise GatewayError(msg)

    def handle_processor_response(self, response, basket=None):
        logger.info('Ali resposne: %s', response)
        logger.info('Ali basket: %s', basket)
        payment = self.get_payment(basket)
        transaction_id = payment['trade_no'] if 'trade_no' in payment else payment['out_trade_no']
        # self.record_processor_response(payment.to_dict(), transaction_id=payment.id, basket=basket)
        self.record_processor_response(payment, transaction_id=transaction_id, basket=basket)
        logger.info("Successfully executed PayPal payment [%s] for basket [%d].", transaction_id, basket.id)

        currency = 'CNY'
        total = Decimal(payment['total_amount'])

        label = 'AliPay Account'
        if 'buyer_open_id' in payment:
            openid = payment['buyer_open_id']
            label = 'AliPay Account ({})'.format(openid)

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=label,
            card_type=None
        )
