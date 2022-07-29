from tkinter import E
import discord
from discord.ext import commands
import os
import json
import tempfile
import shutil
import logging
import subprocess
import inspect
from pcvs.backend import bank
from pcvs.dsl import analysis, render

async def help_cmd(ctx):
    await ctx.send("Usage: /pcvs command\nAvailable commands:-list")

class TheBot(commands.Bot):
    async def on_ready(self):
        await bot.change_presence(activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name="/pcvs"))
        logging.info("Bot started")


bot = TheBot(command_prefix=commands.when_mentioned_or("/"))

@bot.command(name="bank")
async def bank_cmd(ctx, *args):
    """Interact with banks available.
    
    Requests list & contents of banks defined under the current PCVS
    installation:
    - `list`: lists available banks. Token names are used later to post requests
    - `show`: displays bank's content (argument must be the bank name)
    """
    bank.init()
    logging.debug("Process BANK cmd")
    if args:
        if args[0] == 'list':
            s = "List of available banks:\n"
            for bn, bp in bank.list_banks().items():
                s += "{}: {}\n".format(bn, bp)
            await ctx.send("Available banks:\n```{}```".format(s))
        elif args[0] == 'show':
            assert(args[1])
            b = bank.Bank(token=args[1])
            s = b.show(stringify=True)
            await ctx.send("```{}```".format(s))
        elif args[0] == "save":
            assert(args[1])
            b = bank.Bank(token=args[1])
            assert(b.exists())
            assert(len(ctx.message.attachments) == 1)
            tmp = ctx.message.attachments[0]
            assert(tmp.content_type == "application/x-tar")
            await tmp.save(fp=tmp.filename)
            b.save_from_archive(tag=None, archivepath=tmp.filename)
            await ctx.send("Serie {} successfully updated !".format(b.name))
        else:
            await ctx.send("Unknown syntax: {}".format(" ".join(args)))
            
@bot.command(name="analyze")
async def analyze_cmd(ctx, *args):
    """TODO:
    """
    bank.init()
    logging.debug("Process ANALYZE cmd")
    if args:
        logging.debug("args = {}".format(args))
        if args[0] == "list":
            s = "Available analyses:\n"
            for funcname, _ in inspect.getmembers(analysis.SimpleAnalysis, inspect.isfunction):
                s += "* {}\n".format(funcname)
            await ctx.send("```{}```".format(s))
        if args[0] == "render":
            assert(args[1] and args[2])
            req_bank = bank.Bank(token=args[2])
            assert(req_bank.exists())
            req_analysis = analysis.SimpleAnalysis(bank=req_bank)
            for fname, f in inspect.getmembers(req_analysis.__class__, inspect.isfunction):
                if fname == args[1]:
                    rendering = None
                    for a, b in inspect.getmembers(render, inspect.isfunction):
                        if a == fname:
                            rendering = (a, b)
                                
                    await ctx.send("Running analyses might take a while. I'll back soon. :wink:")
                    res = await f(req_analysis, req_bank.default_project)
                    
                    if rendering is None:
                        await ctx.send("Results are attached below: {}".format(res))
                    else:
                        with tempfile.NamedTemporaryFile(suffix=".png") as fh:
                            rendering[1](res, fh.name)
                            await ctx.send("Results are attached below", file=discord.File(fh.name))


LOGLEVEL = os.environ.get('LOGLEVEL', "INFO").upper()
logging.basicConfig(level=LOGLEVEL)
bot.run(os.getenv('DISCORD_TOKEN'))
