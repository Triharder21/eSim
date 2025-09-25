"""bot.py"""
import importlib
import json
import os
from datetime import datetime
from traceback import format_exception
from typing import Union

from discord import Intents, Message
from discord.ext import commands
from discord.ext.commands import Bot, Context, errors
from lxml.html import fromstring
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import Converters
import utils

config_file = "config.json"
if config_file in os.listdir():
    with open(config_file, 'r', encoding="utf-8") as file:
        for k, v in json.load(file).items():
            if k and k not in os.environ:
                os.environ[k] = v

utils.initiate_db()
bot = Bot(command_prefix=".", case_insensitive=True, intents=Intents.default())
bot.VERSION = "07/03/2024 03:15"
bot.config_file = config_file

options = Options()
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
if not os.environ.get("debug"):
    options.add_argument("--headless")

bot.browser_window = webdriver.Chrome(options=options)
bot.incognito_window = webdriver.Chrome(options=options)
bot.should_break_dict = {}  # format: {server: {command: True if it should be canceled, else False if it's running}}
categories = ("Eco", "Mix", "Social", "War", "Info")


async def start() -> None:
    """start function"""
    await bot.wait_until_ready()
    bot.allies = await utils.find_one("allies", "list", os.environ["nick"])
    bot.enemies = await utils.find_one("enemies", "list", os.environ["nick"])
    bot.friends = await utils.find_one("friends", "list", os.environ["nick"])
    for extension in categories:
        bot.load_extension(extension)
    print('Logged in as')
    print(bot.user.name)
    print(f"Invite: https://discordapp.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot")

    # you should change the following line in all your accounts (except for 1) to
    # `"help": ""` https://github.com/akiva0003/eSim/blob/main/config.json#L9
    # this way the bot will send only one help commands.
    if not await utils.is_helper():
        bot.remove_command("help")

    # restart saved long functions
    for d in (await utils.find_one("auto", "work", os.environ['nick'])).values():
        if isinstance(d, list):  # old version
            d = d[0]
        channel = bot.get_channel(int(d["channel_id"]))
        message = await channel.fetch_message(int(d["message_id"]))
        ctx = await bot.get_context(message)
        bot.loop.create_task(ctx.invoke(
            bot.get_command("auto_work"), d["work_sessions"], d["chance_to_skip_work"], nick=d["nick"]))

    for d in (await utils.find_one("auto", "motivate", os.environ['nick'])).values():
        if isinstance(d, list):  # old version
            d = d[0]
        channel = bot.get_channel(int(d["channel_id"]))
        message = await channel.fetch_message(int(d["message_id"]))
        ctx = await bot.get_context(message)
        bot.loop.create_task(ctx.invoke(bot.get_command("auto_motivate"), d["chance_to_skip_a_day"], nick=d["nick"]))

    for d1 in (await utils.find_one("auto", "fight", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("auto_fight"), d["nick"], d["restores"], d["battle_id"],
                d["side"], d["wep"], d["food"], d["gift"], d["ticket_quality"], d["chance_to_skip_restore"]))

    for d1 in (await utils.find_one("auto", "hunt", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("hunt"), d["nick"], d["max_dmg_for_bh"], d["weapon_quality"], d["start_time"],
                d["ticket_quality"], d.get("consume_first", "none")))

    for d1 in (await utils.find_one("auto", "hunt_battle", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("hunt_battle"), d["nick"], d["link"], d["side"], d["dmg_or_hits_per_bh"],
                d["weapon_quality"], d["food"], d["gift"], d["start_time"]))

    for d1 in (await utils.find_one("auto", "watch", os.environ['nick'])).values():
        for d in d1:
            channel = bot.get_channel(int(d["channel_id"]))
            message = await channel.fetch_message(int(d["message_id"]))
            ctx = await bot.get_context(message)
            bot.loop.create_task(ctx.invoke(
                bot.get_command("watch"), d["nick"], d["battle"], d["side"], d["start_time"], d["keep_wall"],
                d["let_overkill"], d["weapon_quality"], d["ticket_quality"], d["consume_first"], d.get("medkits", 0)))


