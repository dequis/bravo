import math

from zope.interface import implements
from twisted.internet import reactor

from bravo.blocks import blocks, items
from bravo.config import configuration
from bravo.ibravo import IChatCommand, IConsoleCommand, ISeason
from bravo.plugin import retrieve_plugins, retrieve_named_plugins
from bravo.plugin import PluginException
from bravo.packets import make_packet
from bravo.utilities import split_time

def parse_player(factory, name):
    if name in factory.protocols:
        return factory.protocols[name]
    else:
        raise Exception("Couldn't find player %s" % name)

def parse_block(block):
    """
    Get the key for a given block/item.
    """

    try:
        if block.startswith("0x"):
            return (int(block, 16), 0)
        else:
            return (int(block), 0)
    except ValueError:
        if block in blocks:
            return blocks[block].key
        elif block in items:
            return items[block].key
        else:
            raise Exception("Couldn't parse block %s!" % block)

def parse_int(i):
    try:
        return int(i)
    except ValueError:
        raise Exception("Couldn't parse quantity %s!" % i)

class Help(object):

    implements(IChatCommand, IConsoleCommand)

    def dispatch(self, plugins):
        l = []

        # This is fairly brute-force and inelegant. I'm very open to
        # suggestions on improving it.
        for plugin in set(plugins.itervalues()):
            usage = "%s %s" % (plugin.name, plugin.usage)
            l.append((plugin.name, usage, plugin.info))
            for alias in plugin.aliases:
                alias_usage = usage.replace(plugin.name, alias)
                info = "Alias for %s" % plugin.name
                l.append((alias, alias_usage, info))

        name_pad = max(len(i[0]) for i in l) + 1
        usage_pad = max(len(i[1]) for i in l) + 1

        yield "%s %s %s" % ("Name:".ljust(name_pad),
            "Usage:".ljust(usage_pad), "Info:")

        for name, usage, info in sorted(l):
            yield "%s %s %s" % (name.ljust(name_pad), usage.ljust(usage_pad),
                info)

    def chat_command(self, factory, username, parameters):
        for i in self.dispatch(retrieve_plugins(IChatCommand)):
            yield i

    def console_command(self, factory, parameters):
        for i in self.dispatch(retrieve_plugins(IConsoleCommand)):
            yield i

    name = "help"
    aliases = tuple()
    usage = ""
    info = "Prints this message"

class List(object):

    implements(IChatCommand, IConsoleCommand)

    def dispatch(self, factory):
        yield "Connected players: %s" % (", ".join(
                player for player in factory.protocols))

    def chat_command(self, factory, username, parameters):
        for i in self.dispatch(factory):
            yield i

    def console_command(self, factory, parameters):
        for i in self.dispatch(factory):
            yield i

    name = "list"
    aliases = ("playerlist",)
    usage = ""
    info = "Lists the currently connected players"

class Time(object):

    implements(IChatCommand, IConsoleCommand)

    def dispatch(self, factory):
        hours, minutes = split_time(factory.time)

        # Find seasons, and figure out which season we're in.
        seasons = retrieve_plugins(ISeason).values()
        seasons.sort(reverse=True, key=lambda season: season.day)
        if seasons:
            if all(s.day > factory.day for s in seasons):
                # We are too close to the beginning of the year; grab the last
                # season of "last" year.
                date = "%d (%d %s)" % (factory.day,
                    factory.day + 360 - seasons[0].day, seasons[0].name)
            else:
                # Grab the closest season, Price-is-Right-style.
                season = (s for s in seasons if s.day <= factory.day).next()
                date = "%d (%d %s)" % (factory.day, factory.day - season.day,
                    season.name)
        else:
            date = "%d" % factory.day
        yield "%02d:%02d, %s" % (hours, minutes, date)

    def chat_command(self, factory, username, parameters):
        for i in self.dispatch(factory):
            yield i

    def console_command(self, factory, parameters):
        for i in self.dispatch(factory):
            yield i

    name = "time"
    aliases = ("date",)
    usage = ""
    info = "Gives the current in-game time and date"

class Say(object):

    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        message = "[Server] %s" % " ".join(parameters)
        yield message
        packet = make_packet("chat", message=message)
        factory.broadcast(packet)

    name = "say"
    aliases = tuple()
    usage = "<message>"
    info = "Broadcasts a message to everybody"

