import discord
from discord.ext import commands, tasks
from registry import Registry
from youtube_dl import YoutubeDL
from lyricsgenius import Genius
import time
import json
from youtube_api import YoutubeAPI

MAX_MESSAGE_LENGTH = 1500
MAX_INACTIVE_TIME = 3600 # 1 hour


class FunkyBot(commands.Bot):
    """FunkyBot is a Discord bot that plays music in voice channels."""

    def __init__(self, command_prefix: str, genius_token: str):
        """"Initializes a FunkyBot instance.
        Args:
            command_prefix (str): The prefix for the commands.
            genius_token (str): The token for the Genius API used for lyrics extractions.
        """
        commands.Bot.__init__(
            self,
            command_prefix=command_prefix,
            help_command=None,
            intents=discord.Intents.all(),
        )
        self._registry = Registry()
        self._ydl_options = {"format": "bestaudio"}
        self._ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        }
        self.add_commands()
        self.__genius_token = genius_token

    async def on_ready(self) -> None:
        """This function is called when the bot is ready
        It starts the play_loop and the leave_inactive_chans tasks
        """
        self.play_loop.start()
        self.leave_inactive_chans.start()
        print("bot is ready")

    async def _valid_voice_channel(
        self, ctx: discord.ext.commands.context.Context
    ) -> bool:
        """'Checks if the user is in a valid voice channel
        Args:
            ctx (discord.ext.commands.Context): The context of the message
        Returns:
            bool: True if the user is in a valid voice channel, False otherwise
        """
        if not ctx.author.voice:
            await ctx.reply("Connect to a voice channel before calling me.")
            return False
        elif not self._registry.channel_exists(
            ctx.guild.id, ctx.author.voice.channel.id
        ):
            return False
        return True

    def add_commands(self):
        @self.command()
        async def leave(ctx: discord.ext.commands.context.Context) -> None:
            '''This command makes the bot leave the voice channel'''
            voice_channel_is_valid = await self._valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            await ctx.reply("See you later ;(")
            self._registry.leave_channel(ctx.guild.id)
            await ctx.guild.voice_client.disconnect()

        @self.command()
        async def lyrics(ctx: discord.ext.commands.context.Context) -> None:
            """This command displays the lyrics of the current song
                The function uses the genius API to get the lyrics of the song by searching for the title of the song
                The function sends the lyrics in multiple messages with each of maximum lentgh of 1500 characters
            Args:
                ctx (discord.ext.commands.Context): The context of the message
            """
            voice_channel_is_valid = await self._valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            # getting the title of the current song
            voice_instance = self._registry.servers[ctx.guild.id].guild.voice_client
            title = self._registry.get_current_song_title(voice_instance, ctx.guild.id)

            if title != "":
                genius = Genius(self.__genius_token)
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
                for line in lyrics:
                    # sending the lyrics in multiple messages with each of maximum lentgh of 1500 characters
                    if line == "":  # in order to send empty lines
                        line = "** **"

                    if paragraph_length + len(line) < MAX_MESSAGE_LENGTH:
                        paragraph.append(line)
                        paragraph_length += len(line)
                    else:
                        message = "\n".join(paragraph)
                        await ctx.send(message)
                        paragraph = []
                        paragraph_length = 0

                        paragraph.append(line)
                        paragraph_length += len(line)

                    if line == lyrics[-1]:  # checks if it is the last line in lyrics
                        message = "\n".join(paragraph)
                        await ctx.send(message)

        @self.command()
        async def pause(ctx: discord.ext.commands.context.Context) -> None:
            '''This command pauses the current song if it is playing
            Args:
                ctx (discord.ext.commands.Context): The context of the message
            '''
            voice_channel_is_valid = await self._valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            voice_client = ctx.message.guild.voice_client
            if voice_client.is_playing():
                voice_client.pause()
                await ctx.send("paused")

        @self.command()
        async def resume(ctx: discord.ext.commands.context.Context) -> None:
            '''This command resumes the current song if was paused
            Args:
                ctx (discord.ext.commands.Context): The context of the message
            '''
            voice_channel_is_valid = await self._valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            voice_client = ctx.message.guild.voice_client
            if not voice_client.is_playing():
                voice_instance = self._registry.servers[ctx.guild.id].guild.voice_client
                await ctx.send(
                    "Resuming "
                    + self._registry.get_current_song_title(voice_instance, ctx.guild.id)
                )
                voice_client.resume()

        @self.command()
        async def skip(ctx: discord.ext.commands.context.Context):
            '''This command skips the current song
            Args:
                ctx (discord.ext.commands.Context): The context of the message
            '''
            voice_channel_is_valid = await self._valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            voice_client = ctx.message.guild.voice_client
            if voice_client.is_playing():
                voice_client.stop()
                await ctx.send("Skipping")

        @self.command()
        async def play(ctx: discord.ext.commands.context.Context, *, title: str = "") -> None:
            '''This command adds a song to the queue
            Args:
                ctx (discord.ext.commands.Context): The context of the message
                title (str): The title of the song to be added to the queue
            '''
            if not ctx.author.voice:
                await ctx.reply("Connect to a voice channel before calling me.")
                return

            elif (
                ctx.guild.id in self._registry.servers
                and not self._registry.channel_exists(
                    ctx.guild.id, ctx.author.voice.channel.id
                )
            ):  
                # checks if the user is in the same server but in a different channel than the bot is in
                # disconnect from current channel and go to the other channel the user is in and deafen the bot
                voice_client = self._registry.servers[ctx.guild.id].guild.voice_client
                self._registry.leave_channel(ctx.guild.id)
                await voice_client.disconnect()
                await ctx.author.voice.channel.connect()
                await ctx.guild.change_voice_state(hannel=ctx.author.voice.channel, self_mute=False, self_deaf=True)  
                self._registry.add_channel(ctx.guild, ctx.author.voice.channel, ctx.message.channel)

            elif not self._registry.channel_exists(
                ctx.guild.id, ctx.author.voice.channel.id
            ):
                await ctx.reply("Glad you called me up !! \U0001F642 \n** **")
                # connect to the server the user in and deafen the bot
                await ctx.author.voice.channel.connect()
                await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_mute=False, self_deaf=True)  
                self._registry.add_channel(ctx.guild, ctx.author.voice.channel, ctx.message.channel)

            if title == "":
                await ctx.send('Type the name of the song after "-play"')
                return

            self._registry.servers[ctx.guild.id].channel.add_to_queue(title)
            await ctx.send(f'"{YoutubeAPI().get_first_title(title)}" added to queue')

        @self.command()
        async def previous(ctx: discord.ext.commands.context.Context):
            '''This command plays the previous song in the queue
            Args:
                ctx (discord.ext.commands.Context): The context of the message
            '''
            voice_channel_is_valid = await self._valid_voice_channel(ctx)
            if not voice_channel_is_valid:
                return

            if self._registry.play_previous(ctx.guild.id):
                voice_client = ctx.message.guild.voice_client
                if voice_client.is_playing():
                    voice_client.stop()  # stop if there is a current song playing
            else:
                await ctx.send("There is no previous song :(")

        @self.command()
        async def help(ctx: discord.ext.commands.context.Context):
            """This command sends in chat the commands of the bot
            Args:
                ctx (discord.ext.commands.Context): The context of the message
            """
            embed = discord.Embed(
                title="Funky Monkey Bot Commands", color=discord.Color.red()
            )
            embed.add_field(
                name="**-play**",
                value="Play the song title written after it",
                inline=False,
            )
            embed.add_field(
                name="**-pause**",
                value="Pauses the currently playing song",
                inline=False,
            )
            embed.add_field(
                name="**-resume**",
                value="To resume song after being paused",
                inline=False,
            )
            embed.add_field(
                name="**-skip**", value="skips the current song ", inline=False
            )
            embed.add_field(
                name="**-lyrics**",
                value="Display the lyrics of the currently song",
                inline=False,
            )
            embed.add_field(
                name="**-leave**",
                value="Make Funkey Monkey leave your voice channel",
                inline=False,
            )
            embed.set_footer(text="Created by Ahmed Mahmoud")
            await ctx.send(embed=embed)

    @tasks.loop(seconds=1)
    async def play_loop(self) -> None:
        '''This function play songs from the queue
        The function is called every second to check for every voice channel the bot is in 
        and checks if the bot is idle and there is a song in the queue and then play it
        '''
        for guild_id in self._registry.servers:
            try:
                server = self._registry.servers[guild_id]
                voice_instance = server.guild.voice_client
                idle = not (voice_instance.is_playing() or voice_instance.is_paused())
                if idle:
                    next_song = self._registry.get_next_song(guild_id)
                    if next_song:
                        song_url = next_song.urls[0]
                        text_channel = server.channel.text
                        await text_channel.send("Playing: \n" + song_url)
                        with YoutubeDL(self._ydl_options) as ydl:
                            info = ydl.extract_info(song_url, download=False)
                        url = info["formats"][0]["url"]
                        voice_instance.play(
                            discord.FFmpegPCMAudio(url, **self._ffmpeg_options)
                        )

                if voice_instance.is_playing():
                    server.channel.last_active = time.time()  # resets the last active time
            except Exception as e:
                print(e)
                try:
                    await self._registry.servers[guild_id].channel.text.send(
                        "Unexpected error happened"
                    )
                except Exception as e:
                    print(e)
                    return

    @tasks.loop(seconds=20)
    async def leave_inactive_chans(self) -> None:
        '''This function checks for inactive voice channels and leave them'''
        servers = self._registry.servers.copy()
        # copy the servers to avoide change in the dict while itterating over it
        for guild_id in servers:
            if time.time() - servers[guild_id].channel.last_active > MAX_INACTIVE_TIME:
                voice_client = servers[guild_id].guild.voice_client
                text_channel = servers[guild_id].channel.text
                self._registry.leave_channel(guild_id)
                await voice_client.disconnect()
                await text_channel.send("I left due to inactivity")


def main():
    with open("secrets.json", "r") as secrets_file:
        secrets = json.load(secrets_file)
    funky_bot = FunkyBot(command_prefix="-", genius_token=secrets["genius_token"])
    funky_bot.run(secrets["discord_token"])

if __name__ == "__main__":
    main()
