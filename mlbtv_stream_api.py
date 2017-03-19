import requests
import mlbtv_session
import mlb_exceptions
import StorageServer
from xbmcswift2 import Plugin
from utils import *
import datetime
import time

cache = StorageServer.StorageServer("plugin.video.mlbbasesloaded", 24)
plugin = Plugin()
session = mlbtv_session.MlbTvSession()
UA_PS4 = 'PS4Application libhttp/1.000 (PS4) libhttp/3.15 (PlayStation 4)'
UA_PC = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.97 Safari/537.36'

def get_stream(home_team, away_team):
    # from grid_ce.json get calendar_event_id (event_id) and id (content_id)
    # and ['game_media']['homebase']['media']
    url = 'http://gdx.mlb.com/components/game/mlb/{0}/grid_ce.json'.format(datetime.datetime.today().strftime(u'year_%Y/month_%m/day_%d'))
    streams = requests.get(url).json()

    stream_to_goto = None
    for stream in streams['data']['games']['game']:
        if stream['home_name_abbrev'] == home_team and stream['away_name_abbrev'] == away_team:
            stream_to_goto = stream
            break

    if stream_to_goto is None:
        plugin.notify("Can't find stream for game between {0} and {1}".format(away_team, home_team))
        return

    event_id = stream_to_goto['calendar_event_id']
    try:
        # Searching for type = 'mlbtv_home' or 'mlbtv_away' will allow choosing
        # which stream to take. Maybe use broadcast rankings to determine?
        content_id = stream_to_goto['game_media']['homebase']['media'][0]['id']
    except KeyError:
        raise mlb_exceptions.StreamNotFoundException()

    cookies = session.get_cookies()
    identity_point_id = cookies['ipid']
    fingerprint = cookies['fprt']

#     session_key = cache.cacheFunction(get_session_key, identity_point_id, fingerprint, event_id, content_id)
    session_key = get_session_key(identity_point_id, fingerprint, event_id, content_id)

    if not session_key or session_key == 'blackout':
        raise mlb_exceptions.StreamNotFoundException()

#     url = cache.cacheFunction(get_url, identity_point_id, fingerprint, content_id, session_key, event_id)
    url = get_url(identity_point_id, fingerprint, content_id, session_key, event_id)

    return url

def get_url(identity_point_id, fingerprint, content_id, session_key, event_id):
    url = 'https://mlb-ws-mf.media.mlb.com/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    params = {
        'identityPointId': identity_point_id,
        'fingerprint': fingerprint,
        'contentId': content_id,
        'eventId': event_id,
        'playbackScenario': 'HTTP_CLOUD_WIRED_60',  # TODO ?
        'subject': 'LIVE_EVENT_COVERAGE',
        'platform': 'PS4',
        'sessionKey': session_key,
        'format': 'json'
    }

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'deflate',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive',
        'User-Agent': UA_PS4
    }

    s = requests.Session()
    s.cookies = session.get_cookies()
    r = s.get(url, params=params, headers=headers).json()
    log("API call {0}\n{1}\n{2}\n{3}".format(url, params, headers, session.get_cookies()))
    if r['status_code'] != 1:
        log(r)
        raise mlb_exceptions.StreamNotFoundException()
    else:
        log("get_url cookies response {0}".format(s.cookies))
        session.save_cookies(s.cookies)
        base_url = r['user_verified_event'][0]['user_verified_content'][0]['user_verified_media_item'][0]['url']
        media_auth = s.cookies['mediaAuth']
        url = "{0}|User-Agent={1}&Cookie=mediaAuth={2}".format(base_url, UA_PS4, media_auth)
        # TODO make configurable
        bandwidth = "800"
        url = url.replace('master_wired60.m3u8', bandwidth+'K/'+bandwidth+'_complete.m3u8')
        return url

    """
    cj = cookielib.LWPCookieJar(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'))
    cj.load(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'),ignore_discard=True)
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    playback_scenario = 'HTTP_CLOUD_WIRED_60' # ??
    url = 'https://mlb-ws-mf.media.mlb.com/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    url = url + '?identityPointId='+identity_point_id
    url = url + '&fingerprint='+fingerprint
    url = url + '&contentId='+content_id
    url = url + '&eventId='+event_id
    url = url + '&playbackScenario='+playback_scenario
    url = url + '&subject=LIVE_EVENT_COVERAGE'
    url = url + '&sessionKey='+urllib.quote_plus(session_key)
    url = url + '&platform=PS4'
    url = url + '&format=json'
    req = urllib2.Request(url)
    req.add_header("Accept", "*/*")
    req.add_header("Accept-Encoding", "deflate")
    req.add_header("Accept-Language", "en-US,en;q=0.8")
    req.add_header("Connection", "keep-alive")
    req.add_header("User-Agent", UA_PS4)

    log("API call {0}".format(req.get_full_url()))
    response = opener.open(req)
    json_source = json.load(response)
    response.close()

    if json_source['status_code'] != 1:
        log(json_source)
        raise StreamNotFoundException()

    url = json_source['user_verified_event'][0]['user_verified_content'][0]['user_verified_media_item'][0]['url']
    for cookie in cj:
        if cookie.name == "mediaAuth":
            media_auth = "mediaAuth="+cookie.value

    cj.save(ignore_discard=True)
    url = url + '|User-Agent='+UA_PS4+'&Cookie='+media_auth
    return url
    """

