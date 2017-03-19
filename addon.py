from xbmcswift2 import Plugin, actions
from xbmcswift2 import xbmcgui, xbmc, xbmcaddon
import mlb_player
import requests
import cookielib
import urllib2
import urllib
import time
import datetime
import os
import json
import StorageServer

plugin = Plugin()

ADDON_PATH_PROFILE = xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
UA_PC = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.97 Safari/537.36'
UA_PS4 = 'PS4Application libhttp/1.000 (PS4) libhttp/3.15 (PlayStation 4)'

cache = StorageServer.StorageServer("plugin.video.mlbbasesloaded", 24)

@plugin.route('/')
def index():
    item = {
        'label': 'Play BasesLoaded',
        'path': plugin.url_for(play_basesloaded.__name__)
    }
    return plugin.finish([item])

@plugin.route('/basesloaded')
def play_basesloaded():
    import get_scores
    import datetime

    li_csv_path =  plugin.addon.getAddonInfo('path') + "/resources/li.csv"
    # TODO be weary of timezone issues with datetime.today()
    # also, need a way of checking if there are any current games, not just
    # games that are currently *on*
    games = get_scores.best_games(datetime.datetime.today(), li_csv_path)
    if games is None:
        plugin.notify("No current games found")
        return

    # item = {
    #     'label': 'Test video',
    #     'path': 'http://s3.amazonaws.com/KA-youtube-converted/JwO_25S_eWE.mp4/JwO_25S_eWE.mp4',
    #     'is_playable': True
    # }
    # return plugin.finish([item])
    # plugin.set_resolved_url(item)

    monitor = xbmc.Monitor()
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    player = mlb_player.MlbPlayer(mlb_playlist=playlist)

    curr_game = None
    streams_not_found = set([])
    # Since MLB API is ~20 seconds in the future of MLB.tv,
    # we'll store the API result and use in the next 20 sec
    # iteration.
    # TODO hit API every 10 seconds, then keep a history array
    # and figure out what actual MLB.tv delay is (via experimentation)
    # and make sure to index back in time to the history array
    future_best_games = games
    while True:
        #actions.update_view('http://mlblive-akc.mlb.com/ls01/mlbam/2016/06/11/MLB_GAME_VIDEO_NYNMIL_HOME_20160611_1/5000K/5000_complete.m3u8|User-Agent=PS4Application libhttp/1.000 (PS4) libhttp/3.15 (PlayStation 4)&Cookie=mediaAuth=a06e2dc0e366b956c91a6e3cab8762e8677e91491a59d08b2ba6bb275ebd21dac00706c60d3f70e6fd4e8ba8ec41006a4577af1482249072a6b9389f8d5e274315692ff6ac9faf580f5d54ec0746e55783c0e07b46a61ba5874467188fd42473eb27c5a225b94eb24a893119de0d00a219ddac26d3a0e9eb7996359b694e2d30edd81deda5b777bec0215880c6bc06a97171d829dc567be8630db9682068318864b81c1c4174ede7f622446a1c225ac0b000d6e76da32cce94629e235f50307aa7c99058621166f6ea7c0117b4e587a4420e0a886d8d091f277685e826c4ab7f064faad8aff116bb29e83b1e256ddcd8')
        # TODO be weary of timezone issues with datetime.today()
        games = future_best_games
        future_best_games = get_scores.best_games(datetime.datetime.today(), li_csv_path)
        if not games:
            # TODO better UX for this situation
            log("No game found")
            xbmc.sleep(5000)
            continue

        # Update state of curr_game
        if curr_game is not None:
            new_curr_game = [game for game in games if game['state'].away_team == curr_game['state'].away_team
                                                   and game['state'].home_team == curr_game['state'].home_team]
            if not new_curr_game:
                curr_game = None
            else:
                curr_game = new_curr_game[0]

        # Iterate through best games in order, choosing first one a stream exists for
        for game in games:
            if curr_game == game:
                log("Not switching because current game is still best game")
                break

            try:
                # Only switch games if:
                #  curr_game is None (either no curr_game or it's in commercial break)
                #  The change in leverage is > 1.5 and there's a new batter in curr_game
                if curr_game is None or ((game['leverage_index'] - curr_game['leverage_index'] > 1.5) and curr_game['state'].new_batter):
                    if (game['state'].home_team, game['state'].away_team) in streams_not_found:
                        log("Already know stream doesn't exist for game {0}".format(game))
                        continue

                    stream = cache.cacheFunction(get_stream, game['state'])
                    log("Switching from {0} to {1}".format(curr_game, game))
                    curr_game = game
                    log("stream: " + stream)
                    player.play_video(stream)

                if curr_game == game:
                    log("Current game is in commercial break or is over")
                if curr_game != game and (game['leverage_index'] - curr_game['leverage_index']) <= 1.5:
                    log("{0} is better game, but not enough better to switch from {1}".format(game, curr_game))
                elif curr_game != game and (game['leverage_index'] - curr_game['leverage_index']) > 1.5:
                    log("{0} is a better game, but {1} still has a batter at the plate".format(game, curr_game))

                break
            except StreamNotFoundException:
                streams_not_found.add((game['state'].home_team, game['state'].away_team),)
                log("Stream not found for {0}. Setting cache to {1}".format(game, streams_not_found))
                continue

        # NOTE there's a bug where if you play some other video after stopping this one within 20 seconds you'll get fucked
        if monitor.waitForAbort(20.0) or not player.isPlayingVideo():
            break

