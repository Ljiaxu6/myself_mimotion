# -*- coding: utf8 -*-
import uuid
from typing import Tuple, Optional, Dict, List
import json
import re
import time
import traceback
import urllib
import uuid
from datetime import datetime
import os
from pathlib import Path
import base64
from random import randint
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import pytz
import requests
from loguru import logger

# ase 解密
class aes_help:

    def __init__(self):

        # 华米传输加密使用的密钥 固定iv
        # 参考自 https://github.com/hanximeng/Zepp_API/blob/main/index.php
        self.HM_AES_KEY = b'xeNtBVqzDc6tuNTh'  # 16 bytes
        self.HM_AES_IV = b'MAAAYAAAAAAAAABg'  # 16 bytes

        self.AES_BLOCK_SIZE = AES.block_size  # 16


    def _pkcs7_pad(self, data: bytes) -> bytes:
        pad_len = self.AES_BLOCK_SIZE - (len(data) % self.AES_BLOCK_SIZE)
        return data + bytes([pad_len]) * pad_len


    def _pkcs7_unpad(self, data: bytes) -> bytes:
        if not data or len(data) % self.AES_BLOCK_SIZE != 0:
            raise ValueError(f"invalid padded data length {len(data)}")
        pad_len = data[-1]
        if pad_len < 1 or pad_len > self.AES_BLOCK_SIZE:
            raise ValueError(f"invalid padding length: {pad_len}")
        if data[-pad_len:] != bytes([pad_len]) * pad_len:
            raise ValueError("invalid PKCS#7 padding")
        return data[:-pad_len]


    def _validate_key(self, key: bytes):
        if not isinstance(key, (bytes, bytearray)):
            raise TypeError("key must be bytes")
        if len(key) != 16:
            raise ValueError("key must be 16 bytes for AES-128")


    def encrypt_data(self, plain: bytes, key: bytes, iv: bytes | None = None) -> bytes:
        """
        返回：IV（16B） + ciphertext（bytes） 或者仅ciphertext（当使用固定IV时）
        参数：
        - plain: 明文字节
        - key: 16 字节 AES-128 密钥
        - iv: IV向量，如果为None则生成随机IV
        """
        self._validate_key(key)
        if not isinstance(plain, (bytes, bytearray)):
            raise TypeError("plain must be bytes")

        if iv is None:
            # 使用随机IV
            iv = get_random_bytes(self.AES_BLOCK_SIZE)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded = self._pkcs7_pad(plain)
            ciphertext = cipher.encrypt(padded)
            return iv + ciphertext
        else:
            # 使用固定IV
            if len(iv) != self.AES_BLOCK_SIZE:
                raise ValueError(f"IV must be {self.AES_BLOCK_SIZE} bytes")
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded = self._pkcs7_pad(plain)
            ciphertext = cipher.encrypt(padded)
            return ciphertext


    def decrypt_data(self,data: bytes, key: bytes, iv: bytes | None = None) -> bytes:
        """
        输入：IV（16B） + ciphertext 或者仅ciphertext（当使用固定IV时）
        返回：明文字节（未解码为字符串）
        """
        self._validate_key(key)
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes")

        if iv is None:
            # 从数据中提取IV（假设前16字节是IV）
            if len(data) < self.AES_BLOCK_SIZE:
                raise ValueError("data too short")

            iv = data[:self.AES_BLOCK_SIZE]
            ciphertext = data[self.AES_BLOCK_SIZE:]

            if len(ciphertext) == 0 or len(ciphertext) % self.AES_BLOCK_SIZE != 0:
                raise ValueError("invalid ciphertext length")
        else:
            # 使用提供的固定IV
            if len(iv) != self.AES_BLOCK_SIZE:
                raise ValueError(f"IV must be {self.AES_BLOCK_SIZE} bytes")
            ciphertext = data
            if len(ciphertext) == 0 or len(ciphertext) % self.AES_BLOCK_SIZE != 0:
                raise ValueError("invalid ciphertext length")

        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(ciphertext)
        return self._pkcs7_unpad(decrypted_padded)


    def bytes_to_base64(self,data: bytes) -> str:
        """
        将字节数据转换为Base64编码字符串
        
        Args:
            data: 需要编码的字节数据
            
        Returns:
            Base64编码的字符串
        """
        return base64.b64encode(data).decode('utf-8')


    def base64_to_bytes(self,data: str) -> bytes:
        """
        将Base64编码字符串转换为字节数据
        
        Args:
            data: Base64编码的字符串
            
        Returns:
            解码后的字节数据
        """
        return base64.b64decode(data.encode('utf-8'))

