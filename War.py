"""War.py"""
import os
from asyncio import sleep
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from random import randint, shuffle, uniform
from typing import Optional

from discord import Embed
from discord.ext.commands import Cog, command, Context
from lxml.html import fromstring
from pytz import timezone
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

import asyncio
import re
from itertools import chain, islice
import time
import random
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from selenium.common.exceptions import NoSuchElementException


from random import choice, uniform
from asyncio import sleep
from typing import Optional
from discord.ext import commands
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


import utils
from Converters import Country, Dmg, FoodOrGift, Id, IsMyNick, MotivateType, Product, Quality, Side


# You may want to replace all `consume_first="gift"` to `consume_first="food"`


class War(Cog):
    """War Commands"""

    def __init__(self, bot):
        self.bot = bot

    async def fight_restore(self, link: str, side: Optional[str], weapon_quality: int) -> (int, int, str, str, str):
        """
        Ένα restore: χτυπάει Berserk με το health που έχει (100HP από το restore) και μετά συνεχίζει
        να πατάει Fight (το game τρώει μόνο του) μέχρι health = 0 και limits -1 food, -1 gift.
        Π.χ. 100HP, 11/11 limits -> 0HP, 10/10 limits.
        Τα free hits (avoid) δεν πειράζουν: μετράμε health και limits, όχι χτυπήματα.
        side=None: όποια πλευρά δείχνει η σελίδα (random mode).
        Επιστρέφει (πλευρά, berserks, damage, τι έφαγε, error ή "").
        """
        driver = self.bot.browser_window
        tree = await self.bot.get_content(link, return_tree=True)
        side = side or self.visible_fight_side()
        if not side:
            return "", 0, 0, "", "ERROR: can't fight in this battle from your current location"
        error = self.setup_fight(weapon_quality, side, "none")
        if error:
            return side, 0, 0, "", error
        start_food, start_gift = utils.get_limits(tree)
        berserks = damage_done = no_answer = 0
        while True:
            health = utils.get_health(tree) or 0
            if health < 50:
                # το επόμενο Fight θα φάει: ξαναφόρτωσε για σωστά health / limits
                tree = await self.bot.get_content(link, return_tree=True)
                health = utils.get_health(tree) or 0
                food_limit, gift_limit = utils.get_limits(tree)
                food_used, gift_used = start_food - food_limit, start_gift - gift_limit
                # τέλος restore: 0 health και έφαγε 1 food + 1 gift (ή δεν έχει άλλα limits)
                if health < 50 and ((food_used >= 1 and gift_used >= 1) or food_limit + gift_limit == 0):
                    if health != 0:
                        error = f"WARNING: finished with {health} health instead of 0"
                    break
                error = self.setup_fight(weapon_quality, side, "none")
                if error:
                    break
            if not self.click_fight(side):
                no_answer += 1
                if no_answer >= 3:
                    error = "the fight button doesn't respond"
                    break
                continue
            no_answer = 0
            tree = fromstring(driver.page_source)
            response = tree.xpath('//*[@id="fightResponse"]')
            response_text = " ".join((response[0].text_content() if response else "").split())
            damage = tree.xpath('//*[@id="fightResponse"]//*[@id="DamageDone"]')
            if not damage:
                if "Slow down" in response_text:
                    continue  # δεν μετράει, ξαναδοκίμασε
                if "Round is closed" in response_text:
                    error = "round is over"
                elif "No health left" not in response_text:
                    error = response_text[:300]
                break
            berserks += 1
            damage_done += int(re.sub(r"\D", "", damage[0].text_content().split("+")[0]) or 0)
            await sleep(uniform(0.5, 2))

        tree = await self.bot.get_content(link, return_tree=True)
        food_limit, gift_limit = utils.get_limits(tree)
        ate = (f"{start_food - food_limit} food, {start_gift - gift_limit} gift, "
               f"limits now {food_limit}/{gift_limit}, health {utils.get_health(tree)}")
        return side, berserks, damage_done, ate, error

    @command()
    async def auto_fight(self, ctx: Context, nick: IsMyNick, battle_id: Id = 0, side: Side = "attacker",
                         wep: Quality = 5, ticket_quality: Quality = 5,
                         chance_to_skip_restore: int = 7, restores: int = 120):
        """Κάθε restore (~10 λεπτά, σε τυχαία ώρα): Berserk με τα 100HP και μετά μέχρι να φάει 1 food + 1 gift.
        (everything inside [] is optional with default values)
        `battle_id=0` means random battle and any side (το `side` αγνοείται, χτυπάει όποια πλευρά δείχνει η σελίδα).

        If `nick` contains more than 1 word - it must be within quotes.
        You can write multiple nicks: "nick 1, nick 2, ..."

        Example: `.auto_fight "My Nick" 184816 attacker 5 5 0 100`
        [battle 184816, attacker side, Q5 weapons, Q5 ticket, no skipped restores (0%), 100 restores]"""

        # Δεν αποθηκεύεται: αν κλείσει το script, σταματάει (δεν ξαναξεκινάει μόνο του).
        utils.remove_finished_command(ctx)
        ctx.command = f"auto_fight-{ctx.message.id}"
        utils.add_command(ctx)  # για να δουλεύει το .cancel auto_fight-<id>

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        specific_battle = (battle_id != 0)
        await ctx.send(f"**{nick}** Starting auto_fight. If you want to stop it, type "
                       f"`.cancel auto_fight-{ctx.message.id} {nick}`")
        while restores > 0 and not utils.should_break(ctx):
            restores -= 1
            if randint(0, 100) <= chance_to_skip_restore:
                await sleep(600)
            if not battle_id:
                battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)
            if not battle_id:
                await ctx.send(
                    f"**{nick}** WARNING: I can't fight in any battle right now, but I will check again after the next restore")
                await utils.random_sleep(restores)
                continue
            api_battles = await self.bot.get_content(f"{base_url}apiBattles.html?battleId={battle_id}")
            if 8 in (api_battles['attackerScore'], api_battles['defenderScore']):
                if specific_battle:
                    await ctx.send(f"**{nick}** Battle has finished.")
                    break
                await ctx.send(f"**{nick}** Searching for the next battle...")
                battle_id = await utils.get_battle_id(self.bot, str(nick), server, battle_id)
                if not battle_id:
                    await utils.random_sleep(restores)
                    continue
                api_battles = await self.bot.get_content(f"{base_url}apiBattles.html?battleId={battle_id}")
            if specific_battle and 1 <= ticket_quality <= 5:
                bonus_region = await utils.get_bonus_region(self.bot, base_url, side, api_battles)
                if bonus_region:
                    if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                        break

            link = f"{base_url}battle.html?id={battle_id}"
            # random mode: όποια πλευρά δείχνει η σελίδα
            side_used, berserks, damage, ate, error = await self.fight_restore(
                link, side if specific_battle else None, wep)
            if not specific_battle and not side_used and 1 <= ticket_quality <= 5:
                # δεν μπορείς να χτυπήσεις από εδώ: πέτα στο bonus region μιας τυχαίας πλευράς και ξαναδοκίμασε
                bonus_region = await utils.get_bonus_region(
                    self.bot, base_url, choice(["attacker", "defender"]), api_battles)
                if bonus_region and await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality,
                                                     nick=nick):
                    side_used, berserks, damage, ate, error = await self.fight_restore(link, None, wep)
            await ctx.send(f"**{nick}** <{link}> {side_used}: {berserks} berserks, {damage:,} dmg (ate {ate})."
                           + (f"\n{error}" if error else "") + f" Restores left: {restores}")
            if error.startswith("ERROR"):  # π.χ. λάθος τοποθεσία
                if specific_battle:
                    break
                battle_id = 0  # random mode: άλλη μάχη στο επόμενο restore
            await utils.random_sleep(restores)

        utils.remove_finished_command(ctx)

    # @command(name="BO")
    async def battle_order(self, ctx: Context, battle: Id, side: Side, key: Optional[int] = 0, *, nick: IsMyNick):
        """
        Set battle order.
        You can use battle link/id.
        key=0 means MU order, key=1 means country order, and key=2 means coalition order
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'action': 'SET_ORDERS' if key != 1 else 'CHANGE_ORDER',
                   'battleId' if key != 1 else 'battleOrderId': f"{battle}_{'true' if side == 'attacker' else 'false'}",
                   'submit': "Set orders"}
        links = {0: "militaryUnitsActions.html", 1: "countryLaws.html", 2: "coalitionManagement.html"}
        await self.bot.get_content(base_url + "myMilitaryUnit.html")
        url = await self.bot.get_content(base_url + links[key], data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    # @command()
    async def buff(self, ctx: Context, buffs_names: str, *, nick: IsMyNick):
        """Buy and use buffs.

        The buff names should be formal (can be found via F12), but here are some shortcuts:
        VAC = EXTRA_VACATIONS, SPA = EXTRA_SPA, SEWER = SEWER_GUIDE, STR = STEROIDS, PD_10 = PAIN_DEALER_10_H
        More examples: BANDAGE_SIZE_C and CAMOUFLAGE_II, MILI_JINXED_ELIXIR, MINI_BLOODY_MESS_ELIXIR

        * You can also use blue/green/red/yellow instead of Jinxed/Finesse/bloody_mess/lucky
        * You can also use Q1-Q6 instead of mili/mini/standard/major/huge/exceptional
        * type `.buff-` if you don't want to buy the buff.

        Examples:
            .buff  str,tank    my nick
            .buff  Q1_elixirs  my nick"""
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        elixirs = ["BLOODY_MESS", "FINESE", "JINXED", "LUCKY"]
        shuffle(elixirs)
        if "BANDAGE_SIZE_" in buffs_names.upper():
            await ctx.send_help("dump_bands")
        buffs_names = buffs_names.upper().split(",")
        for buff in buffs_names[:]:
            if buff.endswith("_ELIXIRS"):
                buffs_names.remove(buff)
                buffs_names.extend([f'{buff.split("_")[0]}_{elixir}_ELIXIR' for elixir in elixirs])

        special_tree = await self.bot.get_content(f"{base_url}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
        special = [item.xpath('b/text()')[0].replace(" ", "_").upper() for item in
                   special_tree.xpath('//div[@class="specialItemInventory"]') if item.xpath('span/text()')]
        results = []
        buffed = False
        for i, buff_name in enumerate(buffs_names):
            buff_name = buff_name.strip().replace(" ", "_")
            if buff_name == "VAC":
                buff_name = "EXTRA_VACATIONS"
            elif buff_name == "SPA":
                buff_name = "EXTRA_SPA"
            elif buff_name == "SEWER":
                buff_name = "SEWER_GUIDE"
            elif "STR" in buff_name:
                buff_name = "STEROIDS"
            elif "PD" in buff_name:
                buff_name = buff_name.replace("PD", "PAIN_DEALER") + ("_H" if not buff_name.endswith("_H") else "")
            elif buff_name.endswith("_ELIXIR"):
                buff_name = utils.fix_elixir(buff_name)
            buffs_names[i] = buff_name
            buff_for_sell = buff_name in ("STEROIDS", "EXTRA_VACATIONS", "EXTRA_SPA", "TANK", "BUNKER", "SEWER_GUIDE")
            actions = ("BUY", "USE") if buff_for_sell and buff_name not in special else ("USE",)
            for action in actions:
                if utils.should_break(ctx):
                    return
                if action == "USE":
                    payload = {'item': buff_name, 'action': action, 'submit': 'Use'}
                else:
                    payload = {'itemType': buff_name, 'action': action, "quantity": 1}
                await self.bot.get_content(base_url + "storage.html?storageType=SPECIAL_ITEM")
                url = await self.bot.get_content(base_url + "storage.html?storageType=SPECIAL_ITEM", data=payload)
                results.append(f"{buff_name}: <{url}>")
                if "error" in url.lower():
                    results.append(f"ERROR: No such buff ({buff_name})")
                if "MESSAGE_OK" in url and buff_name in ("STEROIDS", "TANK", "SEWER", "BUNKER"):
                    buffed = True
        if buffed:
            data = await utils.find_one(server, "info", nick)
            data["Buffed at"] = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%d/%m  %H:%M")
            await utils.replace_one(server, "info", nick, data)

        await ctx.send(f"**{nick}**\n" + "\n".join(results))
        if "EXTRA_SPA" in buffs_names or "EXTRA_VACATIONS" in buffs_names:
            tree = await self.bot.get_content(base_url, return_tree=True)
            food_limit, gift_limit = utils.get_limits(tree)
            await utils.update_info(server, nick, {"limits": f"{food_limit}/{gift_limit}"})

    @command(aliases=["travel"])
    async def fly(self, ctx, region_id: int, ticket_quality: Optional[int] = 5, *, nick: IsMyNick) -> bool:
        """
        Traveling to a region (new interface).
        Δίνεις region_id (συνήθως από battle page).
        Αν δεν έχεις tickets του συγκεκριμένου Q, θα χρησιμοποιήσει χαμηλότερης ποιότητας.
        """
        if not (1 <= ticket_quality <= 5):
            return ticket_quality == 0  # 0 σημαίνει "δεν χρειάζεται να πετάξω"

        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        # 1. Region page
        tree = await self.bot.get_content(f"{base_url}region.html?id={region_id}", return_tree=True)

        # Hidden inputs για travel
        country_id = tree.xpath('//form[contains(@action,"travel.html")]//input[@name="countryId"]/@value')
        region_id_hidden = tree.xpath('//form[contains(@action,"travel.html")]//input[@name="regionId"]/@value')
        redirect_url = tree.xpath('//form[contains(@action,"travel.html")]//input[@name="redirectUrl"]/@value')

        # Αν δεν υπάρχουν → σημαίνει ότι είμαστε ήδη στην περιοχή
        if not (country_id and region_id_hidden and redirect_url):
            return True

        # 2. Διαθέσιμα tickets
        tickets_qualities = [int(x) for x in tree.xpath('//select[@id="ticketQuality"]/option/@value')] or [6]
        if ticket_quality not in tickets_qualities:
            if min(tickets_qualities) < ticket_quality:
                ticket_quality = min(tickets_qualities)
            else:
                await ctx.reply(f"**{nick}** ERROR: there are 0 Q{ticket_quality} tickets in storage.")
                return False

        # 3. Health check
        if not await self.restore_for_travel(base_url, tree, ticket_quality):
            await ctx.reply(f"**{nick}** ERROR: no health / limits.")
            return False

        # 4. Travel payload
        payload = {
            'countryId': country_id[0],
            'regionId': region_id_hidden[0],
            'ticketQuality': ticket_quality,
            'redirectUrl': redirect_url[0],
        }

        # 5. POST στο travel.html
        await self.bot.get_content(f"{base_url}region.html?id={region_id}")
        url = await self.bot.get_content(f"{base_url}travel.html", data=payload)

        await sleep(uniform(0, 1))
        await ctx.send(f"**{nick}** <{url}>")
        return True
        
    @commands.command(aliases=["ttravel"])
    async def tfarm(self, ctx, num_travels: int, ticket_quality: Optional[int] = 5,
                    consume: Optional[FoodOrGift] = None, *, nick: str):
        """
        Τυχαίες μεταφορές σε διαφορετικά regions (χωρίς διπλές).
        Χρήση: .tfarm <num_travels> <ticket_quality> [food/gift] <nick>
        Χωρίς food/gift τρώει food και μετά gift. Με food ή gift τρώει ΜΟΝΟ αυτό.
        Παράδειγμα: .tfarm 10 1 gift Kostas
        """
        if not (1 <= ticket_quality <= 5):
            await ctx.reply(f"**{nick}** ERROR: ticket_quality must be between 1-5.")
            return

        # Όλα γίνονται με clicks στο travel.html (λίστες χωρών/regions της σελίδας), οπότε δουλεύει σε κάθε server
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        driver = self.bot.browser_window
        visited = set()
        travels_done = 0

        while travels_done < num_travels and not utils.should_break(ctx):
            await self.bot.get_content(f"{base_url}travel.html")
            await sleep(uniform(1, 2))

            # 1. Ticket (μόνο όσα έχεις στο storage)
            tickets = {int(o.get_attribute("data-ticket-quality")): o for o in
                       driver.find_elements(By.CSS_SELECTOR, "#travelListDropdown > .option") if self.is_active(o)}
            if not tickets:
                await ctx.send(f"**{nick}** ERROR: no tickets in storage. Stopping tfarm.")
                break
            ticket = ticket_quality if ticket_quality in tickets else min(tickets)

            # 2. Food / gift αν δεν φτάνει το health
            ok, ate = await self.eat_on_travel_page(ticket, consume)
            if not ok:
                await ctx.send(f"**{nick}** ERROR: no health / {consume or 'food/gift'} limits. Stopping tfarm.")
                break

            # 3. Τυχαία χώρα -> τυχαίο region
            target = None
            countries = driver.find_elements(By.CSS_SELECTOR, "#countryListDropdown > .option")
            shuffle(countries)
            for country in countries[:20]:
                old_regions = driver.find_elements(By.CSS_SELECTOR, "#regionListDropDown > .option")
                await self.pick_dropdown_option("travelSelectedCountry", country)
                try:  # περιμένουμε να φορτώσει η λίστα με τα regions της χώρας
                    if old_regions:
                        WebDriverWait(driver, 10).until(EC.staleness_of(old_regions[0]))
                except TimeoutException:
                    pass
                await sleep(uniform(0.5, 1))
                regions = [o for o in driver.find_elements(By.CSS_SELECTOR, "#regionListDropDown > .option")
                           if self.is_active(o) and o.get_attribute("data-region-id") not in visited]
                if regions:
                    target = random.choice(regions)
                    break
            if not target:
                await ctx.send(f"**{nick}** ERROR: no region found to travel to. Stopping tfarm.")
                break
            region_id = target.get_attribute("data-region-id")
            region_name = " ".join(target.get_attribute("textContent").split())
            await self.pick_dropdown_option("travelSelectedRegion", target)
            await sleep(uniform(0.5, 1))

            # 4. Ticket + Travel
            ticket_option = driver.find_element(
                By.CSS_SELECTOR, f'#travelListDropdown > .option[data-ticket-quality="{ticket}"]')
            await self.pick_dropdown_option("travelSelectedTicket", ticket_option)
            await sleep(uniform(0.5, 1))
            # η απάντηση του game μπαίνει στο #travelReload ("You have moved to ..." ή μήνυμα λάθους)
            travel_box = driver.find_element(By.ID, "travelReload")
            before = travel_box.get_attribute("textContent")
            ActionChains(driver).move_to_element(driver.find_element(By.ID, "travelButton")).click().perform()
            try:
                WebDriverWait(driver, 20).until(
                    lambda d: d.find_element(By.ID, "travelReload").get_attribute("textContent") != before)
            except TimeoutException:
                pass
            answer = " ".join(driver.find_element(By.ID, "travelReload").get_attribute("textContent").split())
            await sleep(uniform(1, 2))

            # 5. Έλεγχος ότι άλλαξε η τοποθεσία (sidebar Location)
            await self.bot.get_content(f"{base_url}travel.html")
            location = driver.find_element(
                By.XPATH, "//*[contains(text(), 'Location')]/following::a[contains(@href, 'region.html?id=')][1]")
            if utils.get_id(location.get_attribute("href")) != region_id:
                game_says = answer[:200] if "moved to" not in answer.lower() else "no answer from the game"
                await ctx.send(f"**{nick}** ERROR: travel to {region_name} ({region_id}) did not happen "
                               f"(game says: {game_says}). Stopping tfarm.")
                break

            visited.add(region_id)
            travels_done += 1
            ate = f" (ate: {', '.join(ate)})" if ate else ""
            await ctx.send(f"**{nick}** Travel {travels_done}/{num_travels} -> {region_name} "
                           f"(Q{ticket}){ate} <{base_url}region.html?id={region_id}>")
            await sleep(uniform(0.5, 1.5))

    @staticmethod
    def is_active(option) -> bool:
        classes = option.get_attribute("class") or ""
        return "disabled" not in classes and "notActive" not in classes

    async def pick_dropdown_option(self, selected_id: str, option):
        """Ανοίγει το dropdown του travel.html (hover) και κάνει click στην επιλογή."""
        driver = self.bot.browser_window
        ActionChains(driver).move_to_element(driver.find_element(By.ID, selected_id)).perform()
        await sleep(uniform(0.5, 1))
        # οι λίστες έχουν scroll, οπότε scrollIntoView + click μέσω JS (τρέχει το onclick της σελίδας)
        driver.execute_script("arguments[0].scrollIntoView({block: 'nearest'}); arguments[0].click();", option)

    async def eat_on_travel_page(self, ticket_quality: int, only: Optional[str] = None) -> (bool, list):
        """
        Στο travel.html: τρώει Q5 food (ή Q5 gift) με clicks μέχρι να φτάσει το health για το ticket
        (Q1 = 40HP, Q5 = 0HP). only="food"/"gift" = τρώει μόνο αυτό. Επιστρέφει (ok, τι έφαγε).
        """
        driver = self.bot.browser_window
        required_hp = 50 - ticket_quality * 10
        text = lambda css: driver.find_element(By.CSS_SELECTOR, css).get_attribute("textContent").strip()
        number = lambda css: float(text(css) or 0)
        ate = []
        for _ in range(5):
            health = number("#actualHealth")
            if health >= required_hp:
                return True, ate
            if only != "gift" and number(".foodLimit") > 0 and number("#foodContainer #sfoodQ5") > 0:
                kind = "food"
            elif only != "food" and number(".giftLimit") > 0 and number("#foodContainer #sgiftQ5") > 0:
                kind = "gift"
            else:
                return False, ate

            # διάλεξε food/gift από τη λίστα και πάτα το (όπως με το χέρι)
            if driver.find_element(By.ID, "selectedFood").get_attribute("data-id") != f"s{kind}Q5":
                driver.find_element(By.ID, "foodSelectable").click()
                await sleep(uniform(0.5, 1))
                driver.find_element(By.CSS_SELECTOR, f'#foodContainer .consumableForHealth[data-id="s{kind}Q5"]').click()
                await sleep(uniform(0.5, 1))
            driver.find_element(By.ID, "selectedFood").click()
            ate.append(kind)
            await sleep(2)
            if number("#actualHealth") <= health:  # δεν άλλαξε το health -> κάτι πήγε στραβά
                return False, ate
        return number("#actualHealth") >= required_hp, ate

    async def restore_for_travel(self, base_url: str, tree, ticket_quality: int) -> bool:
        """
        Για το fly: αν δεν φτάνει το health, πάει στο travel.html και τρώει food/gift με clicks.
        (Το region.html δεν έχει πλέον food/gift/limits.)
        """
        health_text = tree.xpath('//span[@id="actualHealth"]/text()')
        if (float(health_text[0]) if health_text else 100.0) >= 50 - ticket_quality * 10:
            return True
        await self.bot.get_content(f"{base_url}travel.html")
        ok, _ = await self.eat_on_travel_page(ticket_quality)
        return ok

    @classmethod
    def convert_to_dict(cls, s):
        """convert to dict"""
        return dict([a.split("=") for a in s.split("&")])

    @classmethod
    async def get_fight_data(cls, base_url, tree, wep, side, value="Berserk"):
        """get fight data"""
        hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value
        data = {"weaponQuality": wep, "battleRoundId": hidden_id, "side": side if side == "attacker" else "default",
                "value": value or "Regular"}
        script = []
        function = ""
        for script in tree.xpath("//script/text()"):
            if "function sendFightRequest(" in script:
                break
        script = "".join(script)
        for function in script.split("function"):
            if "sendFightRequest(" in function:
                break

        data.update(cls.convert_to_dict("ip=" + function.split("&ip=")[1].split("'")[0]))
        fight_url = function.split("url: ")[1].split(",")[0].replace('"', "")
        return f"{base_url}{fight_url}", data

    def setup_health(self, food_or_gift: str):
        driver = self.bot.browser_window
        restore_container = driver.find_element(By.ID, "foodContainer")
        restore_container.find_element(By.ID, "foodSelectable").click()
        restore_list = restore_container.find_elements(By.CLASS_NAME, "consumableForHealth")
        if food_or_gift not in ("food", "gift"):  # f.e none
            food_or_gift = "food"
        for restore in restore_list:
            if restore.get_attribute("data-id") == f"s{food_or_gift}Q5":
                restore.click()

    def restore_health(self, tree, consume_first: str):
        # assuming there are limits
        driver = self.bot.browser_window
        restore_container = driver.find_element(By.ID, "foodContainer")
        food_storage, gift_storage = utils.get_storage(tree)
        food_limit, gift_limit = utils.get_limits(tree)
        if food_storage == 0 and gift_storage == 0:
            return "\nERROR: 0 food and gift in storage"

        try:
            if consume_first == "gift" or (consume_first == "none" and gift_limit > food_limit):
                if gift_storage == 0 or gift_limit == 0:
                    self.setup_health("food")
            else:
                if food_storage == 0 or food_limit == 0:
                    self.setup_health("gift")
            restore_container.find_element(By.ID, "selectedFood").click()
        except Exception:
            return "\nERROR: couldn't restore health"

    def setup_fight(self, weapon_quality: Quality, side: Side, food_or_gift: str, berserk: bool = True):
        driver = self.bot.browser_window
        fight_container = driver.find_element(By.ID, "fightMainColumn")

        # Select weapon (μόνο αν δεν είναι ήδη επιλεγμένο)
        weapon_container = fight_container.find_element(By.ID, "weaponContainer")
        for weapon in weapon_container.find_elements(By.CLASS_NAME, "consumableWeapon"):
            if weapon.get_attribute("data-quality") == str(weapon_quality):
                if "active" not in (weapon.get_attribute("class") or ""):
                    # JS click: το βελάκι καλύπτεται από το fightMainColumn
                    driver.execute_script("arguments[0].click();",
                                          weapon_container.find_element(By.ID, "selectWeaponButton"))
                    driver.execute_script("arguments[0].click();", weapon)
                break

        # Select side: η σελίδα δείχνει μόνο το κουμπί της πλευράς που είσαι.
        # Στα RW υπάρχει το εικονίδιο ⇄ (.changeSide) για αλλαγή πλευράς.
        if self.visible_fight_side() != side:
            change_side = driver.find_elements(By.CSS_SELECTOR, ".changeSide")
            if change_side:
                ActionChains(driver).move_to_element(change_side[0]).click().perform()
                WebDriverWait(driver, 5).until(lambda d: self.visible_fight_side() == side)
            if self.visible_fight_side() != side:
                return f"ERROR: can't fight for the {side} from your current location"

        # Μόνο Berserk (x5)
        checkbox = fight_container.find_element(By.ID, f"{side}BerserkCheckbox")
        if not checkbox.is_selected():
            driver.execute_script("arguments[0].click();", checkbox)  # click() didn't work

    def visible_fight_side(self) -> Optional[str]:
        """Ποιο κουμπί Fight δείχνει η σελίδα: αριστερά = defender, δεξιά = attacker."""
        driver = self.bot.browser_window
        for side, box_id in (("defender", "fightButtonLeftSide"), ("attacker", "fightButtonRightSide")):
            box = driver.find_elements(By.ID, box_id)
            if box and "hidden" not in (box[0].get_attribute("class") or ""):
                return side
        return None

    def select_berserk_once(self, side: str):
        """Επιλέγει το Χ5 (Berserk) μόνο μία φορά πριν ξεκινήσει το fight loop."""
        driver = self.bot.browser_window
        checkbox_id = f"{side}BerserkCheckbox"  # π.χ. "attackerBerserkCheckbox" ή "defenderBerserkCheckbox"
        try:
            checkbox = driver.find_element(By.ID, checkbox_id)
            if not checkbox.is_selected():  # επιλέγει μόνο αν δεν είναι ήδη
                driver.execute_script("arguments[0].click();", checkbox)
                print(f"[DEBUG] Berserk (x5) selected for {side}")
        except NoSuchElementException:
            print(f"[WARNING] Berserk checkbox not found for {side}")


    def click_fight(self, side) -> bool:
        """
        Click στο κουμπί Fight. Αν υπάρχει popup, το click το κλείνει και ξαναδοκιμάζει.
        Σταματάει μόλις έρθει η απάντηση του χτυπήματος (άρα 1 χτύπημα ανά κλήση).
        """
        driver = self.bot.browser_window
        side_str = "Left" if side == "defender" else "Right"
        # marker: η σελίδα αντικαθιστά το "#fightResponse > div" με την απάντηση, οπότε όταν χαθεί ήρθε
        driver.execute_script("""
            const box = document.querySelector('#fightResponse > div');
            if (box) box.insertAdjacentHTML('beforeend', '<span id="botWaitingForHit"></span>');""")
        for attempt in range(5):
            try:
                fight_button = driver.find_element(By.ID, f"fightButton{side_str}Side")
                ActionChains(driver).move_to_element(fight_button).pause(uniform(0.05, 0.15)).click().perform()
            except Exception as e:
                print(f"[DEBUG] Click failed (attempt {attempt + 1}): {e}")
            try:
                WebDriverWait(driver, 3, poll_frequency=0.05).until(
                    lambda d: not d.find_elements(By.ID, "botWaitingForHit"))
                return True
            except TimeoutException:
                pass  # μάλλον το click έκλεισε popup -> ξαναπάτα
        return False


    @command(aliases=["fight_fast"])
    async def fight(self, ctx: Context, nick: IsMyNick, battle: Id, side: Side, weapon_quality: Quality = 5,
                    dmg_or_hits: Dmg = 200, ticket_quality: Quality = 5, consume_first="gift", medkits: int = 0,
                    continue_next_round: bool = False) -> (bool, int):
        driver = self.bot.browser_window
        """
        Dumping limits at a specific battle.
        (everything inside [] is optional with default values)
        Examples:
            .fight "my nick" https://primera.e-sim.org/battle.html?id=1 attacker
            .fight nick 1 a 5 1kk 5 none 1

        * It will auto fly to bonus region.
        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        * set `consume_first` to `none` if you want to consume `1/1` (fast servers)
        * Use `fight_fast` instead of `fight` if you don't want it to spec the battle for a few seconds.
        * If `nick` contains more than 1 word - it must be within quotes.
        - See also: .help dump_bands
        """

        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            await ctx.send(f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
            return True, 0
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        link = f"{base_url}battle.html?id={battle}"
        dmg = dmg_or_hits
        api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        if 1 <= ticket_quality <= 5:
            bonus_region = await utils.get_bonus_region(self.bot, base_url, str(side), api)
            if bonus_region:
                if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                    return
        t2 = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api["secondsRemaining"] < uniform(60, 120)

        tree = await self.bot.get_content(link, return_tree=True)
        setup_error = self.setup_fight(weapon_quality, side, consume_first)
        if setup_error:
            await ctx.send(f"**{nick}** {setup_error}")
            return True, 0
        try:
            food_storage, gift_storage = utils.get_storage(tree)
        except IndexError:
            await ctx.send(f"**{nick}** ERROR")
            return True, 0
        food_limit, gift_limit = utils.get_limits(tree)
        try:
            wep = weapon_quality if not weapon_quality else int(
                tree.xpath(f'//*[@id="weaponQ{weapon_quality}"]')[0].text)
        except IndexError:
            await ctx.send(f"**{nick}** ERROR: There are 0 Q{weapon_quality} weapons in storage")
            return True, 0

        output = f"**{nick}** Fighting at: <{link}&round={api['currentRound']}> for the {side}\n" \
                 f"Limits: {food_limit}/{gift_limit}. Storage: {food_storage}/{gift_storage}/{wep} Q{weapon_quality} weps.\n" \
                 f"If you want me to stop, type `.cancel {ctx.command} {nick}`"
        if food_storage < food_limit or gift_storage < gift_limit or (
                weapon_quality and wep < (food_limit + gift_limit) * 5 / 0.6):
            output += f"\nWARNING: you need to refill your storage. See `.help supply`, `.help pack`, `.help buy`"
        msg = await ctx.send(output)
        damage_done = 0
        update = 0
        no_answer = 0
        if ctx.invoked_with.lower() != "fight_fast":
            await sleep(uniform(3, 7))
        hits_or_dmg = "hits" if dmg <= 1000 else "dmg"
        while damage_done < dmg and not utils.should_break(ctx):
            if len(output) > 1900:
                output = "(Message is too long)"
            if weapon_quality > 0 and ((dmg >= 5 > wep) or (dmg < 5 and wep == 0)):
                await ctx.send(
                    f"**{nick}** Done {damage_done:,} {hits_or_dmg}\nERROR: no Q{weapon_quality} weps in storage")
                break
            health = utils.get_health(tree)
            if (health < 50 and dmg >= 5) or (health == 0 and dmg < 5):
                food_limit, gift_limit = utils.get_limits(tree)
                if food_limit == 0 and gift_limit == 0:
                    if medkits > 0:
                        try:
        # Ανοίγουμε την σελίδα του medkit
                            medkit_url = f"https://{server}.e-sim.org/storage.html?storageType=SPECIAL_ITEM"
                            await self.bot.get_content(medkit_url)

        # Πατάμε το κουμπί με id 'useMedkitMission'
                            medkit_button = driver.find_element(By.ID, "useMedkitMission")
                            driver.execute_script("arguments[0].click();", medkit_button)

                            medkits -= 1
                            await ctx.send(f"**{nick}** used a Medkit! Remaining: {medkits}")

                            await sleep(1.5)  # λίγο χρόνο για να ενημερωθεί η ζωή

        # Επιστρέφουμε στη μάχη
                            driver.get(link)
                            tree = fromstring(driver.page_source)
                            self.setup_fight(weapon_quality, side, consume_first)
                            continue  # συνεχίζουμε το fight loop

                        except NoSuchElementException:
                            await ctx.send(f"**{nick}** ERROR: couldn't find Medkit button")
                            break

                    else:
                        break
                # αλλιώς: το game τρώει food/gift μόνο του όταν πατάμε Fight
            try:
                berserk_checkbox = driver.find_element(By.ID, f"{side}BerserkCheckbox")  # attackerBerserkCheckbox / defenderBerserkCheckbox
                if not berserk_checkbox.is_selected():  # αν δεν είναι ήδη επιλεγμένο
                    driver.execute_script("arguments[0].click();", berserk_checkbox)
                    print(f"[DEBUG] Χ5 selected for side {side}")
            except NoSuchElementException:
                print(f"[DEBUG] Berserk checkbox for side {side} not found")
            if not self.click_fight(side):
                no_answer += 1
                if no_answer >= 3:
                    await ctx.send(f"**{nick}** ERROR: the fight button doesn't respond. Stopping.")
                    break
                continue
            no_answer = 0
            tree = fromstring(self.bot.browser_window.page_source)
            # Η απάντηση του χτυπήματος είναι στο #fightResponse: αν έχει DamageDone -> πέτυχε
            response = tree.xpath('//*[@id="fightResponse"]')
            response_text = response[0].text_content() if response else ""
            damage = tree.xpath('//*[@id="fightResponse"]//*[@id="DamageDone"]')
            if not damage:
                if "Slow down" in response_text:
                    continue  # δεν μετράει ως χτύπημα, ξαναδοκίμασε
                elif "Round is closed" in response_text:
                    output += "\nRound is over."
                    if continue_next_round:
                        await sleep(uniform(15, 25))
                        continue
                    else:
                        break
                elif "No health left" in response_text:
                    output += "\nNo health left."
                    break
                else:
                    await ctx.send(f"**{nick}** ERROR: {' '.join(response_text.split())}"[:1900])
                    break
            if weapon_quality:
                wep -= 5
            if dmg <= 1000:
                damage_done += 5
            else:
                damage_done += int(re.sub(r"\D", "", damage[0].text_content().split("+")[0]) or 0)
            update += 1
            if t2 or uniform(1, 100) < 20:  # 20% chance to sleep less if not t2
                await sleep(uniform(0.05, 0.12))
            else:
                await sleep(uniform(0.05, 0.12))

            if update % 4 == 0:
                # dmg update every 4 berserks.
                output += f"\n{hits_or_dmg.title()} done so far: {damage_done:,}"
                await msg.edit(content=output)
        await msg.edit(content=output)
        await ctx.send(f"**{nick}** Done {damage_done:,} {hits_or_dmg}, remaining limits: {food_limit}/{gift_limit}")
        await utils.update_info(server, nick, {"limits": f"{food_limit}/{gift_limit}"})
        return utils.should_break(ctx) or "ERROR" in output or damage_done == 0 or not any(
            (food_limit, gift_limit)), medkits

    # @command(hidden=True)
    async def dump_bands(self, ctx: Context, nick: IsMyNick, battle: Id, side: Side, weapon_quality: Quality = 5,
                         ticket_quality: Quality = 5) -> None:
        """Dump all your bandages (good for end of server)"""
        await ctx.send(f"**{nick}** If you want to stop it, type `.cancel dump_bands {nick}`")
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        link = f"{base_url}battle.html?id={battle}"
        api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
        if 1 <= ticket_quality <= 5:
            bonus_region = await utils.get_bonus_region(self.bot, base_url, side, api)
            if bonus_region:
                if not await ctx.invoke(self.bot.get_command("fly"), bonus_region, ticket_quality, nick=nick):
                    return
        special_tree = await self.bot.get_content(f"{base_url}storage.html?storageType=SPECIAL_ITEM", return_tree=True)
        special = {item.xpath('b/text()')[0].replace(" ", "_").upper(): item.xpath('span/text()')[0] for item in
                   special_tree.xpath('//div[@class="specialItemInventory"]') if item.xpath('span/text()')}

        tree = await self.bot.get_content(link, return_tree=True)
        fight_url, data = await War.get_fight_data(base_url, tree, weapon_quality, side)
        for bandage_size, total_bandages in special.items():
            if not bandage_size.startswith("BANDAGE_SIZE_") or utils.should_break(ctx):
                continue
            total_bandages = int(total_bandages.replace("x", ""))
            for i in range(total_bandages):
                payload = {'item': "BANDAGE_SIZE_" + bandage_size, 'storageType': "SPECIAL_ITEM", 'action': "USE",
                           'submit': 'Use'}
                health = utils.get_health(tree)
                if health == 0:  # use band
                    await self.bot.get_content(base_url + "storage.html", data=payload)
                    tree = await self.bot.get_content(link, return_tree=True)
                health = utils.get_health(tree)
                while health > 0:
                    data["value"] = "Regular" if health < 50 else "Berserk"
                    await self.bot.get_content(fight_url, data=data)
                    await sleep(1)
                    tree = await self.bot.get_content(link, return_tree=True)
                    health = utils.get_health(tree)
        await ctx.send(f"**{nick}** done dumping bandages")

    # @command()
    async def friend(self, ctx: Context, your_friend: str, *, nick: IsMyNick):
        """Adding a friend to your list.
        - You won't overbid your friends when using `.bid_all_auctions`
        - TODO: You should not steal BHs from your friends
        - TODO: You should not fight hard on `watch` when your friend is fighting.
        If the friend is already in the list, it will be removed."""
        server = ctx.channel.name
        your_friend = your_friend.lower()
        d = self.bot.friends
        if server not in d:
            d[server] = []

        if your_friend not in d[server]:
            d[server].append(your_friend)
            await ctx.send(f"**{nick}** added the nick {your_friend} to your friends list.\n"
                           f"Current list: {', '.join(d[server])}")
        else:
            d[server].remove(your_friend)
            await ctx.send(f"**{nick}** removed the nick {your_friend} from your friends list.\n"
                           f"Current list: {', '.join(d[server])}")
        await utils.replace_one("friends", "list", utils.my_nick(), d)

    # @command(aliases=["ally"])
    async def enemy(self, ctx: Context, country: Country, *, nick: IsMyNick):
        """Adding an ally/enemy to your list.
        The bot will spend more dmg while hunting for an ally, and less when hunting for enemies side.
        It will also give a little push to your allies and against your enemies.
        If the country is already in the list, it will be removed."""
        server = ctx.channel.name

        d = self.bot.allies if ctx.invoked_with.lower() == "ally" else self.bot.enemies
        if server not in d:
            d[server] = []

        if country not in d[server]:
            d[server].append(country)
            await ctx.send(f"**{nick}** added country id {country} to your {ctx.invoked_with} list.\n"
                           f"Current list: {', '.join(str(x) for x in d[server])}")
        else:
            d[server].remove(country)
            await ctx.send(f"**{nick}** removed country id {country} from your {ctx.invoked_with} list.\n"
                           f"Current list: {', '.join(str(x) for x in d[server])}")
        await utils.replace_one(ctx.invoked_with.lower().replace("y", "ies"), "list", utils.my_nick(), d)

    # @command()
    async def hunt(self, ctx: Context, nick: IsMyNick, max_dmg_for_bh: Dmg = 1, weapon_quality: Quality = 5,
                   start_time: int = 60,
                   ticket_quality: Quality = 5, consume_first="none"):
        """Auto hunt BHs (attack and RWs).
        - You can set a list of enemies / allies and the bot will hit half / double for them, see `.help enemy`
        If `nick` contains more than 1 word - it must be within quotes.
        * `consume_first=none` means 1/1 (for fast servers)"""
        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            return await ctx.send(
                f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
        data = {"max_dmg_for_bh": max_dmg_for_bh, "weapon_quality": weapon_quality, "start_time": start_time,
                "ticket_quality": ticket_quality, "consume_first": consume_first}
        ctx.command = f"hunt-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "hunt", data)
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        await ctx.send(f"**{nick}** Starting to hunt at {server}.\n"
                       f"If you want me to stop, type `.cancel hunt-{ctx.message.id} {nick}`")
        avg_hit = 0
        if max_dmg_for_bh == 1:
            try:
                api = await self.bot.get_content(base_url + 'apiCitizenByName.html?name=' + nick.lower())
                tree = await self.bot.get_content(f"{base_url}profile.html?id={api['id']}", return_tree=True)
                avg_hit = float(tree.xpath("//*[@id='hitHelp']/text()")[0].strip().split("-")[-1].replace(",", ""))
            except Exception:
                pass
        should_break = False
        while not should_break:
            battles_time = {}
            for battle in await utils.get_battles(self.bot, base_url):
                round_ends = battle["time_remaining"].split(":")
                battles_time[battle["battle_id"]] = int(round_ends[0]) * 3600 + int(round_ends[1]) * 60 + int(
                    round_ends[2])

            for battle_id, round_ends in sorted(battles_time.items(), key=lambda x: x[1]):
                api_battles = await self.bot.get_content(f'{base_url}apiBattles.html?battleId={battle_id}')
                if api_battles['currentRound'] == 1 and server not in ("secura", "suna", "primera"):
                    break  # first round is longer in some servers
                t = api_battles["hoursRemaining"] * 3600 + api_battles["minutesRemaining"] * 60 + api_battles[
                    "secondsRemaining"]
                if t > round_ends:  # some error
                    break
                if api_battles['frozen'] or t < 10:
                    continue
                if t > start_time:
                    till_next = t - start_time + uniform(-5, 5)
                    await ctx.send(f"**{nick}** Time until <{base_url}battle.html?id={battle_id}&round="
                                   f"{api_battles['currentRound']}>: {timedelta(seconds=round(till_next))}")
                    await sleep(till_next)
                if utils.should_break(ctx):
                    should_break = True
                    break

                defender, attacker = {}, {}
                for hit_record in await self.bot.get_content(
                        f'{base_url}apiFights.html?battleId={battle_id}&roundId={api_battles["currentRound"]}'):
                    side = defender if hit_record['defenderSide'] else attacker
                    if hit_record['citizenId'] in side:
                        side[hit_record['citizenId']] += hit_record['damage']
                    else:
                        side[hit_record['citizenId']] = hit_record['damage']

                a_dmg = sorted(attacker.items(), key=lambda x: x[1], reverse=True)[0][1] if attacker else 0
                d_dmg = sorted(defender.items(), key=lambda x: x[1], reverse=True)[0][1] if defender else 0

                enemies, allies = self.bot.enemies.get(server, []), self.bot.allies.get(server, [])
                max_a_dmg = max_d_dmg = max_dmg_for_bh
                # give a little push to your ally or against your enemy
                if api_battles["defenderId"] in enemies or api_battles["attackerId"] in allies:
                    if api_battles["defenderId"] in enemies:
                        max_d_dmg //= 2
                    if api_battles["attackerId"] in allies:
                        max_a_dmg *= 2
                        a_dmg += 1
                    enemy_dmg, ally_dmg = sum(defender.values()), sum(attacker.values())
                    if 0 <= enemy_dmg - ally_dmg <= max_dmg_for_bh and a_dmg > max_a_dmg:
                        a_dmg = enemy_dmg - ally_dmg

                elif api_battles["attackerId"] in enemies or api_battles["defenderId"] in allies:
                    if api_battles["attackerId"] in enemies:
                        max_a_dmg //= 2
                    if api_battles["defenderId"] in allies:
                        max_d_dmg *= 2
                        d_dmg += 1
                    enemy_dmg, ally_dmg = sum(attacker.values()), sum(defender.values())
                    if 0 <= enemy_dmg - ally_dmg <= max_dmg_for_bh and d_dmg > max_d_dmg:
                        d_dmg = enemy_dmg - ally_dmg

                if a_dmg < max(max_a_dmg, avg_hit):
                    if 10 < a_dmg < 1000:
                        a_dmg = 1000
                    should_break, _ = await ctx.invoke(self.bot.get_command("fight"), nick, battle_id, "attacker",
                                                       weapon_quality, 1 if a_dmg < avg_hit else (a_dmg + 1),
                                                       ticket_quality, consume_first, 0)
                if d_dmg < max(max_d_dmg, avg_hit):
                    if 10 < d_dmg < 1000:
                        d_dmg = 1000
                    should_break, _ = await ctx.invoke(self.bot.get_command("fight"), nick, battle_id, "defender",
                                                       weapon_quality, 1 if d_dmg < avg_hit else (d_dmg + 1),
                                                       ticket_quality, consume_first, 0)
                if should_break:
                    break
            await sleep(30)

        await utils.remove_command(ctx, "auto", "hunt")

    # @command()
    async def duel(self, ctx: Context, nick: IsMyNick, link, max_hits_per_round: Dmg = 100, weapon_quality: Quality = 0,
                   food: Quality = 0, gift: Quality = 0, start_time: int = 0,
                   chance_for_sleep: int = 3, sleep_duration: int = 7, chance_for_nap: int = 27):
        """Auto register and fights in duel tournament.
        By default, every ~33 duels (100/3), it will skip 5-9 hours (7+-2).
        It will also skip ~27% from the rest of the duels.

        * start_time=0 means random.
        """
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        if "duelTournament" not in link:
            return await ctx.send("Not a duel link")
        await ctx.send(f"**{nick}** If you want to cancel it, type `.cancel duel {nick}`")
        while not utils.should_break(ctx):
            ctx.command = f"duel-{ctx.message.id}"
            if uniform(0, 100) < chance_for_sleep:
                rand = uniform(sleep_duration - 2, sleep_duration + 2) * 2
                await ctx.send(f"**{nick}** Sleeping for {timedelta(seconds=round(rand * 30 * 60))}h")
                await sleep(rand * 30 * 60)
            elif uniform(0, 100) < chance_for_nap:
                rand = uniform(1, 2)
                await ctx.send(f"**{nick}** Sleeping for {timedelta(seconds=round(rand * 30 * 60))}h")
                await sleep(rand * 30 * 60)
            else:
                if utils.should_break(ctx):
                    break
                await self.bot.get_content(link)
                url = await self.bot.get_content(link, data={"action": "ENLIST"})
                if not url.endswith("BATTLE_IN_PROGRESS"):
                    await ctx.send(
                        f'**{nick}** <{url}>\nYou can cancel with: `.cancel duel-{ctx.message.id} {nick}` or ' +
                        f'`.click "{nick}" {link} ' + '{"action": "CANCEL_ENLIST"}`')

                    tree = await self.bot.get_content(
                        link.replace("duelTournament.html", "duelTournamentSchedules.html"), return_tree=True)
                    starts_in = tree.xpath("//tr[2]//td[2]//span[1]/text()")[0].replace("Starts: ", "")
                    now = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%H:%M:%S %d-%m-%Y")
                    seconds = (datetime.strptime(starts_in, "%H:%M %d-%m-%Y") -
                               datetime.strptime(now, "%H:%M:%S %d-%m-%Y")).total_seconds()
                    if seconds < 0:
                        await ctx.send(f"**{nick}** {link} is over")
                        break
                    await ctx.send(f"**{nick}** Round starts in {timedelta(seconds=seconds)}")
                    await sleep(seconds + uniform(60, 80))
                if utils.should_break(ctx):
                    break
                tree = await self.bot.get_content(link, return_tree=True)
                my_id = utils.get_ids_from_path(tree, '//*[@id="userName"]')[0]
                attacker, battle, defender = tree.xpath("//*[@class='highlighted']//@href")[:3]
                side = "attacker" if attacker.endswith(f"={my_id}") else "defender"
                await ctx.invoke(self.bot.get_command("hunt_battle"), nick, base_url + battle, side, max_hits_per_round,
                                 weapon_quality, food, gift, start_time)

    # @command()
    async def hunt_battle(self, ctx: Context, nick: IsMyNick, battle: Id, side: Side, dmg_or_hits_per_bh: Dmg = 1,
                          weapon_quality: Quality = 0, food: Quality = 5, gift: Quality = 5, start_time: int = 0):
        """Hunting BH at a specific battle.
        (Good for practice battle / leagues / civil war)

        * if dmg_or_hits < 1000 - it's hits, otherwise - dmg.
        If `nick` contains more than 1 word - it must be within quotes."""

        data = {"link": battle, "side": side, "dmg_or_hits_per_bh": dmg_or_hits_per_bh,
                "weapon_quality": weapon_quality, "food": food, "gift": gift, "start_time": start_time}

        ctx.command = f"hunt_battle-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "hunt_battle", data)

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        link = f"{base_url}battle.html?id={battle}" if not str(battle).startswith("http") else battle
        dmg = dmg_or_hits_per_bh
        hits_or_dmg = "hits" if dmg <= 1000 else "dmg"
        while not utils.should_break(ctx):  # For each round
            api = await self.bot.get_content(link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (api['defenderScore'], api['attackerScore']):
                await ctx.send(f"**{nick}** <{link}> is over")
                break
            seconds_till_round_end = api["hoursRemaining"] * 3600 + api["minutesRemaining"] * 60 + api[
                "secondsRemaining"]
            if seconds_till_round_end < 20:
                await sleep(30)
                continue
            seconds_till_hit = uniform(10, seconds_till_round_end - 10) if start_time < 10 else (
                    seconds_till_round_end - start_time + uniform(-5, 5))
            await ctx.send(
                f"**{nick}** {round(seconds_till_hit)} seconds from now (at T {timedelta(seconds=round(seconds_till_round_end - seconds_till_hit))}),"
                f" I will hit {dmg} {hits_or_dmg} at <{link}> for the {side} side.\n"
                f"If you want to cancel it, type `.cancel hunt_battle-{ctx.message.id} {nick}`")
            await sleep(seconds_till_hit)
            tree = await self.bot.get_content(link, return_tree=True)
            top = tree.xpath(f'//*[@id="top{side}1"]//div[3]/text()')
            if dmg_or_hits_per_bh == 1 and top and int(str(top[0]).replace(",", "").strip()) != 0:
                await ctx.send(f"**{nick}** someone else already fought in this round <{link}>")
                await sleep(seconds_till_round_end - seconds_till_hit + 15)
                continue
            food_limit, gift_limit = utils.get_limits(tree)
            food_storage, gift_storage = utils.get_storage(tree)
            damage_done = 0
            fight_url, data = await self.get_fight_data(base_url, tree, weapon_quality, side,
                                                        value=("Berserk" if dmg >= 5 else ""))
            while damage_done < dmg and not utils.should_break(ctx):
                health = utils.get_health(tree)
                if not health:
                    tree = await self.bot.get_content(link, return_tree=True)
                    health = utils.get_health(tree)
                    if not any([health, food, gift]):
                        break
                restore_needed = (dmg < 5 and health == 0) or (dmg >= 5 and health < 50)
                if not (food or gift) and restore_needed:
                    break
                if (food or gift) and restore_needed:
                    if (food and food_storage == 0) and (gift and gift_storage == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift storage error")
                    if (food and food_limit == 0) and (gift and gift_limit == 0):
                        return await ctx.send(f"**{nick}** ERROR: food/gift limits error")
                    if food and food_storage > 0 and food_limit > 0:
                        food_storage -= 1
                        food_limit -= 1
                        await self.bot.get_content(f"{base_url}eat.html", data={'quality': 5})
                    elif gift and gift_storage > 0 and gift_limit > 0:
                        gift_storage -= 1
                        gift_limit -= 1
                        await self.bot.get_content(f"{base_url}gift.html", data={'quality': 5})
                    else:
                        return await ctx.send(f"**{nick}** ERROR: I couldn't restore health.")
                    health += 50

                tree = await self.bot.get_content(fight_url, data=data, return_tree=True)
                if not tree.xpath('//*[@id="DamageDone"]'):
                    if "Slow down a bit!" in tree.text_content():
                        await sleep(1)
                        continue
                    if "No health left" in tree.text_content():
                        continue
                    if "Round is closed" in tree.text_content():
                        break
                    res = tree.xpath('//div//div/text()')
                    await ctx.send(f"**{nick}** ERROR: {' '.join(res).strip()}")
                    break
                if dmg < 5:
                    damage_done += 1
                elif dmg <= 1000:
                    damage_done += 5
                else:
                    damage_done += int(str(tree.xpath('//*[@id="DamageDone"]')[0].text).replace(",", ""))
                await sleep(uniform(0, 0.2))

            await ctx.send(f"**{nick}** done {damage_done:,} {hits_or_dmg} at <{link}>")
            if not utils.should_break(ctx):
                await sleep(seconds_till_round_end - seconds_till_hit + 15)

        await utils.remove_command(ctx, "auto", "hunt_battle")

    @command()
    async def auto_motivate(self, ctx: Context, chance_to_skip_a_day: Optional[int] = 5, *, nick: IsMyNick):
        """Motivates at random times throughout every day"""
        await utils.save_command(ctx, "auto", "motivate", {"chance_to_skip_a_day": chance_to_skip_a_day})

        await ctx.send(f"**{nick}** Starting to motivate every day with {chance_to_skip_a_day}% chance to skip a day.\n"
                       f"Cancel with `.cancel auto_motivate {nick}`")

        while not utils.should_break(ctx):  # for every day:
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
            sec_til_midnight = (midnight - now).seconds
            await sleep(uniform(0, sec_til_midnight - 600))
            if not utils.should_break(ctx) and randint(1, 100) > chance_to_skip_a_day:
                await ctx.invoke(self.bot.get_command("motivate"), nick=nick)

            # sleep till midnight
            tz = timezone('Europe/Berlin')
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), dt_time(0, 0, 0, 0)))
            await sleep((midnight - now).seconds + 20)

            data = (await utils.find_one("auto", "motivate", os.environ['nick']))[ctx.channel.name]
            if isinstance(data, list):
                data = data[0]
            chance_to_skip_a_day = data["chance_to_skip_a_day"]
        await utils.remove_command(ctx, "auto", "motivate")

    @command()
    async def motivate(self, ctx, item: Optional[MotivateType] = None, *, nick):
        """
        Motivate 5 new citizens (newest first).
        item: weapons (Q1) / food (Q3) / gift (Q3) / tickets (Q1) / any, ή με κόμμα π.χ. food,gift (σειρά προτίμησης).
        Χωρίς item = any (food, gift, tickets, weapons).
        Παράδειγμα: .motivate food Kostas
        """
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        # ----------- Ποιους citizens θα δοκιμάσει -----------
        # Πρώτα όσους δείχνει η λίστα New Citizens (δεν έχει τους "too old"), μετά ανά id προς τα πίσω.
        # Αν η λίστα είναι κενή σε κάποιον server: newest id από το API και προς τα πίσω.
        try:
            listed = await self.citizens_from_list(base_url)
            start = (min(listed) - 1) if listed else await self.find_newest_citizen(base_url)
        except Exception as e:
            await ctx.send(f"**{nick}** ERROR: couldn't find the newest citizens ({e})")
            return
        newest = listed[0] if listed else start
        await ctx.send(f"**{nick}** Newest citizen: <{base_url}profile.html?id={newest}>. "
                       f"{len(listed)} in the New Citizens list, then going backwards by id...")
        candidates = chain(listed, range(start, 0, -1))

        types = item or ["FOOD", "GIFTS", "TICKETS", "WEAPONS"]
        sent_count, checked, failed_in_a_row = 0, [], 0
        max_checks = 300  # πόσους citizens ελέγχουμε το πολύ

        for citizen_id in islice(candidates, max_checks):
            if sent_count >= 5 or utils.should_break(ctx):
                break
            profile = f"<{base_url}profile.html?id={citizen_id}>"
            for attempt in range(2):  # π.χ. η σελίδα δεν φόρτωσε: ξαναδοκίμασε τον ίδιο citizen μία φορά
                try:
                    result = await self.motivate_citizen(base_url, citizen_id, types)
                    break
                except Exception as e:
                    result = {"status": "error", "msg": str(e).strip().splitlines()[0][:200]}
                    await sleep(uniform(3, 6))

            if result["status"] == "sent":
                sent_count += 1
                failed_in_a_row = 0
                checked.append(f"✅ Sent {result['type']} to {result['name']} {profile}")
            elif result["status"] == "limit":
                checked.append(f"🛑 {result['msg']}")
                break
            elif result["status"] == "failed":
                failed_in_a_row += 1
                checked.append(f"❌ Couldn't motivate {result['name']} {profile}: {result['msg']}")
            elif result["status"] == "error":
                checked.append(f"⚠️ Error for {profile}: {result['msg']}")
            # "skip" = too old / already motivated -> χωρίς μήνυμα

            if failed_in_a_row >= 3:
                checked.append("Stopping: 3 failures in a row (daily limit reached or missing items?)")
                break

            if len(checked) >= 5:
                await ctx.send(f"**{nick}**\n" + "\n".join(checked))
                checked.clear()
            # πιο αργά μετά από motivation, πιο γρήγορα όταν απλώς προσπερνάει
            await sleep(uniform(4, 9) if result["status"] == "sent" else uniform(1.5, 3.5))

        if checked:
            await ctx.send(f"**{nick}**\n" + "\n".join(checked))
        await ctx.send(f"**{nick}** Motivated {sent_count} citizens.")

    async def citizen_exists(self, base_url: str, citizen_id: int) -> bool:
        """
        Ελέγχει στο apiCitizenById.html αν υπάρχει ο citizen. Χρησιμοποιεί το δεύτερο (incognito) παράθυρο,
        όπως όλα τα api του bot, ώστε να μη φαίνεται στο παράθυρο του λογαριασμού.
        """
        driver = self.bot.incognito_window
        for _ in range(4):
            await sleep(uniform(0.4, 1.2))
            driver.get(f"{base_url}apiCitizenById.html?id={citizen_id}")
            body = driver.find_element(By.TAG_NAME, "body").text
            if '"login"' in body:
                return True
            if "No citizen" in body:
                return False
            await sleep(1.5)
        raise ConnectionError(f"API did not answer for id {citizen_id}")

    async def citizens_from_list(self, base_url: str) -> list:
        """Τα ids της λίστας New Citizens, νεότερος πρώτος (τα ονόματα έχουν onmousedown="...('profile?id=123', event)")."""
        tree = await self.bot.get_content(f"{base_url}newCitizens.html?countryId=0", return_tree=True)
        await sleep(uniform(1, 3))
        ids = {int(x) for link in tree.xpath('//table//a[contains(@onmousedown, "profile") or contains(@href, "profile")]')
               for x in re.findall(r"id=(\d+)", link.get("onmousedown", "") + link.get("href", ""))}
        return sorted(ids, reverse=True)

    async def find_newest_citizen(self, base_url: str) -> int:
        """Binary search στα citizen ids (τα ids δίνονται με τη σειρά)."""
        lo, hi = 1, 1024
        while await self.citizen_exists(base_url, hi):
            lo, hi = hi, hi * 2
        while hi - lo > 1:
            middle = (lo + hi) // 2
            if await self.citizen_exists(base_url, middle):
                lo = middle
            else:
                hi = middle
        # σε περίπτωση κενών στα ids, κοίτα λίγο πιο πάνω
        i = 1
        while i <= 30:
            if await self.citizen_exists(base_url, lo + i):
                lo, i = lo + i, 1
            else:
                i += 1
        return lo

    async def motivate_citizen(self, base_url: str, citizen_id: int, types: list) -> dict:
        """
        Ανοίγει το motivateCitizen.html και πατάει Motivate στο πρώτο διαθέσιμο type.
        status: sent / skip (too old / ήδη motivated) / limit / failed
        """
        driver = self.bot.browser_window
        url = f"{base_url}motivateCitizen.html?id={citizen_id}"

        def read_page():
            text = " ".join(driver.find_element(By.TAG_NAME, "main").get_attribute("textContent").split())
            text = text.split("Your storage")[0]
            name = re.search(r"^Motivate (.+?) (This citizen|\d+x)", text)
            buttons = {}  # μόνο φόρμες με κουμπί (όσες έχουν σταλεί δεν έχουν)
            for form in driver.find_elements(By.CSS_SELECTOR, "main form"):
                type_input = form.find_elements(By.CSS_SELECTOR, "input[name='type']")
                button = form.find_elements(By.TAG_NAME, "button")
                if type_input and button:
                    buttons[type_input[0].get_attribute("value")] = button[0]
            return (name.group(1) if name else str(citizen_id)), text, buttons

        async def load_page():
            """Ανοίγει τη σελίδα και περιμένει να φορτώσει πλήρως (το get_content περιμένει μόνο το <body>)."""
            for _ in range(3):
                await self.bot.get_content(url)
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                        and d.find_elements(By.TAG_NAME, "main"))
                    return read_page()
                except TimeoutException:
                    await sleep(uniform(2, 4))
            raise TimeoutError(f"the motivate page didn't load")

        name, text, buttons = await load_page()
        if not buttons or "You already motivated" in text:
            return {"status": "skip", "name": name}

        msgs = []
        for type_ in types:
            if type_ not in buttons:
                continue
            await sleep(uniform(1.5, 3.5))  # "διαβάζει" τη σελίδα πριν πατήσει
            ActionChains(driver).move_to_element(buttons[type_]).pause(uniform(0.3, 0.8)).click().perform()
            # περίμενε να φύγει από τη σελίδα (profile.html = επιτυχία, motivateCItizen.html = error)
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: d.current_url != url and d.execute_script("return document.readyState") == "complete")
            except TimeoutException:
                pass
            if "profile.html" in driver.current_url:
                return {"status": "sent", "type": type_, "name": name}
            errors = driver.find_elements(By.CSS_SELECTOR, "#newError, .newError")
            error = " ".join(errors[0].get_attribute("textContent").split()) if errors else "unknown error"
            if "too many motivations" in error.lower():
                return {"status": "limit", "name": name, "msg": error}
            msgs.append(f"{type_}: {error[:120]}")
            await sleep(uniform(1, 2))
            name, text, buttons = await load_page()
            if "You already motivated" in text:  # τελικά στάλθηκε
                return {"status": "sent", "type": type_, "name": name}
        return {"status": "failed", "name": name, "msg": " | ".join(msgs) or "no motivate forms"}

    # @command(aliases=["dow", "mpp"])
    async def attack(self, ctx: Context, country_or_region_id: Id, delay: Optional[int] = 0, *, nick: IsMyNick):
        """
        Attack region / Declare war / Propose MPP
        Possible after a given delay.
        """
        action = ctx.invoked_with.lower()
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if delay:
            await ctx.send(
                f"**{nick}** Ok. Sleeping for {delay} seconds. You can cancel with `.cancel {ctx.command} {nick}`")
            await sleep(delay)
            if utils.should_break(ctx):
                return

        if action == "attack":
            payload = {'action': "ATTACK_REGION", 'regionId': country_or_region_id, 'submit': "Attack"}
        elif action == "mpp":
            payload = {'action': "PROPOSE_ALLIANCE", 'countryId': country_or_region_id, 'submit': "Propose alliance"}
        elif action == "dow":
            payload = {'action': "DECLARE_WAR", 'dowCountryId': country_or_region_id, 'submit': "Declare war"}
        else:
            return
        await self.bot.get_content(base_url + "countryLaws.html")
        url = await self.bot.get_content(base_url + "countryLaws.html", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def medkit(self, ctx, *, nick: IsMyNick):
        """Using a medkit"""
        server = ctx.channel.name
        await self.bot.get_content(f"https://{server}.e-sim.org/index.html")
        url = await self.bot.get_content(f"https://{server}.e-sim.org/medkit.html", data={})
        await ctx.send(f"**{nick}** MEDKIT: <{url}>")
        if url.endswith("MESSAGE_OK"):  # update db
            data = await utils.find_one(server, "info", nick)
            medkits = int(data.get("medkits", 0))
            data["medkits"] = str(medkits - 1)
            await utils.replace_one(server, "info", nick, data)

    # @command(aliases=["upgrade"])
    async def reshuffle(self, ctx: Context, eq_id_or_link: Id, parameter, *, nick: IsMyNick):
        """
        Reshuffle/upgrade a specific parameter.
        Parameter example: Increase chance to avoid damage by 7.08%
        If it's not working, you can try writing "first", "second" or "last" as a parameter.
        (you can also try "avoid", but sometimes there may be unexpected behavior)

        it's recommended to copy and paste the parameter, but you can also write first/last
        """
        action = ctx.invoked_with
        if action.lower() not in ("reshuffle", "upgrade"):
            return await ctx.send(f"**{nick}** ERROR: 'action' parameter can be reshuffle/upgrade only (not {action})")
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"

        link = f"{base_url}showEquipment.html?id={eq_id_or_link}"
        tree = await self.bot.get_content(link, return_tree=True)
        eq = tree.xpath('//*[@id="esim-layout"]//div/div[3]/div/h4/text()')
        parameter_id = tree.xpath('//*[@id="esim-layout"]//div/div[3]/div/h3/text()')
        parameter = parameter.lower()
        if parameter in eq[0].replace("by  ", "by ").lower() or parameter == "first":
            parameter_id = parameter_id[0].split("#")[1]
        elif parameter in eq[1].replace("by  ", "by ").lower() or parameter == "second":
            parameter_id = parameter_id[1].split("#")[1]
        elif parameter in eq[-1].replace("by  ", "by ").lower() or parameter in ("last", "third"):
            parameter_id = parameter_id[-1].split("#")[1]
        else:
            return await ctx.send(
                f"**{nick}** ERROR: I did not find the parameter {parameter} at <{link}>. Try copy & paste.")
        payload = {'parameterId': parameter_id, 'action': f"{action.upper()}_PARAMETER", "submit": action.capitalize()}
        url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
        if not url.endswith("SPLIT_ITEM_OK"):
            return await ctx.send(f"**{nick}** <{url}>")
        api_link = f"{base_url}apiEquipmentById.html?id={eq_id_or_link}"
        api = await self.bot.get_content(api_link)
        embed = Embed(url=link, title=f"{nick} Q{api['EqInfo'][0]['quality']} {api['EqInfo'][0]['slot'].title()}")
        embed.add_field(name="Parameters:", value="\n".join(
            f"**{x['Name']}:** {round(x['Value'], 3)}" for x in api['Parameters']))
        await ctx.send(embed=embed)

    # @command()
    async def rw(self, ctx: Context, region_id_or_link: Id, ticket_quality: Optional[int] = 5, delay: Optional[int] = 0,
                 *,
                 nick: IsMyNick):
        """Opens RW (Resistance War).
        `delay` means how many seconds the bot should wait before opening the RW.
        Note: region can be link or id."""
        if delay > 0:
            await ctx.send(f"**{nick}** Ok. If you changed your mind, type `.cancel rw {nick}`")
            await sleep(delay)
        if not utils.should_break(ctx):
            base_url = f"https://{ctx.channel.name}.e-sim.org/"
            region_link = f"{base_url}region.html?id={region_id_or_link}"
            if not await ctx.invoke(self.bot.get_command("fly"), region_id_or_link, ticket_quality, nick=nick):
                return
            tree = await self.bot.get_content(region_link, data={"submit": "Start resistance"}, return_tree=True)
            result = tree.xpath("//*[@id='esim-layout']//div[2]/text()")[0]
            await ctx.send(f"**{nick}** {result}")

    # @command()
    async def pack(self, ctx: Context, nick: IsMyNick, wep_quality: Quality, weps: int = 200, food: int = 15,
                   gift: int = 15,
                   tickets_quality: Quality = 0, tickets: int = 0):
        """Sends a pack of supply from your MU.
        Examples:
            .pack "my nick" Q1                    (it will send the default amounts: 15/15 and 200 Q1 weps)
            .pack "my nick" Q5 150 20 15 Q1 20    (it will send: 20/15 food/gift, 150 Q5 weps, 20 Q1 tickets)
        """
        data = [(food, 5, "FOOD"), (gift, 5, "GIFT"), (weps, wep_quality, "WEAPON"),
                (tickets, tickets_quality, "TICKET")]
        shuffle(data)
        for entry in data:
            if entry[0] and entry[1]:
                await ctx.invoke(self.bot.get_command("supply"), entry[0], entry[1], entry[2], nick=nick)
                await sleep(uniform(1, 5))

    # @command()
    async def supply(self, ctx: Context, amount: int, quality: Optional[Quality], product: Product, *, nick: IsMyNick):
        """Taking a specific product from MU storage."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        tree = await self.bot.get_content(base_url + "militaryUnitStorage.html", return_tree=True)
        my_id = utils.get_ids_from_path(tree, '//*[@id="userName"]')[0]
        payload = {'product': f"{quality or 5}-{product}", 'quantity': amount,
                   "reason": "", "citizen1": my_id, "submit": "Donate"}
        url = await self.bot.get_content(base_url + "militaryUnitStorage.html", data=payload)
        if "index" in url:
            await ctx.send(f"**{nick}** You are not in any military unit.")
        else:
            await ctx.send(f"**{nick}** {amount} Q{payload['product']} <{url}>")

    # @command(aliases=["gift"])
    async def food(self, ctx: Context, quality: Optional[int] = 5, *, nick: IsMyNick):
        """Using food or gift"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        await self.bot.get_content(f"{base_url}index.html")
        url = await self.bot.get_content(f"{base_url}{ctx.invoked_with.lower().replace('food', 'eat')}.html",
                                         data={'quality': quality})
        await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def watch(self, ctx: Context, nick: IsMyNick, battle: Id, side: Side, start_time: int = 60,
                    keep_wall: Dmg = 3000000, let_overkill: Dmg = 10000000, weapon_quality: Quality = 5,
                    ticket_quality: Quality = 5, consume_first="gift", medkits: int = 0):
        """Fight at the last minutes of every round in a given battle.

        Examples:
        .watch https://alpha.e-sim.org/battle.html?id=1 defender
        In this example, it will start fighting at t1, and will try to keep a default 3kk wall (checking every ~10 sec),
        and if enemies did more than 10kk it will skip the round.

        If link="https://alpha.e-sim.org/battle.html?id=1", side="defender", start_time=120, keep_wall="5kk", let_overkill="15kk"
        it will start fighting at ~t2 (120+-5 secs), it will keep a 5kk wall (checking every ~10 sec),
        and if enemies did more than 15kk it will skip the round.

        * It will increase the wall for every fighting enemy, to compensate for the delay.
        * If `nick` contains more than 1 word - it must be within quotes.
        """
        consume_first = consume_first.lower()
        if consume_first not in ("food", "gift", "none"):
            return await ctx.send(
                f"**{nick}** `consume_first` parameter must be food, gift, or none (not {consume_first})")
        data = {"battle": battle, "side": side, "start_time": start_time, "keep_wall": keep_wall,
                "let_overkill": let_overkill, "weapon_quality": weapon_quality, "ticket_quality": ticket_quality,
                "consume_first": consume_first, "medkits": medkits}
        ctx.command = f"watch-{ctx.message.id}"
        await utils.save_command(ctx, "auto", "watch", data)

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_citizen = await self.bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')
        battle_link = f"{base_url}battle.html?id={battle}"
        error = False
        while not error:
            ctx.invoked_with = "watch"
            r = await self.bot.get_content(battle_link.replace("battle", "apiBattles").replace("id", "battleId"))
            if 8 in (r['defenderScore'], r['attackerScore']):
                break
            sleep_time = r["hoursRemaining"] * 3600 + r["minutesRemaining"] * 60 + r[
                "secondsRemaining"] - start_time + uniform(-5, 5)
            if sleep_time > 0:
                await ctx.send(f"**{nick}** Sleeping for {round(sleep_time)} seconds :zzz:"
                               f"\nIf you want me to stop, type `.cancel watch-{ctx.message.id} {nick}`")
                await sleep(sleep_time)
            if utils.should_break(ctx):
                break
            await ctx.send(f"**{nick}** T{round(start_time / 60, 1)} at <{battle_link}&round={r['currentRound']}>")
            tree = await self.bot.get_content(battle_link, return_tree=True)
            hidden_id = tree.xpath("//*[@id='battleRoundId']")[0].value

            while not error:
                # TODO
                battle_score = await self.bot.get_content(
                    f'{base_url}battleScore.html?id={hidden_id}&at={api_citizen["id"]}&ci={api_citizen["citizenshipId"]}&premium=1')
                if battle_score["remainingTimeInSeconds"] <= 0:
                    break
                my_side = int(battle_score[f"{side}Score"].replace(",", ""))
                enemy = "defender" if side == "attacker" else "attacker"
                enemy_side = int(battle_score[enemy + "Score"].replace(",", ""))
                wall = keep_wall * (battle_score[f"{enemy}sOnline"] + 1) if battle_score["spectatorsOnline"] != 1 else 1
                if enemy_side - my_side < let_overkill and my_side - enemy_side < wall:
                    error, medkits = await ctx.invoke(self.bot.get_command("fight"), nick, battle, side, weapon_quality,
                                                      max(enemy_side - my_side + wall, 10001), ticket_quality,
                                                      consume_first, medkits)
                    ctx.invoked_with = "fight_fast"
                await sleep(uniform(6, 13))

            await utils.idle(self.bot, [battle_link, base_url, base_url + "battles.html"])

        await utils.remove_command(ctx, "auto", "watch")

    # @command(aliases=["unwear"])
    async def wear(self, ctx: Context, ids, *, nick: IsMyNick):
        """
        Wear/take off a specific EQ IDs.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        ids = [int(x.replace("#", "").replace(f"{base_url}showEquipment.html?id=", "").strip()) for x in ids.split(",")
               if x.strip()]
        await self.bot.get_content(f"{base_url}storage.html?storageType=EQUIPMENT")
        for eq_id in ids:
            if utils.should_break(ctx):
                break
            payload = {'action': "PUT_OFF" if ctx.invoked_with.lower() == "unwear" else "EQUIP", 'itemId': eq_id}
            url = await self.bot.get_content(f"{base_url}equipmentAction.html", data=payload)
            await sleep(uniform(1, 2))
            if url == "http://www.google.com/":  # noqa
                # e-sim error
                await sleep(uniform(2, 5))
            results.append(f"ID {eq_id} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))

    # @command()
    async def hunt_events(self, ctx: Context, nick: IsMyNick, dmg_or_hits_per_bh: Dmg = 1,
                          weapon_quality: Quality = 0, food: Quality = 5, gift: Quality = 5, start_time: int = 0):
        """Checks every ~10 minutes if there's a new event battle, and start hunt_battle on it."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api_citizen = await self.bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')
        my_citizenship_id = api_citizen["citizenshipId"]
        my_citizenship = api_citizen["citizenship"]
        await ctx.send(f"**{nick}** Ok. You can cancel with `.cancel hunt_events {nick}`")
        added_battles = []
        while not utils.should_break(ctx):
            try:
                battles = await utils.get_battles(self.bot, base_url, country_id=my_citizenship_id,
                                                  normal_battles=False)
            except Exception:
                battles = []
            for battle in battles:
                if my_citizenship.lower() == battle["defender"]["name"].lower():
                    side = "defender"
                elif my_citizenship.lower() == battle["attacker"]["name"].lower():
                    side = "attacker"
                else:
                    continue
                battle_id = battle["battle_id"]
                if battle_id not in added_battles:
                    added_battles.append(battle_id)
                    self.bot.loop.create_task(ctx.invoke(
                        self.bot.get_command("hunt_battle"), nick, battle_id, side, dmg_or_hits_per_bh,
                        weapon_quality, food, gift, start_time))
            await sleep(uniform(500, 700))


def setup(bot):
    """setup"""
    bot.add_cog(War(bot))