def get_session_key(identity_point_id, fingerprint, event_id, content_id):
    url = 'https://mlb-ws-mf.media.mlb.com/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    params = {
        'identityPointId': identity_point_id,
        'fingerprint': fingerprint,
        'eventId': event_id,
        'subject': 'LIVE_EVENT_COVERAGE',
        'platform': 'WIN8',
        '_': str(int(round(time.time()*1000))),
        'format': 'json',
        'frameworkURL': 'https://mlb-ws-mf.media.mlb.com&frameworkEndPoint=/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    }

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'deflate',
        'Accept-Language': 'en-US,en;q=0.8',
        'Connection': 'keep-alive',
        'User-Agent': UA_PC,
        'Origin': 'http://m.mlb.com',
        'Referer': 'http://m.mlb.com/tv/e{0}/v{1}/?&media_type=video&clickOrigin=Media Grid&team=mlb&forwardUrl=http://m.mlb.com/tv/e{0}/v{1}/?&media_type=video&clickOrigin=Media%20Grid&team=mlb&template=mp5default&flowId=registration.dynaindex&mediaTypeTemplate=video'.format(event_id, content_id)
    }

    log("API call {0}\n{1}\n{2}\n{3}".format(url, params, headers, session.get_cookies()))
    s = requests.Session()
    s.cookies = session.get_cookies()
    r = s.get(url, params=params, headers=headers).json()
    if 'session_key' not in r or not r['session_key']:
        log("Couldn't find session key: {0}".format(r))
    else:
        log("get_session_key cookies response {0}".format(s.cookies))
        session.save_cookies(s.cookies)
        session_key = r['session_key']
        log("Session key: {0}".format(session_key))
        return session_key

    """
    cj = cookielib.LWPCookieJar(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'))
    cj.load(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'),ignore_discard=True)
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    epoch_time_now = str(int(round(time.time()*1000)))
    url = 'https://mlb-ws-mf.media.mlb.com/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    url = url + '?identityPointId='+identity_point_id
    url = url + '&fingerprint='+fingerprint
    url = url + '&eventId='+event_id
    url = url + '&subject=LIVE_EVENT_COVERAGE'
    url = url + '&platform=WIN8'
    url = url + '&frameworkURL=https://mlb-ws-mf.media.mlb.com&frameworkEndPoint=/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    url = url + '&_='+epoch_time_now

    req = urllib2.Request(url)
    req.add_header("Accept", "*/*")
    req.add_header("Accept-Encoding", "deflate")
    req.add_header("Accept-Language", "en-US,en;q=0.8")
    req.add_header("Connection", "keep-alive")
    req.add_header("User-Agent", UA_PC)
    req.add_header("Origin", "http://m.mlb.com")
    req.add_header("Referer", "http://m.mlb.com/tv/e"+event_id+"/v"+content_id+"/?&media_type=video&clickOrigin=Media Grid&team=mlb&forwardUrl=http://m.mlb.com/tv/e"+event_id+"/v"+content_id+"/?&media_type=video&clickOrigin=Media%20Grid&team=mlb&template=mp5default&flowId=registration.dynaindex&mediaTypeTemplate=video")

    log("API call {0}".format(req.get_full_url()))
    response = opener.open(req)
    xml_data = response.read()
    response.close()

    session_key = find(xml_data,'<session-key>','</session-key>')
    if not session_key:
        log("Couldn't find session key: {0}".format(xml_data))
    else:
        log("Session key: {0}".format(session_key))
    return session_key
    """
