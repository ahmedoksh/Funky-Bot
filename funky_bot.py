from discord.ext import commands, tasks
import discord
from registry import Registry
from youtube_dl import YoutubeDL
from lyricsgenius import Genius
import time
import json
from youtube_api import YoutubeAPI


class FunkyBot(commands.Bot):
    def __init__(self, command_prefix, genius_token):
        commands.Bot.__init__(self, command_prefix=command_prefix, help_command=None )
        self.registry = Registry()
        self.ydl_options = {'format': 'bestaudio', 'noplaylist':'True'}
        self.ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        self.add_commands()
        self.genius_token = genius_token

    async def on_ready(self):
        self.play_loop.start()
        self.gc_inactive_channels.start()
        print("bot is ready")
    
    async def valid_voice_channel(self, ctx):
        if not ctx.author.voice:
            await ctx.reply("Connect to a voice channel before calling me.")    
            return False
        elif not self.registry.channel_exists(ctx.guild.id, ctx.author.voice.channel.id):
            return False
        return True
    
    def add_commands(self):

        @self.command()
        async def leave(ctx):
            voice_channel_is_valid = await self.valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return
            
            await ctx.reply('See you later ;(')
            self.registry.leave_channel(ctx.guild.id)
            await ctx.guild.voice_client.disconnect()

        @self.command()
        async def lyrics(ctx):
            voice_channel_is_valid = await self.valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            voice_instance = self.registry.servers[ctx.guild.id].guild.voice_client
            title = self.registry.get_current_song_title(voice_instance, ctx.guild.id)
            if title != "":  
                genius = Genius(self.genius_token)
                song = genius.search_song(title)
                if not song:
                    await ctx.send("I can't find lyrics :(")
                    return

                if not song.lyrics:
                    await ctx.send("I can't find lyrics :(")
                    return 

                lyrics = song.lyrics.split("\n")
                paragraph = []
                paragraph_length = 0
                max_len = 1500
                for line in lyrics:
                    # sending the lyrics in multiple messages with each of maximum lentgh of 1500 characters    
                    if line == "": # in order to send empty lines
                        line = "** **"

                    if paragraph_length + len(line) < max_len:
                        paragraph.append(line)
                        paragraph_length += len(line)
                    else:
                        message='\n'.join(paragraph)
                        await ctx.send(message)
                        paragraph = []
                        paragraph_length = 0 

                        paragraph.append(line)
                        paragraph_length += len(line)
                    
                    if line == lyrics[-1]: # checks if it is the last line in lyrics
                        message='\n'.join(paragraph)
                        await ctx.send(message)

        @self.command()
        async def pause(ctx):
            voice_channel_is_valid = await self.valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            voice_client = ctx.message.guild.voice_client
            if voice_client.is_playing():
                voice_client.pause()
                await ctx.send("paused")

        @self.command()
        async def resume(ctx):
            voice_channel_is_valid = await self.valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return
                
            voice_client = ctx.message.guild.voice_client
            if not voice_client.is_playing():
                voice_instance = self.registry.servers[ctx.guild.id].guild.voice_client
                await ctx.send("Resuming " + self.registry.get_current_song_title(voice_instance, ctx.guild.id))
                voice_client.resume()

        @self.command()
        async def skip(ctx, action=""):
            voice_channel_is_valid = await self.valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            # skip everything if 'all' is passed.
            if action == "all":
                self.registry.skip_whole_queue(ctx.guild.id, ctx.author.voice.channel.id)

            voice_client = ctx.message.guild.voice_client
            if voice_client.is_playing():
                voice_client.stop()
                await ctx.send('Skipping')
            
        @self.command()
        async def play(ctx, *, title=""):
            if not ctx.author.voice:
                await ctx.reply("Connect to a voice channel before calling me.")    
                return

            elif  ctx.guild.id in self.registry.servers and not self.registry.channel_exists(ctx.guild.id, ctx.author.voice.channel.id) : #disconnect from current channel and go to the other channel ####### also the bot can be conneceted to only one channel
                voice_client = self.registry.servers[ctx.guild.id].guild.voice_client
                self.registry.leave_channel(ctx.guild.id)
                await voice_client.disconnect()
                await ctx.author.voice.channel.connect()
                await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_mute = False, self_deaf=True)  #deafen the bot 
                self.registry.add_channel(ctx.guild, ctx.author.voice.channel, ctx.message.channel)  
                
            elif not self.registry.channel_exists(ctx.guild.id, ctx.author.voice.channel.id):
                await ctx.reply('Glad you called me up !! \U0001F642 \n** **')
                await ctx.author.voice.channel.connect()
                await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_mute = False, self_deaf=True) #deafen the bot 
                self.registry.add_channel(ctx.guild, ctx.author.voice.channel, ctx.message.channel) 
            
            if title == "":
                await ctx.send('Type the name of the song after "-play"')
                return 

            self.registry.servers[ctx.guild.id].channel.add_to_queue(title)
            await ctx.send(f'"{YoutubeAPI().get_first_title(title)}" added to queue')

        @self.command()
        async def previous(ctx):
            voice_channel_is_valid = await self.valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            if self.registry.play_previous(ctx.guild.id, ctx.author.voice.channel.id):
                voice_client = ctx.message.guild.voice_client
                if voice_client.is_playing():
                    voice_client.stop() #stop if there is a current song playing
            else:
                await ctx.send("There is no previous song :(")
        
        @self.command()
        async def help(ctx):
            embed=discord.Embed(title="Funky Monkey Bot Commands", color=discord.Color.red())
            embed.add_field(name="**-play**", value='Play the song title written after it', inline=False)
            embed.add_field(name="**-pause**", value='Pauses the currently playing song', inline=False)
            embed.add_field(name="**-resume**", value='To resume song after being paused', inline=False)
            embed.add_field(name="**-skip**", value='skips the current song ', inline=False)
            embed.add_field(name="**-skip all**", value='Skips all the songs in the queue', inline=False)
            embed.add_field(name="**-lyrics**", value='Display the lyrics of the currently song', inline=False)
            embed.add_field(name="**-leave**", value='Make Funkey Monkey leave your voice channel', inline=False)
            embed.set_footer(text="Created by Ahmed Mahmoud")
            await ctx.send(embed=embed)

            
    @tasks.loop(seconds=1)
    async def play_loop(self):
        for guild_id in self.registry.servers:
                try:
                    #voice_instance = discord.utils.get(self.voice_clients, guild=guild)
                    voice_instance = self.registry.servers[guild_id].guild.voice_client
                    idle = not (voice_instance.is_playing() or voice_instance.is_paused())
                    if idle:
                        next_song = self.registry.get_next_song(guild_id)
                        if next_song:
                            song_url = next_song.urls[0]
                            text_channel = self.registry.servers[guild_id].channel.text
                            await text_channel.send("Playing: \n" + song_url)
                            with YoutubeDL(self.ydl_options) as ydl:
                                info = ydl.extract_info(song_url, download=False)
                            url = info['formats'][0]['url']
                            voice_instance.play(discord.FFmpegPCMAudio(url, **self.ffmpeg_options))

                    if voice_instance.is_playing():
                        self.registry.servers[guild_id].channel.last_active = time.time() #resets the last active time
                except Exception as e:
                    print(e)
                    try:
                        await self.registry.servers[guild_id].channel.text.send("Unexpected error happened")
                    except Exception as e:
                        print(e)
                        return

    @tasks.loop(seconds=20)
    async def gc_inactive_channels(self):
        servers = self.registry.servers.copy() #to avoid changing for the 
        for guild_id in servers:
            if time.time() - self.registry.servers[guild_id].channel.last_active > 3600:
                voice_client = self.registry.servers[guild_id].guild.voice_client
                text_channel = self.registry.servers[guild_id].channel.text
                self.registry.leave_channel(guild_id)
                await voice_client.disconnect()
                await text_channel.send("I left due to inactivity")
        
        
def main():
    with open("secrets.json", "r") as secrets_file:
        secrets = json.load(secrets_file)
    funky_bot = FunkyBot(command_prefix="-", genius_token=secrets["genius_token"])
    funky_bot.run(secrets["discord_token"])

main()