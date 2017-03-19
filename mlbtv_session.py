import os
import pickle
import time
from xbmcswift2 import xbmc, xbmcaddon
import requests
from utils import *

COOKIE_PATH = xbmc.translatePath(os.path.join(xbmcaddon.Addon().getAddonInfo('profile'), 'cookies.p'))
UA_PC = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.97 Safari/537.36'

class MlbTvSession():
    def __init__(self):
        if not os.path.exists(COOKIE_PATH):
            self._login()
        cookies = self._load_cookies()
        if self._cookies_expired(cookies):
            self._login()

    def save_cookies(self, cookies):
        self._write_cookies(cookies)

    def get_cookies(self):
        cookies = self._load_cookies()
        if self._cookies_expired(cookies):
            self._login()
            cookies = self._load_cookies()
        return cookies

    def _cookies_expired(self, cookies):
        if not cookies:
            return False
        return time.time() >= max([c.expires for c in cookies])

    def _load_cookies(self):
        with open(COOKIE_PATH, 'rb') as f:
            return pickle.load(f)

    def _write_cookies(self, cookies):
        with open(COOKIE_PATH, 'wb') as f:
            pickle.dump(cookies, f)

    def _login(self):

        """
        cj = cookielib.LWPCookieJar(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'))
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

        url = 'https://securea.mlb.com/authenticate.do'
        login_data = 'uri=%2Faccount%2Flogin_register.jsp&registrationAction=identify&emailAddress='+USERNAME+'&password='+PASSWORD+'&submitButton='

        req = urllib2.Request(url, data=login_data, headers=
            {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
             "Accept-Encoding": "gzip, deflate",
             "Accept-Language": "en-US,en;q=0.8",
             "Content-Type": "application/x-www-form-urlencoded",
             "Origin": "https://securea.mlb.com",
             "Connection": "keep-alive",
             "Cookie": "SESSION_1=wf_forwardUrl%3D%3D%3Dhttp%3A%2F%2Fm.mlb.com%2Ftv%2Fe14-469412-2016-03-02%2Fv545147283%2F%3F%26media_type%3Dvideo%26clickOrigin%3DMedia%2520Grid%26team%3Dmlb%7Ewf_flowId%3D%3D%3Dregistration.dynaindex%7Ewf_template%3D%3D%3Dmp5default%7Ewf_mediaTypeTemplate%3D%3D%3Dvideo%7Estage%3D%3D%3D3%7EflowId%3D%3D%3Dregistration.dynaindex%7EforwardUrl%3D%3D%3Dhttp%3A%2F%2Fm.mlb.com%2Ftv%2Fe14-469412-2016-03-02%2Fv545147283%2F%3F%26media_type%3Dvideo%26clickOrigin%3DMedia%2520Grid%26team%3Dmlb%3B",
             "User-Agent": UA_PC})

        log("API call {0}".format(req.get_full_url()))
        response = opener.open(req)
        # if url has not changed the login was not valid.
        if response.geturl() == url:
            msg = "Please check that your username and password are correct"
            dialog = xbmcgui.Dialog()
            ok = dialog.ok('Invalid Login', msg)
            sys.exit()
        else:
            cj.save(ignore_discard=True)

        response.close()
        """
        url = 'https://securea.mlb.com/authenticate.do'
        login_data = {'password': PASSWORD, 'emailAddress': USERNAME, 'uri': '/account/login_register.jsp', 'registrationAction': 'identify'}
        headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
             "Accept-Encoding": "gzip, deflate",
             "Accept-Language": "en-US,en;q=0.8",
             "Content-Type": "application/x-www-form-urlencoded",
             "Origin": "https://securea.mlb.com",
             "Connection": "keep-alive",
             "Cookie": "SESSION_1=wf_forwardUrl%3D%3D%3Dhttp%3A%2F%2Fm.mlb.com%2Ftv%2Fe14-469412-2016-03-02%2Fv545147283%2F%3F%26media_type%3Dvideo%26clickOrigin%3DMedia%2520Grid%26team%3Dmlb%7Ewf_flowId%3D%3D%3Dregistration.dynaindex%7Ewf_template%3D%3D%3Dmp5default%7Ewf_mediaTypeTemplate%3D%3D%3Dvideo%7Estage%3D%3D%3D3%7EflowId%3D%3D%3Dregistration.dynaindex%7EforwardUrl%3D%3D%3Dhttp%3A%2F%2Fm.mlb.com%2Ftv%2Fe14-469412-2016-03-02%2Fv545147283%2F%3F%26media_type%3Dvideo%26clickOrigin%3DMedia%2520Grid%26team%3Dmlb%3B",
             "User-Agent": UA_PC}
        session = requests.Session()
        response = session.post(url, data=login_data, headers=headers)
        if response.url == url:
            msg = "Please check that your username and password are correct"
            dialog = xbmcgui.Dialog()
            ok = dialog.ok('Invalid Login', msg)
            sys.exit()
        else:
            log("_login cookies response {0}".format(session.cookies))
            self._write_cookies(session.cookies)