from lib import log
from version import VERSION_FOR_BUG_REPORTS
from paths import CLIENT_LOG_PATH
log.set_version(VERSION_FOR_BUG_REPORTS)
log.add_secure_file_handler(CLIENT_LOG_PATH, "w")
log.add_http_handler("http://jlpo.free.fr/soundrts/metaserver")
log.add_console_handler()

import locale
try:
    locale.setlocale(locale.LC_ALL, '')
except:
    from lib.log import warning
    warning("couldn't set locale")

import os
import pickle
import sys
import time
import urllib

from clientmedia import voice, init_media, close_media
from clientmenu import Menu, input_string, END_LOOP
from clientserver import connect_and_play, start_server_and_connect
from clientversion import revision_checker
import config
from constants import MAIN_METASERVER_URL
from definitions import style
from game import TrainingGame, ReplayGame, reload_all
from lib.log import exception
from multimaps import worlds_multi
from msgs import nb2msg
from package import get_packages, get_all_packages_paths
from paths import REPLAYS_PATH, SAVE_PATH
import res
from singlemaps import campaigns
import stats
from version import compatibility_version


_ds = open("cfg/default_servers.txt").readlines()
_ds = [_x.split() for _x in _ds]
DEFAULT_SERVERS = [" ".join(["0"] + _x[:1] + [compatibility_version()] + _x[1:]) for _x in _ds]
SERVERS_LIST_HEADER = "SERVERS_LIST"
SERVERS_LIST_URL = MAIN_METASERVER_URL + "servers.php?header=%s&include_ports=1" % SERVERS_LIST_HEADER