def log(string):
    print "plugin.video.mlbbasesloaded: {0}".format(string)

class StreamNotFoundException(Exception): pass

def get_stream(game):
    # from grid_ce.json get calendar_event_id (event_id) and id (content_id)
    # and ['game_media']['homebase']['media']
    url = 'http://gdx.mlb.com/components/game/mlb/{0}/grid_ce.json'.format(datetime.datetime.today().strftime(u'year_%Y/month_%m/day_%d'))
    streams = requests.get(url).json()

    stream_to_goto = None
    for stream in streams['data']['games']['game']:
        if stream['home_name_abbrev'] == game.home_team and stream['away_name_abbrev'] == game.away_team:
            stream_to_goto = stream
            break

    if stream_to_goto is None:
        plugin.notify("Can't find stream for game between {0} and {1}".format(game['away_team'], game['home_team']))
        return

    id = stream_to_goto['id']
    event_id = stream_to_goto['calendar_event_id']
    try:
        # Searching for type = 'mlbtv_home' or 'mlbtv_away' will allow choosing
        # which stream to take. Maybe use broadcast rankings to determine?
        content_id = stream_to_goto['game_media']['homebase']['media'][0]['id']
    except KeyError:
        raise StreamNotFoundException()

    if need_new_cookie():
        login()

    cj = cookielib.LWPCookieJar(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'))
    cj.load(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'),ignore_discard=True)
    for cookie in cj:
        if cookie.name == "ipid":
            identity_point_id = cookie.value
        elif cookie.name == "fprt":
            fingerprint = cookie.value

    session_key = cache.cacheFunction(get_session_key, identity_point_id, fingerprint, event_id, content_id)

    if not session_key or session_key == 'blackout':
        raise StreamNotFoundException()

    url = cache.cacheFunction(get_url, identity_point_id, fingerprint, content_id, session_key, event_id)
    return url

def need_new_cookie():
    expired_cookies = True
    try:
        cj = cookielib.LWPCookieJar(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'))
        cj.load(os.path.join(ADDON_PATH_PROFILE, 'cookies.lwp'),ignore_discard=True)

        #Check if cookies have expired
        at_least_one_expired = False
        num_cookies = 0
        for cookie in cj:
            num_cookies += 1
            if cookie.is_expired():
                at_least_one_expired = True
                break

        if not at_least_one_expired:
            expired_cookies = False
    except:
        pass

    if expired_cookies or num_cookies == 0:
        #Remove cookie file
        cookie_file = xbmc.translatePath(os.path.join(ADDON_PATH_PROFILE+'cookies.lwp'))
        try:
            os.remove(cookie_file)
        except:
            pass

    return expired_cookies

def get_url(identity_point_id, fingerprint, content_id, session_key, event_id):
    '''
    url = 'https://mlb-ws-mf.media.mlb.com/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    params = {
        'identityPointId': identity_point_id,
        'fingerprint': fingerprint,
        'contentId': content_id,
        'playbackScenario': 'HTTP_CLOUD_WIRED_60',
        'subject': 'LIVE_EVENT_COVERAGE',
        'platform': 'PS4',
        'sessionKey': session_key,
        '_': time.time() * 1000,
        'format': 'json'
    }

    r = requests.get(url, params=params).json()
    print r
    if r['status_code'] != 1:
        dialog = xbmcgui.Dialog()
        dialog.ok('Error starting stream', r['status_message'])
        return
    else:
        url = r['user_verified_event'][0]['user_verified_content'][0]['user_verified_media_item'][0]['url']
        UA_PS4 = 'PS4Application libhttp/1.000 (PS4) libhttp/3.15 (PlayStation 4)'
        url = url + '|User-Agent='+UA_PS4+'&Cookie='+media_auth
        return url
    '''
    # TODO copy over from other project to get cookie jar with media auth
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

def get_session_key(identity_point_id, fingerprint, event_id, content_id):
    '''
    url = 'https://mlb-ws-mf.media.mlb.com/pubajaxws/bamrest/MediaService2_0/op-findUserVerifiedEvent/v-2.3'
    params = {
        'identityPointId': identity_point_id,
        'fingerprint': fingerprint,
        'eventId': event_id,
        'subject': 'LIVE_EVENT_COVERAGE',
        'platform': 'PS4',
        '_': time.time() * 1000,
        'format': 'json'
    }

    r = requests.get(url, params=params)
    print r.json()
    print r.cookies
    return r.json()['session_key']
    '''
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

def find(source,start_str,end_str):
    start = source.find(start_str)
    end = source.find(end_str,start+len(start_str))

    if start != -1:
        return source[start+len(start_str):end]
    else:
        return ''

def login():
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

if __name__ == '__main__':
    plugin.run()
