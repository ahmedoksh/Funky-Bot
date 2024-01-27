from youtube_api import YoutubeAPI
import time
import discord
from typing import List, Dict


class Song:
    """Represents a song with its YouTube URLs and title."""
    
    def __init__(self, search_title: str):
        """
        Initializes a Song instance.

        Args:
            search_title (str): The title of the song to search on YouTube.
        """
        # get URLs of top matches based on the given title
        self.urls = YoutubeAPI().get_top_search_results(search_title)  
        self.title = YoutubeAPI().get_first_title(search_title)


class Channel:
    """Represents a voice and text channel in a Discord server."""

    def __init__(
        self, 
        voice_channel: discord.channel.VoiceChannel,
        text_channel: discord.channel.TextChannel
        ):
        """
        Initializes a Channel instance.

        Args:
            voice_channel (discord.channel.VoiceChannel): The voice channel in the server.
            text_channel (discord.channel.TextChannel): The text channel in the server.
        """
        self.voice = voice_channel
        self.text = text_channel
        self.queue: List[Song] = []
        self.previous = False
        self.cur_song_idx = None
        self.last_active = time.time()

    def add_to_queue(self, title: str) -> None:
        '''Adds a Song object to the queue'''
        self.queue.append(Song(title))

    def play_previous(self) -> bool:
        '''Plays the previous song in the queue
        The function is used to turn the flag of previous to true if it 
        can play the previous song, and return True otherwise return False.
        '''
        if self.cur_song_idx is not None and self.cur_song_idx > 0:
            self.previous = True
            return True
        else:
            return False


class Server:
    """Represents a Discord server with a voice and text channel."""

    def __init__(self, guild: discord.guild.Guild):
        """
        Initializes a Server instance.

        Args:
            guild (discord.guild.Guild): The Discord server.
        """
        self.guild = guild
        self.channel = None


class Registry:
    """Manages the servers and their associated channels."""

    def __init__(self):
        """Initializes a Registry instance."""
        self.servers: Dict[int, Server] = {}  # Mapping from a server id to a Server instance

    def add_channel(
        self,
        guild: discord.guild.Guild, # guild is a server
        voice_channel: discord.channel.VoiceChannel,
        text_channel: discord.channel.TextChannel,
    ) -> None:
        '''Adds a Server instance to the registry
        Args:
            guild: The server to be added
            voice_channel: The voice channel to join in the server
            text_channel: The text channel to send messages in the server
        '''
        if guild.id not in self.servers:
            self.servers[guild.id] = Server(guild)
        self.servers[guild.id].channel = Channel(voice_channel, text_channel)

    def leave_channel(self, server_id: int) -> None:
        '''Removes a Server instance from the registry
        Args:
            server_id: The id of the server
        '''
        if server_id in self.servers:
            del self.servers[server_id]
        else:
            print("Channel not found")

    def channel_exists(self, server_id: int, channel_id: int) -> bool:
        '''Checks if a channel exists in the registry
        Args:
            server_id: The id of the server
            channel_id: The id of the channel
        returns:
            bool: True if the channel exists, False otherwise
        '''
        if server_id not in self.servers:
            return False
        else:
            return self.servers[server_id].channel.voice.id == channel_id

    def get_current_song_title(
        self, voice_client: discord.voice_client.VoiceClient, server_id: int
    ) -> str:
        '''Returns the title of the current song
        Args:
            voice_client: The voice client of the bot
            server_id: The id of the server
        Returns:
            str: The title of the current song if there isn't any song playing it returns an empty string
        '''
        chan = self.servers[server_id].channel
        idle = not (voice_client.is_playing() or voice_client.is_paused())
        if idle:
            return ""
        return self.servers[server_id].channel.queue[chan.cur_song_idx].title

    def get_next_song(self, server_id: int) -> Song:
        '''Returns the next song to be played
        The function is used to get the next song to be played, and update the current song index.
        Args:
            server_id: The id of the server
        Returns:
            Song: if previous flag is true it returns the previous song, other wise next song in queue
        '''
        chan = self.servers[server_id].channel
        
        # if previous flag is true play the previous song
        if chan.previous:
            chan.previous = False
            chan.cur_song_idx -= 1
            return chan.queue[chan.cur_song_idx]

        # if it is the first song to be added in the queue
        if chan.cur_song_idx is None:
            if len(chan.queue) > 0:
                chan.cur_song_idx = 0
                return chan.queue[0]
            else:
                return None

        # if it is the last song in the queue so no next song
        if chan.cur_song_idx >= len(chan.queue) - 1:
            return None

        chan.cur_song_idx += 1
        return chan.queue[chan.cur_song_idx]

    def play_previous(self, server_id: int) -> bool:
        '''Plays the previous song in the queue
        Returns:
            bool: True if it can play the previous song, False otherwise
        '''
        return self.servers[server_id].channel.play_previous()