class Application(object):

    def choose_server_ip_in_a_list(self):
        servers_list = None
        try:
            f = urllib.urlopen(SERVERS_LIST_URL)
            if f.read(len(SERVERS_LIST_HEADER)) == SERVERS_LIST_HEADER:
                servers_list = f.readlines()
        except:
            pass
        if servers_list is None:
            voice.alert([1029]) # hostile sound
            warning("couldn't get the servers list from the metaserver"
                    " => using the default servers list")
            servers_list = DEFAULT_SERVERS
        nb = 0
        menu = Menu()
        for s in servers_list:
            try:
                ip, version, login, port = s.split()[1:]
                # ignore the first parameter (time)
            except:
                warning("line not recognized from the metaserver: %s", s)
                continue
            nb += 1
            if version == compatibility_version():
                menu.append([login, 4073, login], (connect_and_play, ip, port))
        menu.title = nb2msg(len(menu.choices)) + [4078] + nb2msg(nb) + [4079]
        menu.append([4075, 4076], None)
        menu.run()

    def enter_server_ip(self):
        host = input_string([], "^[A-Za-z0-9\.]$")
        if host:
            connect_and_play(host)

    def multiplayer_menu(self):
        revision_checker.start_if_needed()
        if config.login == "player":
            voice.alert([4235]) # type your new login
            self.modify_login()
        menu = Menu([4030], [
            ([4119], self.choose_server_ip_in_a_list),
            ([4120], self.enter_server_ip),
            ([4048], None),
             ])
        menu.run()

    def restore_game(self):
        n = SAVE_PATH
        if not os.path.exists(n):
            voice.alert([1029]) # hostile sound
            return
        f = open(n)
        try:
            i = int(stats.Stats(None, None)._get_weak_user_id())
            j = int(f.readline())
        except:
            i = 0
            j = "error"
        if i == j:
            try:
                game_session = pickle.load(f)
            except:
                exception("cannot load savegame file")
                voice.alert([1029]) # hostile sound
                return
            game_session.run_on()
        else:
            warning("savegame file is not from this machine")
            voice.alert([1029]) # hostile sound

    def training_menu_invite(self, ai_type):
        self.players.append(ai_type)
        self.factions.append("random_faction")
        self.menu.update_menu(self.build_training_menu_after_map())

    def training_menu_after_map(self, m):
        style.load(res.get_text("ui/style", append=True, locale=True)) # XXX: won't work with factions defined in the map
        self.players = [config.login]
        self.factions = ["random_faction"]
        self.map = m
        self.menu = self.build_training_menu_after_map()
        self.menu.loop()

    def start_training_game(self):
        game = TrainingGame(self.map, self.players)
        game.factions = self.factions
        game.run()
        return END_LOOP

    def set_faction(self, pn, r):
        self.factions[pn] = r
        self.menu.update_menu(self.build_training_menu_after_map())

    def _add_faction_menu(self, menu, pn, p, pr):
        if len(self.map.factions) > 1:
            for r in ["random_faction"] + self.map.factions:
                if r != pr:
                    menu.append([p,] + style.get(r, "title"),
                                (self.set_faction, pn, r))

    def build_training_menu_after_map(self):
        menu = Menu()
        if len(self.players) < self.map.nb_players_max:
            menu.append([4058, 4258], (self.training_menu_invite, "easy"))
            menu.append([4058, 4257], (self.training_menu_invite,
                                       "aggressive"))
        if len(self.players) >= self.map.nb_players_min:
            menu.append([4059], self.start_training_game)
        for pn, (p, pr) in enumerate(zip(self.players, self.factions)):
            self._add_faction_menu(menu, pn, p, pr)
        menu.append([4048, 4060], END_LOOP)
        return menu

    def training_menu(self):
        menu = Menu([4055], remember="mapmenu")
        for m in worlds_multi():
            menu.append(m.title, (self.training_menu_after_map, m))
        menu.append([4041], None)
        menu.run()

    def replay(self, n):
        ReplayGame(os.path.join(REPLAYS_PATH, n)).run()

    def replay_menu(self):
        menu = Menu([4315])
        for n in sorted(os.listdir(REPLAYS_PATH), reverse=True):
            if n.endswith(".txt"):
                menu.append([time.strftime("%c", time.localtime(int(n[:-4])))], (self.replay, n))
        menu.append([4041], None)
        menu.run()

    def manage_packages(self):

        def add():
            menu = Menu([4325])
            for p in get_packages():
                if not p.is_active:
                    menu.append([p.name], (p.add, voice))
            menu.append([4118], None)
            menu.run()

        def deactivate():
            menu = Menu([4326])
            for p in get_packages():
                if p.is_active:
                    menu.append([p.name], p.deactivate)
            menu.append([4118], None)
            menu.run()

        def update():
            menu = Menu([4327])
            for p in get_packages():
                if p.is_active:
                    menu.append([p.name], (p.update, voice))
            menu.append([4118], None)
            menu.run()

        menu = Menu([4324], [
            ([4325], add),
            ([4326], deactivate),
            ([4327], update),
            ([4076], END_LOOP),
            ])
        menu.loop()
        reload_all()

    def modify_login(self):
        login = input_string([4235, 4236], "^[a-zA-Z0-9]$") # type your new
                                        # login ; use alphanumeric characters
        if login == None:
            voice.alert([4238]) # current login kept
        elif (len(login) < 1) or (len(login) > 20):
            voice.alert([4237, 4238]) # incorrect login ; current login kept
        else:
            voice.alert([4239, login]) # new login:
            config.login = login
            config.save()

    def modify_default_mods(self):

        def available_mods():
            result = []
            for path in get_all_packages_paths():
                mods_path = os.path.join(path, "mods")
                for mod in os.listdir(mods_path):
                    if os.path.isdir(os.path.join(mods_path, mod)) \
                       and mod not in result and mod not in mods:
                        result.append(mod)
            return result

        def select_next_mod(parent):

            def add_mod(mod):
                if mod not in mods:
                    mods.append(mod)
                    parent.title = mods

            menu = Menu([4320] + mods)
            for mod in available_mods():
                menu.append([mod], (add_mod, mod))
            menu.append([4118], None)
            menu.run()

        def save():
            previous_mods = config.mods
            config.config_mods = ",".join(mods)
            config.mods = config.config_mods
            config.save()
            if config.mods != previous_mods:
                reload_all()
            return END_LOOP

        mods = []
        menu = Menu([4321]) # the list is empty
        menu.append([4320], (select_next_mod, menu))
        menu.append([4096], save)
        menu.append([4098], END_LOOP)
        menu.loop()

    def main(self):
        single_player_menu = Menu([4030],
            [(c.title, c) for c in campaigns()] +
            [
            ([4055], self.training_menu),
            ([4113], self.restore_game),
            ([4118], END_LOOP),
            ])
        server_menu = Menu([4043], [
            ([4044, 4045], (start_server_and_connect, "admin_only")),
            ([4046, 4047], (start_server_and_connect, "")),
            ([4121, 4122], (start_server_and_connect,
                            "admin_only no_metaserver")),
            ([4048], None),
            ])
        options_menu = Menu([4086], [
            ([4087], self.modify_login),
            ([4319], self.modify_default_mods),
            [[4323], self.manage_packages],
            ([4118], END_LOOP),
            ])
        main_menu = Menu([4029, 4030], [
            [[4031, 4032], single_player_menu.loop],
            [[4033, 4034], self.multiplayer_menu],
            [[4035, 4036], server_menu],
            [[4315], self.replay_menu],
            [[4037, 4038], options_menu.loop],
            [[4041, 4042], END_LOOP],
            ])
        if "connect_localhost" in sys.argv:
            connect_and_play()
        else:
            main_menu.loop()


def main():
    try:
        try:
            init_media()
            revision_checker.start_if_needed()
            Application().main()
        except SystemExit:
            raise
        except:
            exception("error")
    finally:
        close_media()


if __name__ == "__main__":
    main()