# 华米接口封装
class zepp_helper:

    def __init__(self):
        self.aes_help = aes_help()
        self.encrypt_data = self.aes_help.encrypt_data
        self.HM_AES_KEY = self.aes_help.HM_AES_KEY
        self.HM_AES_IV = self.aes_help.HM_AES_IV

    # 通过账号密码获取access_token和refresh_token 但是refresh_token不知道怎么使用
    def login_access_token(self, user, password) -> (str | None, str | None):
        headers = {
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "user-agent": "MiFit6.14.0 (M2007J1SC; Android 12; Density/2.75)",
            "app_name": "com.xiaomi.hm.health",
            "appname": "com.xiaomi.hm.health",
            "appplatform": "android_phone",
            "x-hm-ekv": "1",
            "hm-privacy-ceip": "false"
        }
        login_data = {
            'emailOrPhone': user,
            'password': password,
            'state': 'REDIRECTION',
            'client_id': 'HuaMi',
            'country_code': 'CN',
            'token': 'access',
            'redirect_uri': 'https://s3-us-west-2.amazonaws.com/hm-registration/successsignin.html',
        }
        # 等同 http_build_query，默认使用 quote_plus 将空格转为 '+'
        query = urllib.parse.urlencode(login_data)
        plaintext = query.encode('utf-8')
        # 执行请求加密
        cipher_data = self.encrypt_data(plaintext, self.HM_AES_KEY, self.HM_AES_IV)

        url1 = 'https://api-user.zepp.com/v2/registrations/tokens'
        r1 = requests.post(url1, data=cipher_data, headers=headers, allow_redirects=False, timeout=5)
        if r1.status_code != 303:
            return None, "登录异常，status: %d" % r1.status_code
        try:
            location = r1.headers["Location"]
            code = self.get_access_token(location)
            if code is None:
                return None, "获取accessToken失败 %s" % self.get_error_code(location)
        except:
            return None, f"获取accessToken异常:{traceback.format_exc()}"
        return code, None


    # 获取登录code
    def get_access_token(self, location):
        code_pattern = re.compile("(?<=access=).*?(?=&)")
        result = code_pattern.findall(location)
        if result is None or len(result) == 0:
            return None
        return result[0]


    def get_error_code(self, location):
        code_pattern = re.compile("(?<=error=).*?(?=&)")
        result = code_pattern.findall(location)
        if result is None or len(result) == 0:
            return None
        return result[0]


    # 获取北京时间
    def get_beijing_time(self):
        target_timezone = pytz.timezone('Asia/Shanghai')
        # 获取当前时间
        return datetime.now().astimezone(target_timezone)


    # 格式化时间
    def format_now(self):
        return self.get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")


    # 获取时间戳
    def get_time(self):
        current_time = self.get_beijing_time()
        return "%.0f" % (current_time.timestamp() * 1000)


    # 获取login_token，app_token，userid
    def grant_login_tokens(self, access_token, device_id, is_phone=False) -> (str | None, str | None, str | None, str | None):
        url = "https://account.huami.com/v2/client/login"
        headers = {
            "app_name": "com.xiaomi.hm.health",
            "x-request-id": f"{str(uuid.uuid4())}",
            "accept-language": "zh-CN",
            "appname": "com.xiaomi.hm.health",
            "cv": "50818_6.14.0",
            "v": "2.0",
            "appplatform": "android_phone",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        if is_phone:
            data = {
                "app_name": "com.xiaomi.hm.health",
                "app_version": "6.14.0",
                "code": access_token,
                "country_code": "CN",
                "device_id": device_id,
                "device_model": "phone",
                "grant_type": "access_token",
                "third_name": "huami_phone",
            }
        else:
            data = {
                "allow_registration=": "false",
                "app_name": "com.xiaomi.hm.health",
                "app_version": "6.14.0",
                "code": access_token,
                "country_code": "CN",
                "device_id": device_id,
                "device_model": "android_phone",
                "dn": "account.zepp.com,api-user.zepp.com,api-mifit.zepp.com,api-watch.zepp.com,app-analytics.zepp.com,api-analytics.huami.com,auth.zepp.com",
                "grant_type": "access_token",
                "lang": "zh_CN",
                "os_version": "1.5.0",
                "source": "com.xiaomi.hm.health:6.14.0:50818",
                "third_name": "email",
            }
        resp = requests.post(url, data=data, headers=headers).json()
        # print("请求客户端登录成功：%s" % json.dumps(resp, ensure_ascii=False, indent=2))  #
        _login_token, _userid, _app_token = None, None, None
        try:
            result = resp.get("result")
            if result != "ok":
                return None, None, None, "客户端登录失败：%s" % result
            _login_token = resp["token_info"]["login_token"]
            _app_token = resp["token_info"]["app_token"]
            _userid = resp["token_info"]["user_id"]
        except:
            print("提取login_token失败：%s" % json.dumps(resp, ensure_ascii=False, indent=2))
        return _login_token, _app_token, _userid, None


    # 获取app_token 用于提交数据变更
    def grant_app_token(self, login_token: str) -> (str | None, str | None):
        url = f"https://account-cn.huami.com/v1/client/app_tokens?app_name=com.xiaomi.hm.health&dn=api-user.huami.com%2Capi-mifit.huami.com%2Capp-analytics.huami.com&login_token={login_token}"
        headers = {'User-Agent': 'MiFit/5.3.0 (iPhone; iOS 14.7.1; Scale/3.00)'}
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return None, "请求异常：%d" % resp.status_code
        resp = resp.json()
        print("grant_app_token: %s" % json.dumps(resp))

        result = resp.get("result")
        if result != "ok":
            error_code = resp.get("error_code")
            return None, "请求失败：%s" % error_code
        app_token = resp['token_info']['app_token']
        return app_token, None


    # 获取用户信息 主要用于检查app_token是否有效
    def check_app_token(self, app_token) -> (bool, str | None):
        url = "https://api-mifit-cn3.zepp.com/huami.health.getUserInfo.json"

        params = {
            "r": "00b7912b-790a-4552-81b1-3742f9dd1e76",
            "userid": "1188760659",
            "appid": "428135909242707968",
            "channel": "Normal",
            "country": "CN",
            "cv": "50818_6.14.0",
            "device": "android_31",
            "device_type": "android_phone",
            "lang": "zh_CN",
            "timezone": "Asia/Shanghai",
            "v": "2.0"
        }

        headers = {
            "User-Agent": "MiFit6.14.0 (M2007J1SC; Android 12; Density/2.75)",
            "Accept-Encoding": "gzip",
            "hm-privacy-diagnostics": "false",
            "country": "CN",
            "appplatform": "android_phone",
            "hm-privacy-ceip": "true",
            "x-request-id": str(uuid.uuid4()),
            "timezone": "Asia/Shanghai",
            "channel": "Normal",
            "cv": "50818_6.14.0",
            "appname": "com.xiaomi.hm.health",
            "v": "2.0",
            "apptoken": app_token,
            "lang": "zh_CN",
            "clientid": "428135909242707968"
        }
        response = requests.get(url, params=params, headers=headers)
        if response.status_code != 200:
            return False, "请求异常：%d" % response.status_code
        response = response.json()
        message = response["message"]
        if message == "success":
            return True, None
        else:
            return False, message


    def renew_login_token(self, login_token) -> (str | None, str | None):
        url = "https://account-cn3.zepp.com/v1/client/renew_login_token"
        params = {
            "os_version": "v0.8.1",
            "dn": "account.zepp.com,api-user.zepp.com,api-mifit.zepp.com,api-watch.zepp.com,app-analytics.zepp.com,api-analytics.huami.com,auth.zepp.com",
            "login_token": login_token,
            "source": "com.xiaomi.hm.health:6.14.0:50818",
            "timestamp": self.get_time()
        }
        headers = {
            "User-Agent": "MiFit6.14.0 (M2007J1SC; Android 12; Density/2.75)",
            "Accept-Encoding": "gzip",
            "app_name": "com.xiaomi.hm.health",
            "hm-privacy-ceip": "false",
            "x-request-id": str(uuid.uuid4()),
            "accept-language": "zh-CN",
            "appname": "com.xiaomi.hm.health",
            "cv": "50818_6.14.0",
            "v": "2.0",
            "appplatform": "android_phone"
        }

        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            return None, "请求异常：%d" % resp.status_code
        resp = resp.json()
        result = resp["result"]

        if result != "ok":
            return None, "请求失败：%s" % result
        login_token = resp["token_info"]["login_token"]
        return login_token, None


    def post_fake_brand_data(self, step, app_token, userid):
        t = self.get_time()

        today = time.strftime("%F")

        data_json = '%5B%7B%22data_hr%22%3A%22%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F9L%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FVv%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F0v%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F9e%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F0n%5C%2Fa%5C%2F%5C%2F%5C%2FS%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F0b%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F1FK%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FR%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F9PTFFpaf9L%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FR%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F0j%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F9K%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FOv%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2Fzf%5C%2F%5C%2F%5C%2F86%5C%2Fzr%5C%2FOv88%5C%2Fzf%5C%2FPf%5C%2F%5C%2F%5C%2F0v%5C%2FS%5C%2F8%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FSf%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2Fz3%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F0r%5C%2FOv%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FS%5C%2F9L%5C%2Fzb%5C%2FSf9K%5C%2F0v%5C%2FRf9H%5C%2Fzj%5C%2FSf9K%5C%2F0%5C%2F%5C%2FN%5C%2F%5C%2F%5C%2F%5C%2F0D%5C%2FSf83%5C%2Fzr%5C%2FPf9M%5C%2F0v%5C%2FOv9e%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FS%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2Fzv%5C%2F%5C%2Fz7%5C%2FO%5C%2F83%5C%2Fzv%5C%2FN%5C%2F83%5C%2Fzr%5C%2FN%5C%2F86%5C%2Fz%5C%2F%5C%2FNv83%5C%2Fzn%5C%2FXv84%5C%2Fzr%5C%2FPP84%5C%2Fzj%5C%2FN%5C%2F9e%5C%2Fzr%5C%2FN%5C%2F89%5C%2F03%5C%2FP%5C%2F89%5C%2Fz3%5C%2FQ%5C%2F9N%5C%2F0v%5C%2FTv9C%5C%2F0H%5C%2FOf9D%5C%2Fzz%5C%2FOf88%5C%2Fz%5C%2F%5C%2FPP9A%5C%2Fzr%5C%2FN%5C%2F86%5C%2Fzz%5C%2FNv87%5C%2F0D%5C%2FOv84%5C%2F0v%5C%2FO%5C%2F84%5C%2Fzf%5C%2FMP83%5C%2FzH%5C%2FNv83%5C%2Fzf%5C%2FN%5C%2F84%5C%2Fzf%5C%2FOf82%5C%2Fzf%5C%2FOP83%5C%2Fzb%5C%2FMv81%5C%2FzX%5C%2FR%5C%2F9L%5C%2F0v%5C%2FO%5C%2F9I%5C%2F0T%5C%2FS%5C%2F9A%5C%2Fzn%5C%2FPf89%5C%2Fzn%5C%2FNf9K%5C%2F07%5C%2FN%5C%2F83%5C%2Fzn%5C%2FNv83%5C%2Fzv%5C%2FO%5C%2F9A%5C%2F0H%5C%2FOf8%5C%2F%5C%2Fzj%5C%2FPP83%5C%2Fzj%5C%2FS%5C%2F87%5C%2Fzj%5C%2FNv84%5C%2Fzf%5C%2FOf83%5C%2Fzf%5C%2FOf83%5C%2Fzb%5C%2FNv9L%5C%2Fzj%5C%2FNv82%5C%2Fzb%5C%2FN%5C%2F85%5C%2Fzf%5C%2FN%5C%2F9J%5C%2Fzf%5C%2FNv83%5C%2Fzj%5C%2FNv84%5C%2F0r%5C%2FSv83%5C%2Fzf%5C%2FMP%5C%2F%5C%2F%5C%2Fzb%5C%2FMv82%5C%2Fzb%5C%2FOf85%5C%2Fz7%5C%2FNv8%5C%2F%5C%2F0r%5C%2FS%5C%2F85%5C%2F0H%5C%2FQP9B%5C%2F0D%5C%2FNf89%5C%2Fzj%5C%2FOv83%5C%2Fzv%5C%2FNv8%5C%2F%5C%2F0f%5C%2FSv9O%5C%2F0ZeXv%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F1X%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F9B%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2FTP%5C%2F%5C%2F%5C%2F1b%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F0%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F9N%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2F%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%5C%2Fv7%2B%22%2C%22date%22%3A%222021-08-07%22%2C%22data%22%3A%5B%7B%22start%22%3A0%2C%22stop%22%3A1439%2C%22value%22%3A%22UA8AUBQAUAwAUBoAUAEAYCcAUBkAUB4AUBgAUCAAUAEAUBkAUAwAYAsAYB8AYB0AYBgAYCoAYBgAYB4AUCcAUBsAUB8AUBwAUBIAYBkAYB8AUBoAUBMAUCEAUCIAYBYAUBwAUCAAUBgAUCAAUBcAYBsAYCUAATIPYD0KECQAYDMAYB0AYAsAYCAAYDwAYCIAYB0AYBcAYCQAYB0AYBAAYCMAYAoAYCIAYCEAYCYAYBsAYBUAYAYAYCIAYCMAUB0AUCAAUBYAUCoAUBEAUC8AUB0AUBYAUDMAUDoAUBkAUC0AUBQAUBwAUA0AUBsAUAoAUCEAUBYAUAwAUB4AUAwAUCcAUCYAUCwKYDUAAUUlEC8IYEMAYEgAYDoAYBAAUAMAUBkAWgAAWgAAWgAAWgAAWgAAUAgAWgAAUBAAUAQAUA4AUA8AUAkAUAIAUAYAUAcAUAIAWgAAUAQAUAkAUAEAUBkAUCUAWgAAUAYAUBEAWgAAUBYAWgAAUAYAWgAAWgAAWgAAWgAAUBcAUAcAWgAAUBUAUAoAUAIAWgAAUAQAUAYAUCgAWgAAUAgAWgAAWgAAUAwAWwAAXCMAUBQAWwAAUAIAWgAAWgAAWgAAWgAAWgAAWgAAWgAAWgAAWREAWQIAUAMAWSEAUDoAUDIAUB8AUCEAUC4AXB4AUA4AWgAAUBIAUA8AUBAAUCUAUCIAUAMAUAEAUAsAUAMAUCwAUBYAWgAAWgAAWgAAWgAAWgAAWgAAUAYAWgAAWgAAWgAAUAYAWwAAWgAAUAYAXAQAUAMAUBsAUBcAUCAAWwAAWgAAWgAAWgAAWgAAUBgAUB4AWgAAUAcAUAwAWQIAWQkAUAEAUAIAWgAAUAoAWgAAUAYAUB0AWgAAWgAAUAkAWgAAWSwAUBIAWgAAUC4AWSYAWgAAUAYAUAoAUAkAUAIAUAcAWgAAUAEAUBEAUBgAUBcAWRYAUA0AWSgAUB4AUDQAUBoAXA4AUA8AUBwAUA8AUA4AUA4AWgAAUAIAUCMAWgAAUCwAUBgAUAYAUAAAUAAAUAAAUAAAUAAAUAAAUAAAUAAAUAAAWwAAUAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAeSEAeQ8AcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcBcAcAAAcAAAcCYOcBUAUAAAUAAAUAAAUAAAUAUAUAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcCgAeQAAcAAAcAAAcAAAcAAAcAAAcAYAcAAAcBgAeQAAcAAAcAAAegAAegAAcAAAcAcAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcCkAeQAAcAcAcAAAcAAAcAwAcAAAcAAAcAIAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcCIAeQAAcAAAcAAAcAAAcAAAcAAAeRwAeQAAWgAAUAAAUAAAUAAAUAAAUAAAcAAAcAAAcBoAeScAeQAAegAAcBkAeQAAUAAAUAAAUAAAUAAAUAAAUAAAcAAAcAAAcAAAcAAAcAAAcAAAegAAegAAcAAAcAAAcBgAeQAAcAAAcAAAcAAAcAAAcAAAcAkAegAAegAAcAcAcAAAcAcAcAAAcAAAcAAAcAAAcA8AeQAAcAAAcAAAeRQAcAwAUAAAUAAAUAAAUAAAUAAAUAAAcAAAcBEAcA0AcAAAWQsAUAAAUAAAUAAAUAAAUAAAcAAAcAoAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAYAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcBYAegAAcAAAcAAAegAAcAcAcAAAcAAAcAAAcAAAcAAAeRkAegAAegAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAEAcAAAcAAAcAAAcAUAcAQAcAAAcBIAeQAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcBsAcAAAcAAAcBcAeQAAUAAAUAAAUAAAUAAAUAAAUBQAcBYAUAAAUAAAUAoAWRYAWTQAWQAAUAAAUAAAUAAAcAAAcAAAcAAAcAAAcAAAcAMAcAAAcAQAcAAAcAAAcAAAcDMAeSIAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcBQAeQwAcAAAcAAAcAAAcAMAcAAAeSoAcA8AcDMAcAYAeQoAcAwAcFQAcEMAeVIAaTYAbBcNYAsAYBIAYAIAYAIAYBUAYCwAYBMAYDYAYCkAYDcAUCoAUCcAUAUAUBAAWgAAYBoAYBcAYCgAUAMAUAYAUBYAUA4AUBgAUAgAUAgAUAsAUAsAUA4AUAMAUAYAUAQAUBIAASsSUDAAUDAAUBAAYAYAUBAAUAUAUCAAUBoAUCAAUBAAUAoAYAIAUAQAUAgAUCcAUAsAUCIAUCUAUAoAUA4AUB8AUBkAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAAfgAA%22%2C%22tz%22%3A32%2C%22did%22%3A%22DA932FFFFE8816E7%22%2C%22src%22%3A24%7D%5D%2C%22summary%22%3A%22%7B%5C%22v%5C%22%3A6%2C%5C%22slp%5C%22%3A%7B%5C%22st%5C%22%3A1628296479%2C%5C%22ed%5C%22%3A1628296479%2C%5C%22dp%5C%22%3A0%2C%5C%22lt%5C%22%3A0%2C%5C%22wk%5C%22%3A0%2C%5C%22usrSt%5C%22%3A-1440%2C%5C%22usrEd%5C%22%3A-1440%2C%5C%22wc%5C%22%3A0%2C%5C%22is%5C%22%3A0%2C%5C%22lb%5C%22%3A0%2C%5C%22to%5C%22%3A0%2C%5C%22dt%5C%22%3A0%2C%5C%22rhr%5C%22%3A0%2C%5C%22ss%5C%22%3A0%7D%2C%5C%22stp%5C%22%3A%7B%5C%22ttl%5C%22%3A18272%2C%5C%22dis%5C%22%3A10627%2C%5C%22cal%5C%22%3A510%2C%5C%22wk%5C%22%3A41%2C%5C%22rn%5C%22%3A50%2C%5C%22runDist%5C%22%3A7654%2C%5C%22runCal%5C%22%3A397%2C%5C%22stage%5C%22%3A%5B%7B%5C%22start%5C%22%3A327%2C%5C%22stop%5C%22%3A341%2C%5C%22mode%5C%22%3A1%2C%5C%22dis%5C%22%3A481%2C%5C%22cal%5C%22%3A13%2C%5C%22step%5C%22%3A680%7D%2C%7B%5C%22start%5C%22%3A342%2C%5C%22stop%5C%22%3A367%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A2295%2C%5C%22cal%5C%22%3A95%2C%5C%22step%5C%22%3A2874%7D%2C%7B%5C%22start%5C%22%3A368%2C%5C%22stop%5C%22%3A377%2C%5C%22mode%5C%22%3A4%2C%5C%22dis%5C%22%3A1592%2C%5C%22cal%5C%22%3A88%2C%5C%22step%5C%22%3A1664%7D%2C%7B%5C%22start%5C%22%3A378%2C%5C%22stop%5C%22%3A386%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A1072%2C%5C%22cal%5C%22%3A51%2C%5C%22step%5C%22%3A1245%7D%2C%7B%5C%22start%5C%22%3A387%2C%5C%22stop%5C%22%3A393%2C%5C%22mode%5C%22%3A4%2C%5C%22dis%5C%22%3A1036%2C%5C%22cal%5C%22%3A57%2C%5C%22step%5C%22%3A1124%7D%2C%7B%5C%22start%5C%22%3A394%2C%5C%22stop%5C%22%3A398%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A488%2C%5C%22cal%5C%22%3A19%2C%5C%22step%5C%22%3A607%7D%2C%7B%5C%22start%5C%22%3A399%2C%5C%22stop%5C%22%3A414%2C%5C%22mode%5C%22%3A4%2C%5C%22dis%5C%22%3A2220%2C%5C%22cal%5C%22%3A120%2C%5C%22step%5C%22%3A2371%7D%2C%7B%5C%22start%5C%22%3A415%2C%5C%22stop%5C%22%3A427%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A1268%2C%5C%22cal%5C%22%3A59%2C%5C%22step%5C%22%3A1489%7D%2C%7B%5C%22start%5C%22%3A428%2C%5C%22stop%5C%22%3A433%2C%5C%22mode%5C%22%3A1%2C%5C%22dis%5C%22%3A152%2C%5C%22cal%5C%22%3A4%2C%5C%22step%5C%22%3A238%7D%2C%7B%5C%22start%5C%22%3A434%2C%5C%22stop%5C%22%3A444%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A2295%2C%5C%22cal%5C%22%3A95%2C%5C%22step%5C%22%3A2874%7D%2C%7B%5C%22start%5C%22%3A445%2C%5C%22stop%5C%22%3A455%2C%5C%22mode%5C%22%3A4%2C%5C%22dis%5C%22%3A1592%2C%5C%22cal%5C%22%3A88%2C%5C%22step%5C%22%3A1664%7D%2C%7B%5C%22start%5C%22%3A456%2C%5C%22stop%5C%22%3A466%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A1072%2C%5C%22cal%5C%22%3A51%2C%5C%22step%5C%22%3A1245%7D%2C%7B%5C%22start%5C%22%3A467%2C%5C%22stop%5C%22%3A477%2C%5C%22mode%5C%22%3A4%2C%5C%22dis%5C%22%3A1036%2C%5C%22cal%5C%22%3A57%2C%5C%22step%5C%22%3A1124%7D%2C%7B%5C%22start%5C%22%3A478%2C%5C%22stop%5C%22%3A488%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A488%2C%5C%22cal%5C%22%3A19%2C%5C%22step%5C%22%3A607%7D%2C%7B%5C%22start%5C%22%3A489%2C%5C%22stop%5C%22%3A499%2C%5C%22mode%5C%22%3A4%2C%5C%22dis%5C%22%3A2220%2C%5C%22cal%5C%22%3A120%2C%5C%22step%5C%22%3A2371%7D%2C%7B%5C%22start%5C%22%3A500%2C%5C%22stop%5C%22%3A511%2C%5C%22mode%5C%22%3A3%2C%5C%22dis%5C%22%3A1268%2C%5C%22cal%5C%22%3A59%2C%5C%22step%5C%22%3A1489%7D%2C%7B%5C%22start%5C%22%3A512%2C%5C%22stop%5C%22%3A522%2C%5C%22mode%5C%22%3A1%2C%5C%22dis%5C%22%3A152%2C%5C%22cal%5C%22%3A4%2C%5C%22step%5C%22%3A238%7D%5D%7D%2C%5C%22goal%5C%22%3A8000%2C%5C%22tz%5C%22%3A%5C%2228800%5C%22%7D%22%2C%22source%22%3A24%2C%22type%22%3A0%7D%5D'

        find_date = re.compile(r".*?date%22%3A%22(.*?)%22%2C%22data.*?")
        find_step = re.compile(r".*?ttl%5C%22%3A(.*?)%2C%5C%22dis.*?")
        data_json = re.sub(find_date.findall(data_json)[0], today, str(data_json))
        data_json = re.sub(find_step.findall(data_json)[0], step, str(data_json))

        url = f'https://api-mifit-cn.huami.com/v1/data/band_data.json?&t={t}&r={str(uuid.uuid4())}'
        head = {
            "apptoken": app_token,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = f'userid={userid}&last_sync_data_time=1597306380&device_type=0&last_deviceid=DA932FFFFE8816E7&data_json={data_json}'

        response = requests.post(url, data=data, headers=head)
        if response.status_code != 200:
            return False, "请求修改步数异常：%d" % response.status_code
        response = response.json()
        message = response["message"]
        if message == "success":
            return True, message
        else:
            return False, message


# 邮箱登录刷步数主函数
class TokenCache:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Dict[str, Dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.warning(f"读取 token 缓存失败: {exc}")
        return {}

    def save(self, data: Dict[str, Dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, email: str) -> Optional[Dict[str, str]]:
        return self.load().get(email)

    def set(self, email: str, app_token: str, user_id: str) -> None:
        data = self.load()
        data[email] = {
            "app_token": app_token,
            "user_id": user_id,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        self.save(data)


class EmailStepClient:
    """邮箱账号登录并修改步数的简化封装。"""

    def __init__(self, email: str, password: str, token_cache: TokenCache):
        if not email or not password:
            raise ValueError("email 或 password 不能为空")
        self.email = email
        self.password = password
        self.device_id = str(uuid.uuid4())
        self.user_id: Optional[str] = None
        self.app_token: Optional[str] = None
        self.token_cache = token_cache

        self.zepp_helper_object = zepp_helper()

    def login(self) -> Tuple[bool, str]:
        """通过邮箱密码登录并获取 app_token。"""
        access_token, msg = self.zepp_helper_object.login_access_token(self.email, self.password)
        if access_token is None:
            return False, f"登录获取 access_token 失败：{msg}"

        login_token, app_token, user_id, msg = self.zepp_helper_object.grant_login_tokens(
            access_token,
            self.device_id,
            is_phone=False,
        )
        if login_token is None or app_token is None or user_id is None:
            return False, f"登录获取 app_token 失败：{msg}"

        self.app_token = app_token
        self.user_id = user_id
        self.token_cache.set(self.email, app_token, user_id)
        logger.info(f"{self.email} 登录成功 app_token: {self.app_token}, user_id: {self.user_id}")
        return True, "登录成功"

    def ensure_login(self) -> Tuple[bool, str]:
        """优先使用缓存 token；失效再登录。"""
        cached = self.token_cache.get(self.email)
        if cached and cached.get("app_token") and cached.get("user_id"):
            app_token = cached["app_token"]
            user_id = cached["user_id"]
            ok, msg = self.zepp_helper_object.check_app_token(app_token)
            if ok:
                self.app_token = app_token
                self.user_id = user_id
                logger.info(f"{self.email} 使用缓存 token 登录")
                return True, "使用缓存 token 登录"
            logger.warning(f"{self.email} 缓存 token 失效，重新登录: {msg}")

        return self.login()

    def update_steps(self, steps: int) -> Tuple[bool, str]:
        """提交步数变更。"""
        if self.app_token is None or self.user_id is None:
            return False, "未登录，请先调用 login()"
        if steps <= 0:
            return False, "步数必须为正数"

        ok, msg = self.zepp_helper_object.post_fake_brand_data(str(steps), self.app_token, self.user_id)
        if ok:
            logger.info(f"{self.email} 提交步数变更成功，steps: {steps}, ok: {ok}, msg: {msg}")
        else:
            logger.error(f"{self.email} 提交步数变更失败，steps: {steps}, ok: {ok}, msg: {msg}")
        return ok, msg

    def run(self, steps: int) -> Tuple[bool, str]:
        """登录并修改步数的一步调用。"""
        ok, msg = self.ensure_login()
        if not ok:
            return False, msg
        return self.update_steps(steps)

def parse_accounts() -> Dict[str, str]:
    raw = os.getenv("MI_ACCOUNTS", "").strip()
    if not raw:
        return {}
    accounts: Dict[str, str] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError("MI_ACCOUNTS 格式错误，应为 email:password;email:password")
        email, password = item.split(":", 1)
        email = email.strip()
        password = password.strip()
        if not email or not password:
            raise ValueError("MI_ACCOUNTS 中存在空的账号或密码")
        accounts[email] = password
    return accounts


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"环境变量 {name} 必须是整数")


def get_beijing_date() -> str:
    return datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")


def parse_run_ranges() -> Dict[int, Tuple[int, int]]:
    """
    环境变量 RUN_RANGES 格式：
    1=8000-12000;2=12000-15000;3=15000-30000
    """
    raw = os.getenv("RUN_RANGES", "").strip()
    if not raw:
        return {
            1: (8000, 12000),
            2: (12000, 15000),
            3: (15000, 30000),
        }

    ranges: Dict[int, Tuple[int, int]] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" not in item or "-" not in item:
            raise ValueError("RUN_RANGES 格式错误，应为 1=8000-12000;2=12000-15000")
        run_part, range_part = item.split("=", 1)
        min_part, max_part = range_part.split("-", 1)
        run_index = int(run_part.strip())
        min_steps = int(min_part.strip())
        max_steps = int(max_part.strip())
        if min_steps <= 0 or max_steps <= 0 or min_steps > max_steps:
            raise ValueError(f"RUN_RANGES 中 run={run_index} 的范围不正确")
        ranges[run_index] = (min_steps, max_steps)

    if not ranges:
        raise ValueError("RUN_RANGES 为空")
    return ranges


def get_run_index(state_path: Path, email: str, max_run: int) -> Optional[int]:
    today = get_beijing_date()
    data: Dict[str, object] = {}
    if state_path.exists():
        try:
            with state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning(f"读取运行状态失败: {exc}")

    if data.get("date") != today:
        data = {"date": today, "counts": {}}

    counts = data.get("counts")
    if not isinstance(counts, dict):
        counts = {}

    current = int(counts.get(email, 0))
    if current >= max_run:
        return None

    next_count = current + 1
    counts[email] = next_count
    data["counts"] = counts

    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return next_count


def main() -> None:
    accounts = parse_accounts()
    if not accounts:
        raise ValueError("未设置 MI_ACCOUNTS，请在环境变量中配置账号密码")

    run_ranges = parse_run_ranges()

    cache_path = Path(os.getenv("TOKEN_CACHE_PATH", ".cache/token_cache.json"))
    token_cache = TokenCache(cache_path)

    state_path = Path(os.getenv("RUN_STATE_PATH", ".cache/run_state.json"))
    max_run = max(run_ranges.keys())

    for email, password in accounts.items():
        run_index = get_run_index(state_path, email, max_run)
        if run_index is None:
            logger.info(f"{email} 当天已超过最大运行次数 {max_run}，跳过")
            continue

        if run_index not in run_ranges:
            logger.info(f"{email} 当前第 {run_index} 次运行不在 RUN_RANGES 中，跳过")
            continue

        min_steps, max_steps = run_ranges[run_index]
        logger.info(f"{email} 当前第 {run_index} 次运行，步数范围 {min_steps}-{max_steps}")
        client = EmailStepClient(email, password, token_cache)
        steps = randint(min_steps, max_steps)
        ok, msg = client.run(steps)
        logger.info(f"email: {email}, steps: {steps}, ok: {ok}, msg: {msg}")


if __name__ == "__main__":
    main()
