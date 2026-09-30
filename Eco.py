"""Eco.py"""
import json
import os
from asyncio import sleep
from datetime import datetime, time, timedelta
from random import choice, randint, uniform
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from random import choice, uniform, randint
from asyncio import sleep
import os, json

from random import choice, uniform, randint
from asyncio import sleep
import os, json
from discord.ext.commands import command

import os
import json
import asyncio
from random import randint, uniform, choice
from discord.ext.commands import command

from utils import should_break
import os
import json
import asyncio
from random import choice, uniform, randint
import time as time_module  # το `time` από κάτω είναι το datetime.time
from asyncio import sleep  # async sleep (όλα τα "await sleep(...)" του αρχείου)
from lxml import html
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


from discord import Embed
from discord.ext.commands import Cog, Context, command
from pytz import timezone

import utils
from Converters import Country, Id, IsMyNick, MotivateType, Product, Quality
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from random import shuffle
import re


class Eco(Cog):
    """Eco Commands"""

    def __init__(self, bot):
        self.bot = bot

    # @command()
    async def contract(self, ctx: Context, contract_id: Optional[Id] = 0, *, nick: IsMyNick):
        """Accept specific contract id.
        Write 0 as contract_id to get the list of contracts"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if contract_id == 0:
            tree = await self.bot.get_content(f"{base_url}contracts.html", return_tree=True)
            text = [x.text_content().strip().replace("\n", " ").replace("\t", "") for x in
                    tree.xpath('//*[@id="esim-layout"]//div[2]//ul//li')[:5]]
            links = utils.get_ids_from_path(tree, '//*[@id="esim-layout"]//div[2]//ul//li//a')[::2][:5]
            if links:
                embed = Embed(title=nick)
                embed.add_field(name="Contracts (first 5)", value="\n".join(
                    f"[{t}]({base_url}profile.html?id={link})" for t, link in zip(text, links)))
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"**{nick}** no pending contracts")
        else:
            payload = {'action': "ACCEPT", "submit": "Accept"}
            await self.bot.get_content(f"https://{ctx.channel.name}.e-sim.org/contract.html?id={contract_id}")
            url = await self.bot.get_content(f"https://{ctx.channel.name}.e-sim.org/contract.html?id={contract_id}",
                                             data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command()
    async def bid(self, ctx, auction: Id, price: float, delay: Optional[bool] = False, *, nick: IsMyNick):
        """Bidding an auction few seconds before its end"""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if delay:
            tree = await self.bot.get_content(f"{base_url}auction.html?id={auction}", return_tree=True)
            try:
                auction_time = str(tree.xpath(f'//*[@id="auctionClock{auction}"]')[0].text)
            except Exception:
                return await ctx.send(f"**{nick}** ERROR: This auction has probably finished. if you think this"
                                      f" is a mistake - set delay to False")
            h, m, s = auction_time.split(":")
            t = randint(15, 60)
            delay_in_seconds = int(h) * 3600 + int(m) * 60 + int(s) - t
            await ctx.send(f"**{nick}** Ok, I will bid ~{t} seconds before the auction ends")
            await sleep(delay_in_seconds)
        if not delay or not utils.should_break(ctx):
            payload = {'action': "BID", 'id': auction, 'price': f"{float(price):.2f}"}
            await self.bot.get_content(f"{base_url}auction.html?id={auction}")
            url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    @command(hidden=True)
    async def set_auctions_prices(self, ctx: Context, nick: IsMyNick, *, prices: str = "{}"):
        """
        - Write .set_auctions_prices <nick> to see current prices (first use shows a draft)
        - You MUST paste the entire text and just change the prices you want

        For each item, you can specify prices in the following formats:
        1. A single price, for example: `"helmet3": 1.1`. In this case, the bot will bid 1.1 gold on all Q3 helmets.
        2. Multimple prices, for example `"helmet3": "1, 1.1, 1.2"`. In this case, the bot will bid any price from that list randomly.
        3. Range of prices, for example `"helmet3": "1-1.2"`. In this case, the bot will bid any price from that range (min 1, max 1.2).
        4. Any combination of the above, for example `"helmet3": "2, 1-1.2, 1.5-1.8"`. In this case, the bot will bid 2g on third of the auctions, another third will be from the range 1-1.2, and the rest from the range 1.5-1.8
        - You can also bid companies by qualities: `{"q1": "0", "q2": "0", "q3": "0", "q4": "0", "q5": "0"}
        """
        server = ctx.channel.name
        file_name = f"auctions_prices_{server}.json"
        prices = json.loads(prices.replace("'", '"'))
        if not prices:
            if file_name in os.listdir():
                with open(file_name, "r", encoding="utf-8") as file:
                    await ctx.send("Current prices:\n" + file.read())
            else:
                await ctx.send(
                    "Here's a draft:\n"
                    f'.set_auctions_prices "{nick}" ' +
                    '```json\n{"helmet1": "0.1-0.3", "helmet2": "0.6,0.7", "helmet3": "0", "helmet4": "0", "helmet5": "0", "helmet6": "0", "helmet7": "0",\n'
                    '"vision1": "0", "vision2": "0", "vision3": "0", "vision4": "0", "vision5": "0", "vision6": "0", "vision7": "0",\n'
                    '"weapon1": "0", "weapon2": "0", "weapon3": "0", "weapon4": "0", "weapon5": "0", "weapon6": "0", "weapon7": "0",\n'
                    '"offhand1": "0", "offhand2": "0", "offhand3": "0", "offhand4": "0", "offhand5": "0", "offhand6": "0", "offhand7": "0",\n'
                    '"armor1": "0", "armor2": "0", "armor3": "0", "armor4": "0", "armor5": "0", "armor6": "0", "armor7": "0",\n'
                    '"pants1": "0", "pants2": "0", "pants3": "0", "pants4": "0", "pants5": "0", "pants6": "0", "pants7": "0",\n'
                    '"shoes1": "0", "shoes2": "0", "shoes3": "0", "shoes4": "0", "shoes5": "0", "shoes6": "0", "shoes7": "0",\n'
                    '"charm1": "0", "charm2": "0", "charm3": "0", "charm4": "0", "charm5": "0", "charm6": "0", "charm7": "0",\n\n'

                    '"jinxedElixirMili": "0", "jinxedElixirMini": "0", "jinxedElixirStandard": "0", "jinxedElixirMajor": "0", "jinxedElixirHuge": "0", "jinxedElixirExceptional": "0",\n'
                    '"fineseElixirMili": "0", "fineseElixirMini": "0", "fineseElixirStandard": "0", "fineseElixirMajor": "0", "fineseElixirHuge": "0", "fineseElixirExceptional": "0",\n'
                    '"bloodyMessElixirMili": "0", "bloodyMessElixirMini": "0", "bloodyMessElixirStandard": "0", "bloodyMessElixirMajor": "0", "bloodyMessElixirHuge": "0", "bloodyMessElixirExceptional": "0",\n'
                    '"luckyElixirMili": "0", "luckyElixirMini": "0", "luckyElixirStandard": "0", "luckyElixirMajor": "0", "luckyElixirHuge": "0", "luckyElixirExceptional": "0",\n\n'

                    '"reshuffle": "0", "upgrade": "0", "vacations": "0", "spa": "0", "resistance": "0", "bunker": "0", "steroids": "0", "tank": "0",\n'
                    '"camouflage_first_class": "0", "camouflage_second_class": "0", "camouflage_third_class": "0",\n'
                    '"bandagea": "0","bandageb": "0","bandagec": "0","bandaged": "0","bandagee": "0","bandagef": "0",\n'
                    '"painDealer1h": "0", "painDealer10h": 0, "painDealer25h": ""}```')
                await ctx.send_help("set_auctions_prices")
        else:
            with open(file_name, "w", encoding="utf-8") as file:
                json.dump(prices, file)
            await ctx.send(f"**{nick}** I have created a file named `{file_name}` containing those prices.\n"
                           f"You can edit it any time, or invoke the command again with all prices.\n"
                           f'You can now use `.bid_all_auctions {nick}`')

    @command()
    async def bid_all_auctions(self, ctx, *, nick: IsMyNick):
        """Bidding on all auctions.
        Type `.help set_auctions_prices` to see how to set the prices.
        You can set up friends that you won't overbid. See `.help friend`
        """

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        file_name = f"auctions_prices_{server}.json"
        friends_file = f"custom_friends_{server}.json"

        # Load auction prices
        if file_name not in os.listdir():
            return await ctx.invoke(
                self.bot.get_command("set_auctions_prices"),
                nick=nick
            )

        with open(file_name, "r", encoding="utf-8") as file:
            prices = json.load(file)

        # Load custom friends
        custom_friends = []
        if friends_file in os.listdir():
            with open(friends_file, "r", encoding="utf-8") as file:
                custom_friends = json.load(file)

        custom_friends = [friend.lower() for friend in custom_friends]

        await ctx.send(
            f"**{nick}** Ok. You can cancel with "
            f"`.cancel bid_all_auctions {nick}`"
        )

        # Friends: in-game friends + custom friends + own nick
        all_friends = set([nick.lower()] + [f.lower() for f in self.bot.friends.get(server, [])] + custom_friends)
        # Τα ονόματα των items στη σελίδα -> ονόματα στο auctions_prices_<server>.json
        eq_aliases = {"weapon_upgrade": "weapon", "personal_armor": "armor", "lucky_charm": "charm"}
        normalized_keys = {k.lower().replace("_", ""): k for k in prices}

        def price_key(auction_item: str) -> str:
            parts = auction_item.split()
            if not parts:
                return ""
            if len(parts) > 1 and re.fullmatch(r"Q\d", parts[0]):  # "Q7 WEAPON_UPGRADE ..." -> weapon7
                item_type = parts[1].lower()
                return eq_aliases.get(item_type, item_type) + parts[0][1:]
            code = parts[0].lower().replace("extra_", "")  # "EXTRA_VACATIONS" -> vacations
            return normalized_keys.get(code.replace("_", ""), code)

        def pick_price(key: str) -> float:
            price = choice((str(prices.get(key, "0")) or "0").split(",")).strip()
            if "-" in price:
                low, high = price.split("-")
                return round(uniform(float(low), float(high)), 2)
            return float(price or 0)

        driver = self.bot.browser_window
        await self.bot.get_content(f"{base_url}auctions.html")
        await sleep(uniform(2, 4))
        page = 1

        while not utils.should_break(ctx):
            # τα στοιχεία κάθε auction είναι στο κίτρινο κουμπί (data-*), το bid γίνεται με το πράσινο
            offers = [{"id": b.get_attribute("data-id"),
                       "min_bid": float(b.get_attribute("data-minimal-outbid") or 0),
                       "buyer": (b.get_attribute("data-top-bidder") or "").strip().lower(),
                       "item": b.get_attribute("data-auction-item") or ""}
                      for b in driver.find_elements(By.CSS_SELECTOR, "button.btn-yellow[data-action='BID']")]
            if not offers:
                break

            results = []
            for offer in offers:
                if utils.should_break(ctx):
                    break
                key = price_key(offer["item"])
                price = pick_price(key)
                # Don't bid if: our price is below the minimum outbid, or the top bidder is a friend / ourselves
                if not price or offer["min_bid"] > price or offer["buyer"] in all_friends:
                    continue

                # γράψε την τιμή στο κουτάκι της γραμμής και πάτα το πράσινο κουμπί (όπως με το χέρι)
                price_box = driver.find_element(By.ID, f"bidPrice{offer['id']}")
                ActionChains(driver).move_to_element(price_box).pause(uniform(0.3, 0.8)).click().perform()
                price_box.clear()
                for char in f"{price:.2f}":
                    price_box.send_keys(char)
                    await sleep(uniform(0.05, 0.2))
                await sleep(uniform(0.5, 1.5))
                bid_button = driver.find_element(
                    By.CSS_SELECTOR, f"button.bid[data-action='BID'][data-id='{offer['id']}']")
                self.human_click(bid_button)

                # η σελίδα αντικαθιστά τη γραμμή με το αποτέλεσμα
                try:
                    WebDriverWait(driver, 10).until(EC.staleness_of(bid_button))
                    new_offer = driver.find_elements(
                        By.CSS_SELECTOR, f"button.btn-yellow[data-action='BID'][data-id='{offer['id']}']")
                    top = (new_offer[0].get_attribute("data-top-bidder") or "").strip() if new_offer else ""
                    status = "✅" if top.lower() == nick.lower() else f"❌ top bidder: {top or '?'}"
                except TimeoutException:
                    status = "⚠️ no answer"
                results.append(f"{status} <{base_url}auction.html?id={offer['id']}> {key}: {price:.2f}")
                await sleep(uniform(2, 7))

            if results:
                await ctx.send(f"**{nick}**\n" + "\n".join(results))

            # επόμενη σελίδα: click στον αριθμό της (ajax paging)
            next_page = [a for a in driver.find_elements(By.CSS_SELECTOR, "a.sendAjaxPaging")
                         if a.text.strip() == str(page + 1)]
            if not next_page:
                break
            first_offer = driver.find_elements(By.CSS_SELECTOR, "button.btn-yellow[data-action='BID']")
            self.human_click(next_page[0])
            try:
                if first_offer:
                    WebDriverWait(driver, 10).until(EC.staleness_of(first_offer[0]))
            except TimeoutException:
                break
            page += 1
            await sleep(uniform(2, 4))

        if not utils.should_break(ctx):
            await ctx.send(
                f"**{nick}** Done bidding all auctions."
            )

    @command(hidden=True)
    async def set_custom_friends(self, ctx: Context, nick: IsMyNick = None, *, friends: str = "[]"):
        """
        - Write `.set_custom_friends <nick>` to see current custom friends (first use shows a draft)
        - You MUST paste the entire list and just change the names you want
        """
        server = ctx.channel.name
        file_name = f"custom_friends_{server}.json"

        try:
            friends_list = json.loads(friends.replace("'", '"'))
        except json.JSONDecodeError:
            friends_list = []

        if not friends_list:
            if file_name in os.listdir():
                with open(file_name, "r", encoding="utf-8") as file:
                    await ctx.send("Current custom friends:\n" + file.read())
            else:
                await ctx.send(
                    "Here's a draft:\n"
                    f'.set_custom_friends "{nick or "MyNick"}" ' +
                    '```json\n["friend1", "friend2", "anotherFriend"]```'
                )
                await ctx.send_help("set_custom_friends")
        else:
            friends_list = [f.lower() for f in friends_list]
            with open(file_name, "w", encoding="utf-8") as file:
                json.dump(friends_list, file)
            await ctx.send(
                f"**{nick or 'DefaultNick'}** I have created a file named `{file_name}` containing those friends.\n"
                f"You can edit it any time, or invoke the command again with the full list.\n"
                f'You can now use `.bid_all_auctions {nick or "MyNick"}` and it will avoid outbidding them.'
            )
        


    # @command()
    async def cc(self, ctx: Context, countries, max_price: float, amount: float, *, nick: IsMyNick):
        """Buying specific amount of coins, up to a pre-determined price.
        (It can help if there are many small offers, like NPC)"""
        countries = [await Country().convert(ctx, country.strip()) for country in countries.split(",")]
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        for country in countries:
            bought_amount = 0
            error = False
            for page in range(10):
                tree = await self.bot.get_content(
                    f"{base_url}monetaryMarketOffers?sellerCurrencyId=0&buyerCurrencyId={country}&page=1",
                    return_tree=True)
                amounts = tree.xpath("//*[@class='amount']//b/text()")
                ratios = tree.xpath("//*[@class='ratio']//b/text()")
                offers_ids = [int(x.attrib['data-id']) for x in tree.xpath("//*[@class='buy']/button")]
                try:
                    cc = tree.xpath("//*[@class='buy']/button")[0].attrib['data-buy-currency-name']
                except IndexError:
                    await ctx.send(f"**{nick}** country {country} - no offers found.")
                    break
                for offer_id, offer_amount, ratio in zip(offers_ids, amounts, ratios):
                    if utils.should_break(ctx):
                        return
                    try:
                        offer_amount, ratio = float(offer_amount), float(ratio)
                        if ratio > max_price:
                            await ctx.send(f"**{nick}** The price is too high ({ratio} per {cc}).")
                            error = True
                            break

                        payload = {'action': "buy", 'id': offer_id,
                                   'ammount': round(min(offer_amount, amount - bought_amount), 2),
                                   'stockCompanyId': '', 'submit': 'Buy'}
                        url = await self.bot.get_content(f"{base_url}monetaryMarketOfferBuy.html", data=payload)
                        if "MM_POST_OK_BUY" not in str(url):
                            await ctx.send(f"ERROR: <{url}>")
                            error = True
                            break
                        await ctx.send(f"**{nick}** Bought {payload['ammount']} {cc} at {ratio} each.")
                        bought_amount += payload['ammount']
                        if bought_amount >= amount:
                            error = True
                            break
                        await sleep(uniform(0, 2))
                        # sleeping for a random time between 0 and 2 seconds. feel free to change it

                    except Exception as exc:
                        error = True
                        await ctx.send(f"**{nick}** ERROR {exc}")
                        await sleep(5)
                if error:
                    break

            if bought_amount > 0:
                await ctx.send(f"**{nick}** bought total {round(bought_amount, 2)} {cc}.")
                await sleep(uniform(0, 4))

    # @command()
    async def buy(self, ctx: Context, market: Country, amount: int, quality: Optional[Quality], product: Product, *,
                  nick: IsMyNick):
        """Buy products at the given market."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if not quality:
            quality = 5
        if not product:
            return await ctx.send(f"**{nick}** ERROR: Invalid input")

        while 0 < amount and not utils.should_break(ctx):
            tree = await self.bot.get_content(
                f"{base_url}productMarket.html?resource={product}&quality={quality}&countryId={market}",
                return_tree=True)
            data = tree.xpath("//*[@class='buy']/button")
            try:
                (data or tree.xpath('//*[@class="buy"]/button'))[0]
            except IndexError:
                await ctx.send(f"**{nick}** ERROR: there are no Q{quality} {product} in the market.")
                break
            if data:  # new format
                offer_id = data[0].attrib['data-id']
                stock = int(data[0].attrib['data-quantity'])
                cost = float(data[0].attrib['data-price'])
            else:
                offer_id = tree.xpath('//*[@id="command"]/input[1]')[0].value
                stock = int(tree.xpath("//tr[2]//td[3]/text()")[0])
                cost = float([x.strip() for x in tree.xpath("//tr[2]//td[4]//text()") if x.strip()][0])
            quantity = min(stock, amount)
            payload = {'action': "buy", 'id': offer_id, 'quantity': quantity, "submit": "Buy"}
            url = await self.bot.get_content(base_url + "productMarket.html", data=payload)
            await ctx.send(f"**{nick}** Quantity: {quantity}. Price: {cost} each. <{url}>")
            if "POST_PRODUCT_BUY_OK" not in url:
                break
            amount -= quantity

    @command()
    async def donate(self, ctx: Context, donation_type, data, receiver_name: str, *, nick: IsMyNick):
        """
        Donating specific EQ ID(s) to a specific user.
        `donation_type` can be eq or gold.
        if you want to donate eq, write its ids at `data`, separated by adjacent commas.
        if you want to donate gold, write the amount at `data`.
        if you want to donate product, use this:
         .click nick https://primera.e-sim.org/donateProducts.html?id=0000  {"product": "5-WEAPON", "quantity": X}
        if you want to donate specific coin or specify reason, use this:
         .click nick https://primera.e-sim.org/donateMoney.html?id=0000     {"currencyId": 0, "sum": 0, "reason": ""}
         .click nick https://primera.e-sim.org/donateEquipment.html?id=0000 {"equipmentId": XX, "id": XXX, "reason": ""}

        You can also input receiver_id instead of receiver_name. If your nick is numerical, write it with a leading dot: ".000"
        """
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if receiver_name.startswith("."):
            receiver_id = receiver_name[1:]
        elif receiver_name.isdigit():
            receiver_id = receiver_name
        else:
            api_citizen = await self.bot.get_content(f"{base_url}apiCitizenByName.html?name={receiver_name.lower()}")
            receiver_id = api_citizen["id"]
        await self.bot.get_content(f"{base_url}profile.html?id={receiver_id}")
        if "eq" in donation_type.lower():
            results = []
            ids = [int(x.strip()) for x in data.split(",") if x.strip()]
            await self.bot.get_content(f"{base_url}donateEquipment.html?id={receiver_id}")
            for index, eq_id in enumerate(ids):
                payload = {"equipmentId": eq_id, "reason": ""}
                payload = {"payload": payload, "find_by": "css", "element": 'form[action="donateEquipment.html"]'}
                url = await self.bot.get_content(f"{base_url}donateEquipment.html?id={receiver_id}", data=payload)
                results.append(f"ID {eq_id} - <{url}>")
            await ctx.send(f"**{nick}**\n" + "\n".join(results))

        elif donation_type.lower() == "gold":
            if not data.replace('.', '', 1).isdigit():
                await ctx.send(f"**{nick}** ERROR: you must provide the sum to donate")
            else:
                payload = {"currencyId": 0, "sum": data, "reason": ""}
                payload = {"payload": payload, "find_by": "id", "element": "donateMoneyForm"}
                url = await self.bot.get_content(f"{base_url}donateMoney.html?id={receiver_id}", data=payload)
                await ctx.send(f"**{nick}** <{url}>")
        else:
            await ctx.send(f"**{nick}** ERROR: you can donate eq or gold only, not {donation_type}")

    # @command()
    async def job(self, ctx: Context, company_id: Optional[int] = 0, ticket_quality: Optional[Quality] = 5, *,
                  nick: IsMyNick):
        """Leaving current job and applying to the given company_id or to the best offer at the local market."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        if company_id != 0:
            api_citizen = await self.bot.get_content(f"{base_url}apiCitizenByName.html?name={nick.lower()}")
            tree = await self.bot.get_content(f"{base_url}company.html?id={company_id}", return_tree=True)
            region = utils.get_ids_from_path(tree, '//div[1]//div[2]//div[5]//div[1]//div//div[1]//div//div[4]//a')[0]
            if not await ctx.invoke(self.bot.get_command("fly"), region, ticket_quality, nick=nick):
                return
            job_ids = [job_id.value for job_id in tree.xpath('//tr//td[4]//form[1]/input[1]')]
            skills = [int(x) for x in tree.xpath('//td[1]/text()') if x.isdigit()]
            job_id = None
            for _job_id, skill in zip(job_ids, skills):
                if api_citizen["economySkill"] >= skill:
                    job_id = _job_id
                    break
            if job_id is None:
                return await ctx.send(
                    f"**{nick}** ERROR: There are no job offers in <{base_url}company.html?id={company_id}> for your skill.")
        else:
            tree = await self.bot.get_content(base_url + "jobMarket.html", return_tree=True)
            job_id = tree.xpath("//*[@class='job-offer-footer']//@value")[0]

        url = await self.bot.get_content(base_url + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
        if "APPLY_FOR_JOB_ALREADY_HAVE_JOB" in url:
            await self.bot.get_content(base_url + "work.html", data={'action': "leave", "submit": "Leave job"})
            url = await self.bot.get_content(base_url + "jobMarket.html", data={"id": job_id, "submit": "Apply"})
            if "APPLY_FOR_JOB_ALREADY_HAVE_JOB" in url:
                return await ctx.send(
                    f"**{nick}** ERROR: Couldn't apply for a new job. Perhaps you should wait 6 hours.")
        await ctx.send(f"**{nick}** <{url}>")
        await ctx.invoke(self.bot.get_command("work"), nick=nick)

    # @command(aliases=["split"])
    async def merge(self, ctx: Context, ids_or_quality: str, include_bound: Optional[bool] = False, *, nick: IsMyNick):
        """
        Merges a specific EQ IDs / all EQs up to specific Q (included) / elixirs.

        Examples:
        .merge 36191,34271,33877 My Nick  ->   Merges eqs id 36191, 34271 and 33877
        .merge 5 My Nick                  ->   Merges all Q1-Q5 eqs in your storage.
        .split 36191 My Nick              ->   Splits eq id 36191
        .merge mini_lucky My Nick         ->   Merges 3 mini elixirs into lucky
        .merge mini_bloody My Nick        ->   Merges 3 mili bloody mess elixirs into mini

        * You can also use blue/green/red/yellow instead of Jinxed/Finesse/bloody_mess/lucky
        * You can also use Q1-6 instead of mili/mini/standard/major/huge/exceptional

        IMPORTANT NOTE: No spaces in `ids_or_quality`! only commas (or within quotes)
        """

        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        if ctx.invoked_with.lower() == "split":
            await self.bot.get_content(f'{base_url}storage.html?storageType=EQUIPMENT')
            payload = {'action': "SPLIT", "itemId": int(ids_or_quality.strip())}
            url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
            await ctx.invoke(self.bot.get_command("eqs"), nick=nick)
        elif "," in ids_or_quality:
            await self.bot.get_content(f'{base_url}storage.html?storageType=EQUIPMENT')
            eq1, eq2, eq3 = [eq.strip() for eq in ids_or_quality.split(",")]
            payload = {'action': "MERGE", f'itemId[{eq1}]': eq1, f'itemId[{eq2}]': eq2, f'itemId[{eq3}]': eq3}
            url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")
            await ctx.invoke(self.bot.get_command("eqs"), nick=nick)

        elif ids_or_quality.isdigit():
            await ctx.send(f"**{nick}** On it! You can cancel with `.cancel merge {nick}`")
            max_q_to_merge = int(ids_or_quality.lower().replace("q", ""))  # max_q_to_merge - including
            results = []
            error = False
            for _ in range(5):
                tree = await self.bot.get_content(f'{base_url}storage.html?storageType=EQUIPMENT', return_tree=True)
                ids = tree.xpath('//*[starts-with(@id, "cell")]/a/text()')
                items = tree.xpath('//*[starts-with(@id, "cell")]/b/text()')
                soul_bounds = ["id" in x.attrib for x in tree.xpath('//*[starts-with(@id, "cell")]/p[1]')]
                eqs_dict = {}
                for eq_id, item, soul in zip(ids, items, soul_bounds):
                    quality = int(item.split()[0].replace("Q", ""))
                    if quality < max_q_to_merge + 1 and (include_bound or not soul):
                        if quality not in eqs_dict:
                            eqs_dict[quality] = []
                        eqs_dict[quality].append(int(eq_id.replace("#", "")))
                for i in range(1, max_q_to_merge + 1):
                    for z in range(len(eqs_dict.get(i, [])) // 3):
                        if utils.should_break(ctx):
                            error = True
                            break
                        eq1, eq2, eq3 = eqs_dict[i][z * 3:z * 3 + 3]
                        payload = {'action': "MERGE", f'itemId[{eq1}]': eq1, f'itemId[{eq2}]': eq2,
                                   f'itemId[{eq3}]': eq3}
                        url = await self.bot.get_content(base_url + "equipmentAction.html", data=payload)
                        results.append(f"<{url}>")
                        await sleep(uniform(0, 2))
                        if url == "http://www.google.com/":
                            # e-sim error
                            await sleep(5)

                        elif "?actionStatus=CONVERT_ITEM_OK" not in url:
                            # no money etc
                            error = True
                            break
                    if results:
                        await ctx.send(f"**{nick}**\n" + "\n".join(results)[:1950])
                        results.clear()
                    if error:
                        break
                if error:
                    break
            await ctx.send(f"**{nick}**\n" + "\n".join(results)[:1950])
            await ctx.invoke(self.bot.get_command("eqs"), nick=nick)

        else:
            elixir_type = utils.fix_elixir(ids_or_quality)
            if "LUCKY" in elixir_type:
                payload = {"luckyElixirType": elixir_type, "action": "MERGE_THREE_ELIXIRS_INTO_LUCKY_ONE",
                           "submit": "Merge"}
            else:
                payload = {"elixirType": elixir_type, "action": "MERGE_ELIXIRS_INTO_BIGGER", "submit": "Merge"}
            await self.bot.get_content(f'{base_url}storage.html?storageType=ELIXIRS')
            url = await self.bot.get_content(base_url + "elixirAction.html", data=payload)
            await ctx.send(f"**{nick}** <{url}>")

    # @command()
    async def mm(self, ctx: Context, *, nick: IsMyNick):
        """Sells all currencies in your account in the appropriate markets & edit current offers if needed."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        api = await self.bot.get_content(base_url + "apiCountries.html")
        money_tree = await self.bot.get_content(base_url + "storage.html?storageType=MONEY", return_tree=True)
        money = [x.strip() for x in money_tree.xpath("//*[@class='currencyDiv']//text()") if x.strip()]
        coins = dict(zip(money[1::2], money[0::2]))
        if "Gold" in coins:
            del coins["Gold"]
        for currency, amount in coins.items():
            if utils.should_break(ctx):
                return
            currency_id = [i["id"] for i in api if i["currencyName"] == currency][0]
            tree = await self.bot.get_content(
                f'{base_url}monetaryMarket.html?buyerCurrencyId={currency_id}&sellerCurrencyId=0', return_tree=True)
            try:
                rate = float(tree.xpath("//*[@class='buy']/button")[0].attrib['data-sell-currency'])
            except Exception:
                rate = 0.1
            # round down amount to prevent e-sim rounding error
            payload = {"offeredCurrencyId": currency_id, "buyerCurrencyId": 0, "amount": int(float(amount)),
                       "rate": round(rate - 0.0001, 4)}
            await self.bot.get_content(base_url + "monetaryMarketOfferPost.html", data=payload)
            await ctx.send(f"**{nick}** posted {amount} {currency} for {payload['rate']}")

        money_tree = await self.bot.get_content(base_url + "storage.html?storageType=MONEY", return_tree=True)
        ids = money_tree.xpath('//*[@id="command"]//input[1]')
        currencies = [x.strip() for x in money_tree.xpath(f"//*[@class='amount']//text()") if x.strip()][1::2]
        for i in range(len(currencies)):
            if utils.should_break(ctx):
                return
            currency_id = [x["id"] for x in api if x["currencyName"] == currencies[i]][0]
            tree = await self.bot.get_content(
                f'{base_url}monetaryMarketOffers?buyerCurrencyId={currency_id}&sellerCurrencyId=0&page=1',
                return_tree=True)
            seller = tree.xpath("//*[@class='seller']/a/text()")[0].strip()
            rate = float(tree.xpath("//*[@class='buy']/button")[0].attrib['data-sell-currency'])
            if seller.lower() != nick.lower():
                payload = {"id": ids[i].value, "rate": round(rate - 0.0001, 4), "submit": "Edit"}
                await self.bot.get_content(base_url + "monetaryMarket.html?action=change", data=payload)
                await ctx.send(f"**{nick}** edited {currencies[i]} for {payload['rate']}")

    # @command()
    async def sell(self, ctx: Context, quantity: int, quality: Optional[Quality], product: Product, price: float,
                   country: Country, *, nick: IsMyNick):
        """Sell products at market."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        payload = {'action': 'POST_OFFER', 'product': f'{quality or 5}-{product}',
                   'countryId': country, 'quantity': quantity, 'price': price}
        await self.bot.get_content(f"{base_url}storage.html?storageType=PRODUCT")
        url = await self.bot.get_content(f"{base_url}storage.html?storageType=PRODUCT", data=payload)
        await ctx.send(f"**{nick}** <{url}>")

    # @command()
    async def update_job_offer(self, ctx: Context, company_id: int, max_salary: float, country: Country, skill: int,
                               region_id: Optional[int] = 0, *, nick: IsMyNick):
        """Checks every ~10 minutes if there's an offer above yours.
        If so, updates your offer accordingly (up to `max_salary`)"""
        ctx.command = f"update_job_offer-{ctx.message.id}"
        await ctx.send(f"**{nick}** If you want to stop it, type `.cancel update_job_offer-{ctx.message.id} {nick}`")
        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        company_link = f"{base_url}company.html?id={company_id}"
        tree = await self.bot.get_content(company_link, return_tree=True)
        company_name = tree.xpath('//*[@id="companyPreview"]/a/text()')[0]
        job_ids = [job_id.value for job_id in tree.xpath('//tr//td[4]//form[1]/input[1]')]
        skills = [int(x) for x in tree.xpath('//td[1]/text()') if x.isdigit()]
        job_id = None
        for _job_id, offer_skill in zip(job_ids, skills):
            if offer_skill == skill:
                job_id = _job_id
                break
        while not utils.should_break(ctx):
            tree = await self.bot.get_content(
                f"{base_url}getJobOffers?countryId={country}&minimalSkill={skill}&regionId={region_id}",
                return_tree=True)
            salary = float(tree.xpath('//*[@class="currency"]/b/text()')[0])
            company = tree.xpath('//*[@class="job-offer-content"]/div/a/text()')[0].strip().lower()
            # companies, employers = company[::2], company[1::2]
            if company != company_name.lower():
                if salary > max_salary:
                    await ctx.send(
                        f"**{nick}** Salary is too high for {company_link}, skill {skill} ({salary} > {max_salary})")
                    await sleep(uniform(500, 700))  # continue after some additional pause.
                else:
                    await self.bot.get_content(company_link)
                    payload = {'offerId': job_id, "action": "EDIT_JOB_OFFER", "salary": round(salary + 0.01, 2)}
                    url = await self.bot.get_content(company_link, data=payload)
                    await ctx.send(f"**{nick}** salary {payload['salary']}, skill {skill} : {url}")
            await sleep(uniform(500, 700))

    # @command()
    async def auction(self, ctx: Context, ids, price: float, hours: int, *, nick: IsMyNick):
        """Sell specific EQ ID(s) / reshuffle / upgrade / PD_10h / camouflage_II at auctions.
        `ids` MUST be separated by a comma, and without spaces (or with spaces, but within quotes)
        set `ids=ALL` if you want to sell all your eqs."""
        base_url = f"https://{ctx.channel.name}.e-sim.org/"

        results = []
        if ids.lower() == "all":
            tree = await self.bot.get_content(base_url + 'storage.html?storageType=EQUIPMENT', return_tree=True)
            ids = tree.xpath('//*[starts-with(@id, "cell")]/a/text()')
        else:
            ids = [x.strip() for x in ids.split(",") if x.strip()]
        for eq_id in ids:
            if utils.should_break(ctx):
                return
            eq_id = eq_id.replace(base_url + "showEquipment.html?id=", "").replace("#", "").strip().lower()
            if eq_id == "pd_1h":
                item = "SPECIAL_ITEM 7"
            elif eq_id == "pd_10h":
                item = "SPECIAL_ITEM 8"
            elif eq_id == "pd_25h":
                item = "SPECIAL_ITEM 9"
            elif eq_id == "camouflage_i":
                item = "SPECIAL_ITEM 16"
            elif eq_id == "camouflage_ii":
                item = "SPECIAL_ITEM 17"
            elif eq_id == "camouflage_iii":
                item = "SPECIAL_ITEM 18"
            elif eq_id == "upgrade":
                item = "SPECIAL_ITEM 19"
            elif eq_id == "reshuffle":
                item = "SPECIAL_ITEM 20"
            else:
                item = f"EQUIPMENT {eq_id}"
            payload = {'action': "CREATE_AUCTION", 'price': price, "id": item, "length": hours,
                       "submit": "Create auction"}
            await self.bot.get_content(f"{base_url}myAuctions.html")
            url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            if "CREATE_AUCTION_ITEM_EQUIPED" in url:
                ctx.invoked_with = "unwear"
                await ctx.invoke(self.bot.get_command("wear"), ids, nick=nick)
                url = await self.bot.get_content(base_url + "auctionAction.html", data=payload)
            results.append(f"ID {eq_id} - <{url}>")
        await ctx.send(f"**{nick}**\n" + "\n".join(results))

    def page_error(self) -> str:
        """Το κόκκινο μήνυμα λάθους του game (π.χ. "There is no money in the company..."), αν υπάρχει."""
        errors = [e for e in self.bot.browser_window.find_elements(By.CSS_SELECTOR, "#newError, .newError")
                  if e.get_attribute("textContent").strip()]
        return " ".join(errors[0].get_attribute("textContent").split()) if errors else ""

    def human_click(self, element):
        ActionChains(self.bot.browser_window).move_to_element(element).pause(uniform(0.3, 0.8)).click().perform()

    def done_notice(self) -> bool:
        """Μετά από work/train το game δείχνει το .workNotify ("You will be able to work again in:" / "You can train again in:")."""
        return any(e.is_displayed() for e in self.bot.browser_window.find_elements(By.CSS_SELECTOR, ".workNotify"))

    async def wait_for_result(self) -> str:
        """Περιμένει μέχρι 15 sec: "done" (.workNotify) ή το μήνυμα λάθους (.newError)."""
        for _ in range(30):
            await sleep(0.5)
            if self.page_error():
                return self.page_error()
            if self.done_notice():
                return "done"
        return "no answer from the game"

    async def _train(self, base_url: str) -> str:
        """train.html -> Train. Επιστρέφει το μήνυμα για το Discord."""
        driver = self.bot.browser_window
        await self.bot.get_content(base_url + "train.html")
        await sleep(uniform(1.5, 3.5))
        buttons = [b for b in driver.find_elements(By.ID, "trainButton") if b.is_displayed()]
        if not buttons:
            return "Already trained" if self.done_notice() else "ERROR: Couldn't find the Train button"
        self.human_click(buttons[0])
        result = await self.wait_for_result()
        return "Trained successfully" if result == "done" else f"ERROR: Couldn't train: {result}"

    async def _work(self, base_url: str, ticket_quality: int) -> str:
        """work.html -> (Travel αν χρειάζεται) -> Work. Επιστρέφει το μήνυμα για το Discord."""
        driver = self.bot.browser_window
        await self.bot.get_content(base_url + "work.html")
        await sleep(uniform(1.5, 3.5))

        # "You cannot work from your current location" -> φόρμα travel.html με ticket
        travel = [b for b in driver.find_elements(By.CSS_SELECTOR, "form[action='travel.html'] button.travel")
                  if b.is_displayed()]
        if travel:
            select = Select(travel[0].find_element(By.XPATH, "./ancestor::form//select[@name='ticketQuality']"))
            qualities = [int(o.get_attribute("value")) for o in select.options]
            if ticket_quality not in qualities:
                return f"ERROR: Couldn't travel to work: no Q{ticket_quality} tickets (you have Q{qualities})"
            select.select_by_value(str(ticket_quality))
            await sleep(uniform(0.8, 2))
            self.human_click(travel[0])
            await sleep(uniform(3, 5))
            if self.page_error():
                return f"ERROR: Couldn't travel to work: {self.page_error()}"

        buttons = [b for b in driver.find_elements(By.ID, "workButton") if b.is_displayed()]
        if not buttons:
            return "Already worked" if self.done_notice() else "ERROR: Couldn't find the Work button"
        await sleep(uniform(1, 2.5))
        self.human_click(buttons[0])
        # λάθος (π.χ. no money / no resources) -> σταματάει εδώ, χωρίς νέα προσπάθεια
        result = await self.wait_for_result()
        return "Worked successfully" if result == "done" else f"ERROR: Couldn't work: {result}"

    @command()
    async def daily(self, ctx: Context, ticket_quality: Optional[int] = 5,
                    motivate_item: Optional[MotivateType] = None, *, nick: IsMyNick):
        """Η καθημερινή ρουτίνα ενός λογαριασμού: train + work, μετά motivate (5 citizens).
        ticket_quality: ticket για να πάει στη δουλειά αν χρειάζεται (default 5).
        motivate_item: food / gift / tickets / weapons / any ή π.χ. food,gift (default: food, gift, tickets, weapons).
        Παράδειγμα: .daily 5 food Radical  ή απλά  .daily Radical
        Τρέχει μόνο στο μηχάνημα του nick (κάθε μηχάνημα κάνει τον δικό του λογαριασμό)."""
        await ctx.send(f"**{nick}** Starting daily routine: train + work, then motivate. "
                       f"Cancel with `.cancel daily {nick}`")
        await ctx.invoke(self.bot.get_command("work"), ticket_quality, nick=nick)
        if utils.should_break(ctx):
            return
        await sleep(uniform(20, 60))  # ανθρώπινη παύση ανάμεσα στις δουλειές
        await ctx.invoke(self.bot.get_command("motivate"), motivate_item, nick=nick)
        await ctx.send(f"**{nick}** Daily routine done.")

    @command(aliases=["w", "work+"])
    async def work(self, ctx: Context, ticket_quality: Optional[int] = 5, *, nick: IsMyNick):
        """Train + work (με τυχαία σειρά).
        ticket_quality: με ποιο ticket θα πάει στο region της εταιρείας αν χρειάζεται (1-5, default 5).
        Παράδειγμα: .work 1 Kostas
        `work+` -> for premium users (https://primera.e-sim.org/taskQueue.html)"""

        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        if ctx.invoked_with.lower() == "work+":
            payload1 = {'task': "WORK", "action": "put", "submit": "Add plan"}
            payload2 = {'task': "TRAIN", "action": "put", "submit": "Add plan"}
            await self.bot.get_content(base_url + "taskQueue.html", data=payload1)
            await sleep(uniform(1, 2))
            await self.bot.get_content(base_url + "taskQueue.html", data=payload2)

        async def work_step():
            try:
                result = await self._work(base_url, ticket_quality)
            except Exception as exc:
                result = f"ERROR: Couldn't work. Error: {str(exc).strip().splitlines()[0]}"
            if result == "Worked successfully":
                data = await utils.find_one(server, "info", nick)
                data["Worked at"] = datetime.now().astimezone(timezone('Europe/Berlin')).strftime("%d/%m  %H:%M")
                await utils.replace_one(server, "info", nick, data)
            await ctx.send(f"**{nick}** {result}")

        async def train_step():
            try:
                result = await self._train(base_url)
            except Exception as exc:
                result = f"ERROR: Couldn't train. Error: {str(exc).strip().splitlines()[0]}"
            await ctx.send(f"**{nick}** {result}")

        steps = [train_step, work_step]
        shuffle(steps)
        await steps[0]()
        await sleep(uniform(3, 15))
        await steps[1]()

    @command()
    async def auto_fly(self, ctx: Context, ticket_quality: int, country: Optional[Country] = 26,
                       total_days: Optional[int] = 1,
                       avg_delay: Optional[float] = 5.0, *, nick: IsMyNick):
        """Fly at random times throughout every day (for drops)
        Currently, max drops per 24h = 6. 80% of them are Q1 shoes/pants, 16 Q2 and 4% Q3.
        There's 2% chance to get a drop when you use Q5 ticket, and 3% if you use Q1."""

        base_url = f"https://{ctx.channel.name}.e-sim.org/"
        await ctx.send(f"**{nick}** If you want to cancel it, type `.cancel auto_fly {nick}`")
        regions = [row['id'] for row in await self.bot.get_content(base_url + "apiRegions.html") if
                   row['homeCountry'] == country]
        max_flights_per_day = 300
        flights_per_restore = (10 // (5 - ticket_quality)) if ticket_quality != 5 else max_flights_per_day
        for day in range(total_days):
            found = 0
            last_region = 0
            flights = 0
            output = f"**{nick}** "
            for i in range(max_flights_per_day // flights_per_restore):
                for j in range(flights_per_restore):
                    region_id = last_region
                    while region_id == last_region:
                        region_id = choice(regions)
                    last_region = region_id
                    payload = {'ticketQuality': ticket_quality}
                    payload = {"payload": payload, "find_by": "css",
                               "element": 'form[method="post"][action="travel.html"]'}
                    tree = await self.bot.get_content(f"{base_url}region.html?id={region_id}", data=payload,
                                                      return_tree=True)
                    flights += 1
                    if tree.xpath("//*[@class='travelEquipmentDrop']"):
                        output += f"found drop after {(i + 1) * (j + 1)} flights\n"
                        found += 1
                    await sleep(uniform(min(0.0, avg_delay - 2.0), avg_delay + 2))
                    if found == 6 or utils.should_break(ctx):
                        break
                if found == 6 or utils.should_break(ctx):
                    break
                await utils.random_sleep()

            await ctx.send(output + f"Found total {found} drops for today. Total flights: {flights}")
            if utils.should_break(ctx):
                break
            await sleep(uniform(24, 30) * 60 * 60)

    @command()
    async def auto_work(self, ctx: Context, work_sessions: Optional[int] = 1, chance_to_skip_work: Optional[int] = 3, *,
                        nick: IsMyNick):
        """Works at random times throughout every day"""
        data = {"work_sessions": work_sessions, "chance_to_skip_work": chance_to_skip_work}
        await utils.save_command(ctx, "auto", "work", data)
        await ctx.send(
            f"**{nick}** I will work from now on {work_sessions} times every day, with {chance_to_skip_work}% chance to skip a work.\n"
            f"If you wish to stop it, type `.cancel auto_work {nick}`")

        tz = timezone('Europe/Berlin')
        while not utils.should_break(ctx):  # for every day:
            sec_between_works = (24 * 60 * 60) // work_sessions
            now = datetime.now(tz)
            midnight = tz.localize(datetime.combine(now + timedelta(days=1), time(0, 0, 0, 0)))

            for i in range(work_sessions):
                sec_til_midnight = (midnight - now).seconds
                work_session_start = sec_between_works if i else 0
                work_session_end = sec_til_midnight % sec_between_works + (sec_between_works if i else 0)
                if work_session_start < min(work_session_end, sec_til_midnight - 20):
                    await sleep(uniform(work_session_start, min(work_session_end, sec_til_midnight - 20)))
                now = datetime.now(tz)
                if utils.should_break(ctx):
                    break
                if randint(1, 100) > chance_to_skip_work:
                    await ctx.invoke(self.bot.get_command("work"), nick=nick)
                if (midnight - now).seconds < sec_between_works:
                    break

            # Updated the data once a day (allow the user to change chance_to_skip_work or work_sessions)
            data = (await utils.find_one("auto", "work", os.environ['nick']))[ctx.channel.name]
            if isinstance(data, list):
                data = data[0]
            chance_to_skip_work = data["chance_to_skip_work"]
            work_sessions = data["work_sessions"]

            # sleep till midnight
            await sleep((midnight - now).seconds + 20)
        await utils.remove_command(ctx, "auto", "work")

    # @command()
    async def send_contracts(self, ctx: Context, contract_id: Id, contract_name, *, nick: IsMyNick):
        """
        Sending specific contract to all your friends,
        unless you have already sent them that contract, they have rejected your previous one, or they are staff members"""
        server = ctx.channel.name
        base_url = f"https://{server}.e-sim.org/"
        blacklist = set()
        await get_staff_list(self.bot, base_url, blacklist)
        await get_received_contracts(self.bot, base_url, blacklist, contract_name)
        await get_rejected_contracts(self.bot, base_url, blacklist)
        async for friend in get_friends_list(self.bot, nick, server):
            if utils.should_break(ctx):
                break
            if friend not in blacklist:
                payload = {'action': "PROPOSE", 'citizenProposedTo': friend, 'submit': 'Propose'}
                for _ in range(10):
                    try:
                        await self.bot.get_content(f"{base_url}contract.html?id={contract_id}")
                        url = await self.bot.get_content(f"{base_url}contract.html?id={contract_id}", data=payload)
                        await ctx.send(f"**{friend}:** <{url}>")
                        break  # sent
                    except Exception as error:
                        await ctx.send(f"**{nick}** {error} while sending to {friend}")
        await ctx.send(f"**{nick}** done.")


async def get_rejected_contracts(bot, base_url: str, blacklist: set, alerts_filter: str = "CONTRACTS",
                                 text: str = "has rejected your") -> None:
    """remove rejected contracts"""
    tree = await bot.get_content(base_url + 'notifications.html?filter=' + alerts_filter, return_tree=True)
    last_page = utils.get_ids_from_path(tree, "//ul[@id='pagination-digg']//li[last()-1]/") or ['1']
    last_page = int(last_page[0])
    for page in range(1, int(last_page) + 1):
        if page != 1:
            tree = await bot.get_content(f'{base_url}notifications.html?filter={alerts_filter}&page={page}',
                                         return_tree=True)
        for tr in range(2, 22):
            if text in " ".join(tree.xpath(f"//tr[{tr}]//td[2]/text()")):
                blacklist.add(tree.xpath(f"//tr[{tr}]//td[2]//a[1]/text()")[0].strip())


async def get_friends_list(bot, nick: str, server: str, skip_banned_and_inactive: bool = True) -> iter:
    base_url = f"https://{server}.e-sim.org/"
    api_citizen = await bot.get_content(f'{base_url}apiCitizenByName.html?name={nick.lower()}')

    for page in range(1, 100):
        tree = await bot.get_content(f'{base_url}profileFriendsList.html?id={api_citizen["id"]}&page={page}',
                                     return_tree=True)
        for div in range(1, 13):
            friend = tree.xpath(f'//div//div[1]//div[{div}]/a/text()')
            if skip_banned_and_inactive:
                status = (tree.xpath(f'//div//div[1]//div[{div}]/a/@style') or [""])[0]
                if "color: #f00" in status or "color: #888" in status:  # Banned or inactive
                    continue
            if not friend:
                return
            yield friend[0].strip()


async def get_staff_list(bot, base_url: str, blacklist: set) -> None:
    """Get staff list"""
    tree = await bot.get_content(f"{base_url}staff.html", return_tree=True)
    nicks = tree.xpath('//*[@id="esim-layout"]//a/text()')
    for nick in nicks:
        blacklist.add(nick.strip())


async def get_received_contracts(bot, base_url: str, blacklist: set, contract_name: str) -> None:
    tree = await bot.get_content(f'{base_url}contracts.html', return_tree=True)
    li = 0
    while True:
        try:
            li += 1
            line = tree.xpath(f'//*[@id="esim-layout"]//div[2]//ul//li[{li}]/a/text()')
            if contract_name.lower() in line[0].strip().lower() and "offered to" in \
                    tree.xpath(f'//*[@id="esim-layout"]//div[2]//ul//li[{li}]/text()')[1]:
                blacklist.add(line[1].strip())
        except Exception:
            break


def setup(bot):
    """setup"""
    bot.add_cog(Eco(bot))
