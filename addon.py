from xbmcswift2 import Plugin
from xbmcswift2 import xbmc
import mlb_player
import datetime
import mlbtv_stream_api
from utils import *
import mlb_exceptions
from globals import *

plugin = Plugin()

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

    li_csv_path =  plugin.addon.getAddonInfo('path') + "/resources/li.csv"
    # TODO be weary of timezone issues with datetime.today()
    # also, need a way of checking if there are any current games, not just
    # games that are currently *on*
    games = get_scores.best_games(datetime.datetime.today(), li_csv_path)
    if games is None:
        plugin.notify("No games on")
        return

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
        # TODO be weary of timezone issues with datetime.today()
        # TODO encapsulate all this logic in an object
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

                    stream = mlbtv_stream_api.get_stream(game['state'].home_team, game['state'].away_team)

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
            except mlb_exceptions.StreamNotFoundException:
                streams_not_found.add((game['state'].home_team, game['state'].away_team),)
                log("Stream not found for {0}. Setting cache to {1}".format(game, streams_not_found))
                continue

        # NOTE there's a bug where if you play some other video after stopping this one within 20 seconds you'll get in trouble
        if monitor.waitForAbort(20.0) or not player.isPlayingVideo():
            break

if __name__ == '__main__':
    plugin.run()
