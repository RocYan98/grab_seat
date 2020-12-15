"""
学习通抢座
"""
import base64
import datetime
import inspect
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import TimedRotatingFileHandler

import re
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
import warnings

warnings.filterwarnings('ignore')

# user_name, password, times_dict, room_id, seat_id
stu_dect = [
    ("user_name", "password", [("08:00", "12:00"), ("12:00", "16:00"), ("16:00", "20:00"), ("20:00", "22:00")],
     "room_id", "seat_id"),
]


def _getLogger(seat):
    """日志记录"""
    logger = logging.getLogger("[" + "座位" + seat + "]")
    this_file = inspect.getfile(inspect.currentframe())
    dirpath = os.path.abspath(os.path.dirname(this_file))
    if os.path.isdir('%s/log' % dirpath):  # 创建log文件夹
        pass
    else:
        os.mkdir('%s/log' % dirpath)
    dir = '%s/log' % dirpath

    handler = TimedRotatingFileHandler(os.path.join(dir, "StudySeat_5.log"), when="midnight", interval=1,
                                       backupCount=20)
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    return logger


class superstar_login:
    def __init__(self, user_info_dict):
        self.login_page = "https://passport2.chaoxing.com/mlogin?loginType=1&newversion=true&fid=&refer=http%3A%2F%2Foffice.chaoxing.com%2Ffront%2Fthird%2Fapps%2Fseat%2Fcode%3Fid%3D{}%26seatNum%3D{}".format(
            user_info_dict[3], user_info_dict[4])
        self.url = "https://office.chaoxing.com/front/third/apps/seat/code?id={}&seatNum={}".format(user_info_dict[3],
                                                                                                    user_info_dict[4])
        self.is_can_appoint_url = "https://office.chaoxing.com/data/apps/seat/room/info"
        self.submit_url = "https://office.chaoxing.com/data/apps/seat/submit"
        self.seat_url = "https://office.chaoxing.com/data/apps/seat/getusedtimes"
        self.login_url = "https://passport2.chaoxing.com/fanyalogin"
        self.token = ""
        self.fail_dict = []
        self.user_info_dict = user_info_dict
        self.password = base64.b64encode(user_info_dict[1].encode("utf-8"))
        self.start_time = None
        self.end_time = None
        self.scheduler = BlockingScheduler()
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; V1922A Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/77.0.3865.120 MQQBrowser/6.2 TBS/045329 Mobile Safari/537.36 MMWEBID/7991 MicroMessenger/7.0.18.1740(0x27001235) Process/tools WeChat/arm64 NetType/WIFI Language/zh_CN ABI/arm64",
            "X-Requested-With": "com.tencent.mm",
            "Cookie": ""
        }
        self.login_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; V1922A Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/77.0.3865.120 MQQBrowser/6.2 TBS/045329 Mobile Safari/537.36 MMWEBID/7991 MicroMessenger/7.0.18.1740(0x27001235) Process/tools WeChat/arm64 NetType/WIFI Language/zh_CN ABI/arm64",
            "Cookie": "",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "passport2.chaoxing.com"
        }
        self.logger = _getLogger(self.user_info_dict[4])

    def get_html(self, url):
        self.headers["Cookie"] = self.login_headers["Cookie"]
        response = requests.get(url=url, headers=self.headers, verify=False)
        html = response.content.decode('utf-8')
        self.token = re.findall('token: \'(.*?)\'', html)[0]
        cookie = requests.utils.dict_from_cookiejar(response.cookies)
        if len(cookie) < 2:
            self.get_html(self.url)
            return None
        self.headers["Cookie"] = ""
        for i in cookie:
            self.headers["Cookie"] += i + "=" + cookie[i] + ";"
            self.login_headers["Cookie"] += i + "=" + cookie[i] + ";"

    def get_login_html(self):
        self.logger.debug("---登录页面 before---")
        response = requests.get(url=self.login_page, headers=self.headers, verify=False)
        cookie = requests.utils.dict_from_cookiejar(response.cookies)
        self.headers["Cookie"] = ""
        for i in cookie:
            self.headers["Cookie"] += i + "=" + cookie[i] + ";"
            self.login_headers["Cookie"] += i + "=" + cookie[i] + ";"
        self.logger.debug("---登录页面 end---")

    def get_submit(self, url, seat, try_times):
        day = datetime.date.today() + datetime.timedelta(days=1)
        # day = datetime.date.today()
        parm = {
            "roomId": self.user_info_dict[3],
            "day": str(day),
            "startTime": seat[0],
            "endTime": seat[1],
            "seatNum": self.user_info_dict[4],
            "token": self.token,
            "type": 1
        }
        html = requests.post(url=url, params=parm, headers=self.headers, verify=False).content.decode('utf-8')
        msg = self.user_info_dict[4] + "---" + seat[0] + "~" + seat[1] + ':'
        jhtml = json.loads(html)
        if jhtml["success"]:
            msg += "预约成功"
            print(msg)
            self.logger.info(msg)
        elif try_times < 3:
            msg += json.loads(html)["msg"] + " 即将尝试重新预约"
            print(msg)
            self.logger.info(msg)
            self.get_submit(url, seat, try_times + 1)
        else:
            msg += "预约失败"
            print(msg + "")
            self.logger.info(msg)

    def login(self):
        parm = {
            "fid": -1,
            "uname": self.user_info_dict[0],
            "password": base64.b64encode(self.user_info_dict[1].encode("utf-8")),
            "refer": "http%3A%2F%2Foffice.chaoxing.com%2Ffront%2Fthird%2Fapps%2Fseat%2Fcode%3Fid%3D4219%26seatNum%3D380",
            "t": True
        }
        jsons = requests.post(url=self.login_url, params=parm, headers=self.login_headers, verify=False)
        cookie = requests.utils.dict_from_cookiejar(jsons.cookies)
        cookie_str = ""
        for i in cookie:
            cookie_str += i + "=" + cookie[i] + ";"
        self.headers["Cookie"] += cookie_str
        self.login_headers["Cookie"] += cookie_str
        content = jsons.content.decode('utf-8')
        if content.find("true") != -1:
            print(self.user_info_dict[4] + "---登录成功")
            self.logger.info("---登录成功---")
        else:
            print(self.user_info_dict[4] + "---登录失败")
            self.logger.info("---登录失败---")

    def submit(self, i):
        self.get_html(self.url)
        self.get_submit(self.submit_url, i, 0)

    def submit_final(self):
        self.start_time = time.time()
        dit = self.user_info_dict[2]
        executor1 = ThreadPoolExecutor()
        for i in dit:
            executor1.submit(self.submit, i)
            time.sleep(0.05)
        self.end_time = time.time()
        time.sleep(10)
        executor1.shutdown()
        self.shutdown()

    def shutdown(self):
        self.logger.info("===调度结束===")

    def run(self):
        self.get_login_html()
        self.login()
        self.scheduler.add_job(self.submit_final, 'cron', day_of_week='0-6', hour=17, minute=00)
        # self.submit_final()
        self.logger.info("===调度开始===")
        self.scheduler.start()


def show(dict):
    s = superstar_login(dict)
    s.run()


def main():
    executor = ThreadPoolExecutor()
    for i in stu_dect:
        executor.submit(show, i)
    executor.shutdown()


if __name__ == "__main__":
    main()