def login(server: str) -> None:
    driver = bot.browser_window
    if driver.current_url == f"https://{server}.e-sim.org/":
        try:
            login_button = driver.find_element(By.ID, 'navigateToLogin')
            if login_button.is_displayed():
                login_button.click()
        except Exception:
            pass
    login_form = driver.find_element(By.CSS_SELECTOR, "form[action='Iogin.html']")
    username_input = login_form.find_element(By.NAME, "login")
    password_input = login_form.find_element(By.NAME, "password")
    nick = utils.my_nick(server)
    username_input.send_keys(nick)
    password_input.send_keys(os.environ.get(server + "_password", os.environ.get('password')))
    login_form.submit()

    url = driver.current_url
    print(datetime.now(), nick, server, url)
    # if "index.html?act=login" not in str(url):
    #     raise ConnectionError(f"{nick} - Failed to login {url}")


strategies = {
    "id": By.ID,
    "name": By.NAME,
    "class": By.CLASS_NAME,
    "css": By.CSS_SELECTOR,
    "xpath": By.XPATH,
    "link_text": By.LINK_TEXT,
    "partial_link_text": By.PARTIAL_LINK_TEXT,
    "tag_name": By.TAG_NAME,
}


async def get_content(link: str = None, data: dict = None, return_tree: bool = False,
                      incognito: bool = False, logged_in: bool = False) -> Union[str, fromstring, tuple, dict, list]:
    """`return_tree=None` means return (tree, url)"""

    incognito = incognito or (link and "api" in link)
    driver = bot.incognito_window if incognito else bot.browser_window
    if not link:
        link = driver.current_url
    # tab for each server:
    # if server not in driver.window_handles:
    #     driver.execute_script(f"window.open('', '{server}');")
    #     driver.switch_to.window(server)
    if driver.current_url != link:
        driver.get(link)
        max_wait = 10
        WebDriverWait(driver, max_wait).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    tree = fromstring(driver.page_source)

    logged = tree.xpath('//*[@id="command"]')
    if not incognito and (any("Iogin.html" in x.action for x in logged) or tree.xpath('//*[@id="navigateToLogin"]')):
        if not logged_in:
            server = link.split("https://", 1)[1].split(".e-sim.org", 1)[0]
            login(server)
            return await get_content(link, data, return_tree, incognito, True)  # call the function again
        else:
            raise ConnectionError("notLoggedIn")

    if not incognito:  # missionDropdownClose
        try:
            if tree.xpath('//*[@id="blackBackground"]'):
                driver.find_element(By.ID, "tutorialCB").click()
        except NoSuchElementException:
            pass

    # Περίπτωση 1: click σε στοιχείο
    from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    TimeoutException
)

    if data and "click" in data:
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((strategies[data["find_by"].lower()], data["element"])))
            driver.find_element(strategies[data["find_by"].lower()], data["element"]).click()
        except (ElementClickInterceptedException, ElementNotInteractableException):
        # Κάνε click στο body για να φύγει popup
            try:
                driver.execute_script("document.body.click();")
                await asyncio.sleep(1)
            except Exception as e:
                print("Popup clear failed:", e)
        # Ξαναδοκίμασε το click
            driver.find_element(strategies[data["find_by"].lower()], data["element"]).click()


# Περίπτωση 2: submit φόρμας με payload
    elif data and "find_by" in data:
        form = driver.find_element(strategies[data["find_by"].lower()], data["element"])
        for key, value in data.get("payload", {}).items():
            try:
                for element in form.find_elements(By.NAME, key):
                    if element.tag_name == "select":
                        select = Select(element)
                        select.select_by_value(str(value))
                    elif element.get_attribute("type") == "radio":
                        if element.get_attribute("value") == str(value):
                            element.click()
                            break
                    elif key != "submit":
                        element.clear()
                        element.send_keys(str(value))
            except NoSuchElementException:
                print(f"Element '{key}' not found in {link}. Skipping...")
        form.submit()

