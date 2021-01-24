import discord
from discord.ext import commands, tasks
from discord.ext.commands import CommandNotFound, MessageConverter
import logging
import configparser
import validators

logging.basicConfig(level=logging.INFO)
import aiohttp
import discord.utils
import re

# image search bot/"disimager", coded by Lance Faltinsky

# read config file and set vars accordingly
config = configparser.ConfigParser()
config.read('config.ini')
token = config['bot']['token']
prefix = str(config['bot']['prefix'])

# create bot object
bot = commands.Bot(command_prefix=prefix)


# cog loading
@bot.event
async def on_ready():
    appid = await bot.application_info()
    appid = appid.id
    print("Disimager is ready\nInvite the bot here:\n" + discord.utils.oauth_url(appid))


# prevent ugly errors if command not found. also dont clash with other bots
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        return
    raise error


# -- actual image searching part --

# the url we need to query google with. an image link is appended to the end.
googlerequest = "https://www.google.com/searchbyimage?site=search&sa=X&image_url="


# command time
# "content" can be a link to either an image, or a link to a message with an image in it
@bot.command()
async def imgsearch(ctx, content=None):
    # no link? lets check if they have attachments
    if not content:
        # if user uploads an image, we set the content to be the url of that new image
        if len(ctx.message.attachments) > 0:
            content = ctx.message.attachments[0].url
            print(content)
        else:
            await ctx.send('Please link to an image, a message, or upload an image to reverse search.')
            return
    # ensure provided URL is valid
    if not validators.url(content):
        await ctx.send('Provided URL is invalid')
        return
    # we check if the link is a discord message link. if it is, we check if the message has attachments
    # and then extract the url from it
    if "https://discord.com/channels/" in content:
        # attempt to fetch the message, if it doesnt work then message is invalid
        try:
            msg = await MessageConverter().convert(ctx=ctx, argument=content)
        except discord.ext.commands.CommandError or discord.ext.commands.BadArgument:
            await ctx.send('Unable to find the linked message')
            return
        if len(msg.attachments) > 0:
            content = msg.attachments[0].url
        else:
            # as a last resort, try a regular expression to see if the linked message has an embedded image
            # re expression credit to http://urlregex.com/. because i suck at re
            print(msg.content)
            urls = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                              msg.content)
            print(urls)
            if len(urls) > 0:
                content = urls[0]
                if len(urls) > 2:
                    await ctx.send('The message you linked has multiple image links. Searching the first one.\n'
                                   'Please search the direct image link if this is not what you wanted.')
            else:
                await ctx.send('Linked message has no attachments')
                return

    # the rest is out of our hands- we will run the request and then check for errors on google's side
    # there is no need to check if the link is actually a link to an image
    # use aiohttp, requests is blocking. code courtesy of discord.py discord
    searchlink = googlerequest + content
    async with aiohttp.ClientSession(headers={
        'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36'}) as cs:
        async with cs.get(searchlink) as r:
            res = await r.text()
            # was gonna use beautifulsoup, but we can just check if keywords are in the text to check originality
            # we also need to make sure the search results page is really that and not google captcha'ing us
            if "No other sizes of this image found" in res:
                embed = discord.Embed(
                    title='Reverse image search results',
                    description='Image appears original - no reverse image results',
                    color=discord.Colour.green()
                )
                embed.set_footer(text=f'Requested by {str(ctx.author)}')
                await ctx.send(embed=embed)
                return
            elif "Find other sizes of this image" in res:
                embed = discord.Embed(
                    title='Reverse image search results',
                    description=f'Image may be unoriginal - matching image results found\n'
                                f'[See for yourself]({searchlink})',
                    color=discord.Colour.red()
                )
                embed.set_footer(text=f'Requested by {str(ctx.author)}')
                await ctx.send(embed=embed)
                return
            else:
                # if we reach this point, its very likely google blocked us
                embed = discord.Embed(
                    title='Reverse image search results',
                    description='Something happened that wasn\'t supposed to. Google could be blocking us.',
                    color=discord.Colour.orange()
                )


# run bot
bot.run(token)