class Give(object):

    implements(IChatCommand, IConsoleCommand)

    def chat_command(self, factory, username, parameters):
        if len(parameters) == 1:
            block = parameters[0]
            count = 1
        elif len(parameters) == 2:
            block = parameters[0]
            count = parameters[1]
        else:
            block = " ".join(parameters[:-1])
            count = parameters[-1]

        player = parse_player(factory, username)
        block = parse_block(block)
        count = parse_int(count)

        x = player.player.location.x
        y = player.player.location.y
        z = player.player.location.z
        theta = player.player.location.theta

        # Do some trig to put the pickup two blocks ahead of the player in the
        # direction they are facing. Note that all three coordinates are
        # "misnamed;" the unit circle actually starts at (0, 1) and goes
        # *backwards* towards (-1, 0).
        x -= 2 * math.sin(theta)
        y += 1
        z += 2 * math.cos(theta)

        coords = int(x * 32), int(y * 32), int(z * 32)

        factory.give(coords, block, count)

        # Return an empty tuple for iteration
        return tuple()

    def console_command(self, factory, parameters):
        for i in self.chat_command(factory, parameters[0], parameters[1:]):
            yield i

    name = "give"
    aliases = tuple()
    usage = "<block> <quantity>"
    info = "Gives a number of blocks or items to a certain player"

class Quit(object):
    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        # Let's shutdown!
        message = "Server shutting down."
        yield message

        # Use an error packet to kick clients cleanly.
        packet = make_packet("error", message=message)
        factory.broadcast(packet)

        yield "Saving all chunks to disk..."
        for chunk in factory.world.dirty_chunk_cache.itervalues():
            factory.world.save_chunk(chunk)

        yield "Halting."
        reactor.stop()

    name = "quit"
    aliases = ("exit",)
    usage = ""
    info = "Quits the server"

class SaveAll(object):

    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        yield "Flushing all chunks..."

        for chunk in factory.world.chunk_cache.itervalues():
            factory.world.save_chunk(chunk)

        yield "Save complete!"

    name = "save-all"
    aliases = tuple()
    usage = ""
    info = "Saves all world data to disk"

class SaveOff(object):

    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        yield "Disabling saving..."

        factory.world.save_off()

        yield "Saving disabled. Currently running in memory."

    name = "save-off"
    aliases = tuple()
    usage = ""
    info = "Disables saving of world data to disk"

class SaveOn(object):

    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        yield "Enabling saving (this could take a bit)..."

        factory.world.save_on()

        yield "Saving enabled."

    name = "save-on"
    aliases = tuple()
    usage = ""
    info = "Enables saving of world data to disk"

class WriteConfig(object):

    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        f = open("".join(parameters), "w")
        configuration.write(f)
        f.close()
        yield "Configuration saved."

    name = "write-config"
    aliases = tuple()
    usage = ""
    info = "Saves configuration to disk"

class Season(object):

    implements(IConsoleCommand)

    def console_command(self, factory, parameters):
        wanted = " ".join(parameters)
        try:
            season = retrieve_named_plugins(ISeason, [wanted])[0]
        except PluginException:
            yield "Couldn't find season %s" % wanted
            return

        msg = "Changing season to %s..." % wanted
        yield msg
        factory.day = season.day
        factory.update_season()
        yield "Season successfully changed!"

    name = "season"
    aliases = tuple()
    usage = "<season>"
    info = "Advance date to the beginning of the given season"

class Me(object):
    implements(IChatCommand)

    def dispatch(self, username, says):
        say = " ".join(says)
        msg = "* %s %s" % (username,say)
        yield msg

    def chat_command(self, factory, username, parameters):
        for i in self.dispatch(username, parameters):
            yield i

    name = "me"
    aliases = tuple()
    usage = "<message>"
    info = "/me like IRC"

class Kick(object):
    """
    /kick those players who should be kicked.

    With great power comes greate responsibility, use this wisely.
    """

    implements(IConsoleCommand)

    def dispatch(self, factory, parameters):
        player = parse_player(factory, parameters[0])
        if len(parameters) == 1:
            msg = "%s has been kicked." % parameters[0]
        elif len(parameters) > 1:
            reason = " ".join(parameters[1:])
            msg = "%s has been kicked for %s" % (parameters[0],reason)
        packet = make_packet("error", message=msg)
        player.transport.write(packet)
        yield msg

    def console_command(self, factory, parameters):
        for i in self.dispatch(factory, parameters):
            yield i

    name = "kick"
    aliases = tuple()
    usage = "<player> [<reason>]"
    info = "Kicks <player> from the server"

class GetPos(object):

    implements(IChatCommand)

    def chat_command(self, factory, username, parameters):
        player = parse_player(factory, username)
        l = player.player.location
        locMsg = "Your location is <%d, %d, %d>" % (l.x, l.y, l.z)
        yield locMsg

    name = "getpos"
    aliases = tuple()
    usage = ""
    info = "Hey0 /getpos"

help = Help()
list = List()
time = Time()
say  = Say()
give = Give()
quit = Quit()
save_all = SaveAll()
save_off = SaveOff()
save_on = SaveOn()
write_config = WriteConfig()
season = Season()
me = Me()
kick = Kick()
getpos = GetPos()