# Περίπτωση 3: καθαρό POST data (π.χ. από dump_health)
    elif data is not None:
        driver.get(link)
        script = """
        function post(path, params) {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = path;
            for (const key in params) {
                if (params.hasOwnProperty(key)) {
                    const hiddenField = document.createElement('input');
                    hiddenField.type = 'hidden';
                    hiddenField.name = key;
                    hiddenField.value = params[key];
                    form.appendChild(hiddenField);
                }
            }
            document.body.appendChild(form);
            form.submit();
        }
        post(arguments[0], arguments[1]);
        """
        driver.execute_script(script, link, data)

    else:
        driver.get(link)


    if "api" in link or "battleScore" in link:
        api = json.loads(driver.find_element(By.TAG_NAME, 'body').text)
        if "error" in api:
            raise ConnectionError(api["error"])
        return api if "apiBattles" not in link else api[0]

    tree = fromstring(driver.page_source)
    if return_tree is None:
        return tree, driver.current_url
    return tree if return_tree else driver.current_url


@bot.event
async def on_message(message: Message) -> None:
    """Override original on_message, to allow other bots to invoke commands"""
    ctx = await bot.get_context(message)
    if ctx.valid:
        if "allowed_servers" in os.environ and str(ctx.guild.id) not in os.environ["allowed_servers"]:
            if "logs_channel_id" in os.environ:
                logs = bot.get_channel(int(os.environ["logs_channel_id"]))
                await logs.send(
                    f"**WARNING**: {ctx.author.mention} tried to invoke `{ctx.command}` in a forbidden guild named `{ctx.guild.name}` (ID `{ctx.guild.id}`) "
                    f"on channel named `{ctx.channel.name}`.\n"
                    f"Full message: `{message.content}`\nMore details:\n\n```{message}```")
            return
        await bot.invoke(ctx)


@bot.before_invoke
async def add_command(ctx: Context) -> None:
    utils.add_command(ctx)


@bot.after_invoke
async def remove_finished_command(ctx: Context) -> None:
    utils.remove_finished_command(ctx)


# @bot.command()
async def update(ctx: Context, *, nick: Converters.IsMyNick) -> None:
    """Updates the code from the source.
    You can also use `.update ALL`"""
    bot.incognito_window.get("https://api.github.com/repos/akiva0003/eSim/git/trees/main")
    api = json.loads(bot.incognito_window.page_source)
    for github_file in api["tree"]:
        file_name = github_file["path"]
        if not file_name.endswith(".py"):
            continue
        bot.incognito_window.get(f"https://raw.githubusercontent.com/akiva0003/eSim/main/{file_name}")
        with open(file_name, "w", encoding="utf-8", newline='') as f:
            f.write(bot.incognito_window.page_source)
    bot.incognito_window.get("https://api.github.com/repos/akiva0003/eSim/branches/main")
    bot.VERSION = json.loads(bot.incognito_window.page_source)["commit"]["commit"]["author"]["date"]
    importlib.reload(utils)
    importlib.reload(Converters)
    utils.initiate_db()  # global variable reloaded
    for extension in categories:
        bot.reload_extension(extension)

    await ctx.send(f"**{nick}** updated. Running commands won't be affected.")


@bot.event
async def on_command_error(ctx: Context, error: Exception) -> None:
    """on command error"""
    error = getattr(error, 'original', error)
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("ERROR: you can't use this command in a private message!")
        return
    if isinstance(error, (commands.CommandNotFound, errors.CheckFailure)):
        return
    if isinstance(error, (errors.MissingRequiredArgument, errors.BadArgument)):
        if await utils.is_helper():
            await ctx.reply(f"```{''.join(format_exception(type(error), error, error.__traceback__))}```"[:1950])
        return
    try:
        last_msg = str(list(await ctx.channel.history(limit=1).flatten())[0].content)
    except IndexError:
        print(
            f"I can't read the channel history. Please give me Admin role and check here all intents https://discord.com/developers/applications/{bot.user.id}/bot")
        return
    nick = utils.my_nick(ctx.channel.name)
    error_msg = f"**{nick}** ```{''.join(format_exception(type(error), error, error.__traceback__))}```"[:1950]
    if error_msg != last_msg:
        # Don't send from all users.
        try:
            await ctx.reply(error_msg)
        except Exception:
            await ctx.reply(error)


bot.get_content = get_content
if os.environ["TOKEN"] != "PASTE YOUR TOKEN HERE":
    bot.loop.create_task(start())  # startup function
    bot.run(os.environ["TOKEN"])
else:
    print("ERROR: please follow those instructions: https://github.com/akiva0003/eSim#setup")
