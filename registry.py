from collections import defaultdict
from youtube_api import YoutubeAPI
import time

class Song():
    def __init__(self, search_title):
        self.played = False
        self.urls = YoutubeAPI().get_top_search_results(search_title) # URLs of top matches based on the given title.
        self.title = YoutubeAPI().get_first_title(self.urls[0])

class Channel():
    def __init__(self, voice_channel, text_channel):
        self.voice = voice_channel
        self.text = text_channel
        self.queue = []
        self.previous = False
        self.cur_song_idx = None
        self.last_active = time.time()

    def add_to_queue(self, title):
        self.queue.append(Song(title))

    def play_previous(self):
        if self.cur_song_idx > 0:
            self.previous = True
            return True
        else:
            return False

class Server():
    def __init__(self, guild):
        self.guild = guild
        self.channel = None # Mapping from a channel id to a Channel

class Registry():
    def __init__(self):
        self.servers = defaultdict() # Mapping from a server id to a Server instance
    
    def add_channel(self, guild, voice_channel, text_channel):
        if guild.id not in self.servers:
            self.servers[guild.id] = Server(guild)
        self.servers[guild.id].channel = Channel(voice_channel, text_channel)
    
    def leave_channel(self, server_id):
        try:
            del self.servers[server_id]
        except:
            print("Channel not found")

    def channel_exists(self, server_id, channel_id):
        try:
            return self.servers[server_id].channel.voice.id == channel_id
        except:
            return False 
        
    
    def get_current_song_title(self, voice_client, server_id):
        chan = self.servers[server_id].channel
        idle = not (voice_client.is_playing() or voice_client.is_paused())
        if idle:
            return ""
        return self.servers[server_id].channel.queue[chan.cur_song_idx].title
    
    def skip_whole_queue(self, server_id):
        self.servers[server_id].channel.cur_song_id = len(self.servers[server_id].channel.queue) -1

    def get_next_song(self, server_id):
        chan = self.servers[server_id].channel
        if chan.previous:
            self.servers[server_id].channel.previous = False
            if chan.cur_song_idx != len(self.servers[server_id].channel.queue)-1: #if the last song played is not the last song in queue
                self.servers[server_id].channel.cur_song_idx-=1
            return self.servers[server_id].channel.queue[chan.cur_song_idx]

        if chan.cur_song_idx is None:
            if len(chan.queue) > 0: #for the very first time at the first song in queue, where cur_song_indx is None
                self.servers[server_id].channel.cur_song_idx = 0
                return self.servers[server_id].channel.queue[0]
            else:
                return None

        if chan.cur_song_idx >= len(chan.queue)-1:
            return None
            
        self.servers[server_id].channel.cur_song_idx+=1
        return self.servers[server_id].channel.queue[self.servers[server_id].channel.cur_song_idx]

    def play_previous(self, server_id, channel_id):
        return self.servers[server_id].channel.play_previous()