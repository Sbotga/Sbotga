import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from discord.app_commands import locale_str
from COGS.discord_translations import translations

from main import DiscordBot

import time

from DATA.helpers import discord_autocompletes as autocompletes
from DATA.helpers import tools
from DATA.helpers import embeds
from DATA.helpers import unblock

from DATA.game_api import methods

from DATA.helpers import views

from DATA.game_api import proxy_service  # start the proxy service.

from DATA.helpers import views


class UserCog(commands.Cog):
    def __init__(self, bot: DiscordBot):
        self.bot = bot

        if not hasattr(self.bot, "proxy_running"):
            self.bot.proxy_running = False
        if not self.bot.proxy_running:
            self.bot.proxy_running = proxy_service.run_proxy()

    class LinkCheckView(views.SbotgaView):
        def __init__(
            self,
            bot: DiscordBot,
            timeout: int,
            link_code: str,
            user_id: int,
            region: str,
        ):
            super().__init__(timeout=timeout)
            self.link_code = link_code
            self.user_id = user_id
            self.region = region

            self.bot = bot

        @discord.ui.button(
            label="Link Account",
            style=discord.ButtonStyle.success,
        )
        async def link(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            if interaction.user.id != interaction.message.interaction_metadata.user.id:
                embed = embeds.error_embed(
                    await interaction.translate("errors.cannot_click")
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.defer()
            self.link.disabled = True
            user_id = self.user_id
            try:
                api = methods.Tools.get_api(self.region)
                data = api.get_profile(int(user_id), forced=True)
                last_updated = api.profile_cache[int(user_id)]["last_updated"]
            except Exception as e:
                # self.bot.traceback(e)
                return await interaction.followup.edit_message(
                    self.message.id,
                    embed=embeds.error_embed(
                        f"Couldn't get your profile; something went wrong and this is a bug."
                    ),
                    view=self,
                )
            if data["userProfile"].get("word") == self.link_code:
                await self.bot.user_data.discord.update_pjsk_id(
                    interaction.user.id, int(self.user_id), self.region
                )
                embed = embeds.success_embed(
                    title="Link Success",
                    description=(
                        f"Successfully linked to your PJSK {self.region.upper()} account!\n\n**Name:** {data['user']['name']}\n"
                        f"**User ID:** `{data['user']['userId']}`\n"
                        f"**Joined:** <t:{(int(format(data['user']['userId'], '064b')[:42], 2) + 1600218000000) // 1000}:R>\n"
                        f"**Rank:** **`🎵 {data['user']['rank']}`**\n\n"
                        f"**Bio**\n```{data['userProfile'].get('word') or 'No Bio'}```\n"
                    ),
                )
            else:
                embed = embeds.error_embed(
                    title="Link Failed",
                    description=f"**{data['user']['name']}**'s current bio is not `{self.link_code}`. Please try again.\n\n**Current Bio**\n```\n{data['userProfile'].get('word') or 'No Bio'}\n```",
                )
            return await interaction.followup.edit_message(
                self.message.id, embed=embed, view=self
            )

    class UserIDModal(discord.ui.Modal):
        def __init__(self, region: str, bot: DiscordBot):
            self.pjsk_id = discord.ui.TextInput(
                label="PJSK User ID",
                placeholder=f"Input your PJSK user ID for {region.upper()}",
                required=True,
            )
            super().__init__(title="PJSK User ID")
            self.add_item(self.pjsk_id)

            self.region = region
            self.bot = bot

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.send_message(
                embed=embeds.embed("Please wait...")
            )
            msg = await interaction.original_response()
            user_id = self.pjsk_id.value
            if not user_id.isdigit():
                embed = embeds.error_embed(
                    "Invalid user ID.",
                )
                return await msg.edit(embed=embed)
            discord_id = (
                await self.bot.user_data.discord.get_discord_user_id_from_pjsk_id(
                    user_id, self.region
                )
            )
            if discord_id:
                embed = embeds.error_embed(
                    "This PJSK account has already been linked.\n-# Lost your Discord account and need to unlink? Contact support.",
                )
                return await msg.edit(embed=embed)
            try:
                # min and max         10000000                    402827003243343876 is my id
                assert int(user_id) > 10000000 and int(user_id) < 10000000000000000000
                api = methods.Tools.get_api(self.region)
                data = api.get_profile(int(user_id))
                last_updated = api.profile_cache[int(user_id)]["last_updated"]
            except Exception as e:
                if "404" in str(e):
                    return await msg.edit(
                        embed=embeds.error_embed(
                            f"Couldn't get your profile; is this account in the {self.region.upper()} server (if not, change the region option)? Is the user id valid?"
                        )
                    )
                raise e
                is_self = True
            joined = (
                f"**Joined:** <t:{(int(format(data['user']['userId'], '064b')[:42], 2) + 1600218000000) // 1000}:R>\n"
                if self.region in ["en", "jp"]
                else ""
            )
            embed = embeds.embed(
                title="Linking to " + data["user"]["name"],
                description=(
                    f"**User ID:** `{data['user']['userId']}`\n"
                    f"{joined}"
                    f"**Rank:** **`🎵 {data['user']['rank']}`**\n\n"
                    f"**Bio**\n```{data['userProfile'].get('word') or 'No Bio'}```\n### ℹ️ Press the back arrow after changing your bio to save it. You may need to wait a few seconds if you have slow wifi."
                ),
                color=discord.Color.dark_magenta(),
            )
            link_code = "sbotga_" + tools.generate_secure_string(7)
            embed.add_field(
                name="To Link",
                value=f"Please set your **PJSK** bio (`Comment`) to the following code and click the button within 5 minutes.\n```\n{link_code}\n```",
                inline=False,
            )
            embed.set_footer(
                text=f"{self.region.upper()} - Last updated {round(time.time()-last_updated)}s ago"
            )
            view = UserCog.LinkCheckView(
                bot=self.bot,
                timeout=300,
                link_code=link_code,
                user_id=user_id,
                region=self.region,
            )
            await msg.edit(embed=embed, view=view)
            view.message = msg

    class TransferCheckView(views.SbotgaView):
        def __init__(
            self,
            bot: DiscordBot,
            timeout: int,
            transfer_id: str,
            transfer_password: str,
            region: str,
        ):
            super().__init__(timeout=timeout)
            self.transfer_id = transfer_id
            self.transfer_password = transfer_password
            self.region = region

            self.bot = bot

        @discord.ui.button(
            label="Cancel",
            style=discord.ButtonStyle.gray,
        )
        async def cancel(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            for child in self.children:
                if isinstance(child, discord.ui.Button) or isinstance(
                    child, discord.ui.Select
                ):
                    child.disabled = True
            embed = embeds.embed(
                title="Cancelled",
                description="Account transfer cancelled.\n-# To stay safe, please reset your account transfer settings.",
                color=discord.Color.red(),
            )
            await interaction.response.edit_message(embed=embed, view=self)

        @discord.ui.button(
            label="Transfer Account",
            style=discord.ButtonStyle.success,
        )
        async def transfer(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            self.transfer.disabled = True
            self.cancel.disabled = True
            embed = embeds.embed(
                title="Transferring...",
                description=f"We are transferring your account.\n\nIf this message does not update within a minute, assume something went wrong and contact support at </help:1326325488939040808>.\n\nYou can try your old transfer settings in that case.\n**Transfer ID:** `{self.transfer_id}`\n**Transfer Password:** `{self.transfer_password}`",
                color=discord.Color.dark_gray(),
            )
            await interaction.response.edit_message(view=self, embed=embed)
            try:
                api = methods.Tools.get_api(self.region)
                data, new, cred = await api.get_user_data(
                    self.transfer_id, self.transfer_password, inherit=True
                )
            except Exception as e:
                self.bot.traceback(e)
                return await interaction.edit_original_response(
                    embed=embeds.error_embed(
                        f"SOMETHING WENT WRONG!\nTry using your original transfer credentials if you were already locked out of your account.\n\n**Transfer ID:** `{self.transfer_id}`\n**Transfer Password:** `{self.transfer_password}`\n\nIf this didn't work, CONTACT SUPPORT IMMEDIATELY (see: </help:1326325488939040808>).\n-# We do not take any responsibility for lost data. If we are unable to recover your account, contacting SEGA support may work."
                    ),
                    view=self,
                )
            embed = embeds.success_embed(
                title="Transfer Success",
                description=(
                    f"Your transfer was successful. Please use the new account transfer credentials to get your account back.\n-# Title Screen > Menu > Account Transfer\n\n"
                    f"**Transfer ID:** `{new[0]}`\n**Transfer Password:** `{new[1]}`\n\nAlternatively, you can use your **Game Center** or **Play Store** link to log in.\n\n**After transferring, reset your transfer settings by making a new transfer.**"
                ),
            )
            embed.set_footer(text=f"{self.region.upper()} - Data Updated")
            return await interaction.edit_original_response(embed=embed, view=self)

    class TransferIDModal(discord.ui.Modal):
        def __init__(self, region: str, bot: DiscordBot, pjsk_id: int):
            self.transfer_id = discord.ui.TextInput(
                label="Transfer ID",
                placeholder=f"Menu > Account Transfer > To Another OS",
                required=True,
                min_length=16,
                max_length=16,
            )
            self.transfer_password = discord.ui.TextInput(
                label="Transfer Password",
                placeholder=f"Menu > Account Transfer > To Another OS",
                required=True,
                min_length=8,
                max_length=16,
            )
            super().__init__(title="PJSK Transfer Settings")
            self.add_item(self.transfer_id)
            self.add_item(self.transfer_password)

            self.region = region
            self.bot = bot
            self.pjsk_id = pjsk_id

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.send_message(
                embed=embeds.embed("Attempting to DM you."), ephemeral=True
            )
            try:
                msg = await interaction.user.send(
                    embed=embeds.embed("Checking transfer...")
                )
                await interaction.edit_original_response(
                    embed=embeds.success_embed("DM success! Continuing in DMs.")
                )
            except:
                await interaction.edit_original_response(
                    embed=embeds.error_embed(
                        "I couldn't DM you. Please allow DMs to continue."
                    )
                )
                return
            try:
                api = methods.Tools.get_api(self.region)
                data, _, _ = await api.get_user_data(
                    self.transfer_id.value.strip(),
                    self.transfer_password.value,
                    inherit=False,
                )
            except Exception as e:
                if "404" not in str(e):
                    self.bot.traceback(e)
                return await msg.edit(
                    embed=embeds.error_embed(
                        f"Invalid transfer settings. Please try again."
                    )
                )
            if data["afterUserGamedata"]["userId"] != self.pjsk_id:
                return await msg.edit(
                    embed=embeds.error_embed(
                        "Hey, this isn't your account! We can only get the account data for the PJSK account you have linked to your Discord."
                    )
                )
            if any(
                [value for value in data["userEventDeviceTransferRestrict"].values()]
            ):
                embed = embeds.error_embed(
                    "You have a transfer restriction due to being t300 in the event.",
                )
                return await msg.edit(embed=embed, view=None)
            joined = (
                f"**Joined:** <t:{(int(format(data['afterUserGamedata']['userId'], '064b')[:42], 2) + 1600218000000) // 1000}:R>\n"
                if self.region in ["en", "jp"]
                else ""
            )
            embed = embeds.embed(
                title="Confirm Transfer",
                description=(
                    f"After transferring, you will need to transfer back on your original account.\n-# To stay safe, please ensure you have a **Game Center** or **Play Store** link on your account.\n\n**After transferring, reset your transfer settings by making a new transfer.**\n\n"
                    f'**User ID:** `{data["afterUserGamedata"]["userId"]}`\n'
                    f"{joined}"
                    f'**Rank:** **`🎵 {data["afterUserGamedata"]["rank"]}`**\n'
                    f'**Name:** `{data["afterUserGamedata"]["name"]}`'
                ),
                color=discord.Color.dark_magenta(),
            )
            embed.set_footer(text=f"{self.region.upper()} - Updating Data")
            view = UserCog.TransferCheckView(
                bot=self.bot,
                timeout=60,
                transfer_id=self.transfer_id.value.strip(),
                transfer_password=self.transfer_password.value,
                region=self.region,
            )
            await msg.edit(embed=embed, view=view)
            view.message = msg

    user = app_commands.Group(
        name="user",
        description="User account settings.",
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    )

    user_pjsk = app_commands.Group(
        name="pjsk", description="User PJSK related settings.", parent=user
    )

    @user_pjsk.command(
        auto_locale_strings=False,
        name="update_data",
        description="Update saved PJSK user data.",
    )
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    @app_commands.describe(region=locale_str("general.region"))
    async def user_pjsk_update_data(
        self, interaction: discord.Interaction, region: str = "default"
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        )
                    )
                ),
                ephemeral=True,
            )
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        if not pjsk_id:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    f"You are not linked to a PJSK {region.upper()} account."
                ),
                ephemeral=True,
            )

        async def transfer(interaction: discord.Interaction):
            api = methods.Tools.get_api(region)
            data = api.attempt_get_user_data(pjsk_id)
            if data:
                sub_level = await self.bot.subscribed(interaction.user)
                current_time = time.time()

                if sub_level < 2:
                    cooldown_end = (data["now"] / 1000) + 14400  # 4 hours
                    if cooldown_end > current_time:
                        embed = embeds.error_embed(
                            (
                                f"You recently transferred your account already. Try again <t:{int(cooldown_end)}:R>.\n"
                                f"-# 4 hours cooldown. Donate to shorten the cooldown to 30 minutes. See </donate:1326321351417528442>"
                            ),
                        )
                        return await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )
                else:
                    cooldown_end = (data["now"] / 1000) + 1800  # 30 minutes
                    if cooldown_end > current_time:
                        embed = embeds.error_embed(
                            f"You recently transferred your account already. Try again <t:{int(cooldown_end)}:R>."
                        )
                        return await interaction.response.send_message(
                            embed=embed, ephemeral=True
                        )
            view = views.SbotgaView(timeout=60)
            button = discord.ui.Button(
                label="Begin Transfer",
                style=discord.ButtonStyle.primary,
                custom_id="transferring",
            )
            button.callback = lambda interaction: interaction.response.send_modal(
                self.TransferIDModal(region=region, bot=self.bot, pjsk_id=pjsk_id)
            )

            view.add_item(button)

            embed = embeds.embed(
                title="Account Transfer",
                description="You are about to transfer your account to Sbotga temporarily. To begin, click the button below. This process will happen in your DMs.\n**⚠️ Do not share your transfer settings with anyone else.**\n### Transferring Back\nAfter transferring, you must transfer back with your **Game Center/Play Store** link, or with the provided transfer settings.\n### Why?\nThis will allow us to access and download your PJSK data (such as AP/FCs) to use in some of our commands. Transferring your account is not required to use this bot.\n## More Info\n**We do NOT store your transfer ID or password at ANY time.**\n**Privacy Policy:** https://github.com/Sbotga/info/blob/main/legal/PRIVACY.md\n**More Information:** https://github.com/Sbotga/info/blob/main/en/LINKING.md",
                color=discord.Color.from_rgb(247, 102, 30),
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            view.message = await interaction.original_response()

        async def proxy(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True, ephemeral=True)
            api = methods.Tools.get_api(region)
            data = api.attempt_get_user_data(pjsk_id)
            if data:
                current_time = time.time()
                cooldown_end = (data["now"] / 1000) + 300  # 5 minutes
                if cooldown_end > current_time:
                    embed = embeds.error_embed(
                        f"You recently transferred your account already. Try again <t:{int(cooldown_end)}:R>."
                    )
                    return await interaction.followup.send(embed=embed)

            embed = embeds.embed(
                title="Proxy Data Transfer",
                description='### Instructions (iOS/iPadOS 13+ only)\n1. Connect to a wifi network. Turn off any VPNs.\n2. In settings, click on the `🛈` to the right of the wifi name.\n3. Scroll down and click "Configure Proxy"\n4. Click "Manual", and enter the following.\n```\nServer: proxy.sbuga.com\nPort:   8999```\n5. Hit "Save" at the top right. **This will turn off your wifi. To undo this, simply click "Off" in "Configure Proxy".**\n6. **SKIP TO STEP 9 IF YOU\'VE DONE THIS BEFORE FOR Sbotga.** On Safari (only Safari), go to the website `mitm.it`. Under `iOS`, click "Get mitmproxy-ca-cert.pem". Click "Allow".\n7. Go to **Settings > General > VPN & Device Management > mitmproxy**, and click "Install" in the top right corner. Enter your passcode, and click "Install" again.\n8. Go to **Settings > General > About > Certificate Trust Settings (at the bottom)**, and turn on "mitmproxy".\n9. Launch PJSK as normal.\n10. Disconnect from the proxy (see step 5).\n### Why?\nThis will allow us to access and download your PJSK data (such as AP/FCs) to use in some of our commands. Doing this is not required to use this bot.\n## More Info\n**We do NOT store your account credentials at ANY time in this process.**\n**Privacy Policy:** https://github.com/Sbotga/info/blob/main/legal/PRIVACY.md\n**More Information:** https://github.com/Sbotga/info/blob/main/en/LINKING.md',
                color=discord.Color.blue(),
            )

            await interaction.followup.send(embed=embed)

        view = views.SbotgaView(timeout=60)
        button = discord.ui.Button(
            label="Account Transfer", style=discord.ButtonStyle.primary
        )
        button.callback = transfer
        if region not in ["en", "jp"]:
            button.disabled = True
        view.add_item(button)
        button = discord.ui.Button(label="Proxy", style=discord.ButtonStyle.primary)
        button.callback = proxy
        view.add_item(button)

        embed = embeds.embed(
            title=f"{region.upper()} Account Data Update",
            description="Please choose your update method below. Different methods have different cooldowns for usage.\n\n1. Account Transfer (JP and EN servers only)\n2. Proxy (Apple devices only, all servers)\n\n**Privacy Policy:** https://github.com/Sbotga/info/blob/main/legal/PRIVACY.md\n**More Information:** https://github.com/Sbotga/info/blob/main/en/LINKING.md",
            color=discord.Color.from_rgb(247, 102, 30),
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @user_pjsk.command(
        auto_locale_strings=False,
        name="link",
        description="Link your PJSK account to your Discord account.",
    )
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    @app_commands.describe(region=locale_str("general.region"))
    async def user_pjsk_link(
        self, interaction: discord.Interaction, region: str = "default"
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        )
                    )
                ),
                ephemeral=True,
            )
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        if pjsk_id:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    f"You are already linked to a PJSK {region.upper()} account. We do not support alt accounts."
                ),
                ephemeral=True,
            )
        await interaction.response.send_modal(
            self.UserIDModal(region=region, bot=self.bot)
        )

    @user_pjsk.command(
        auto_locale_strings=False,
        name="unlink",
        description="Unlink your PJSK account from your Discord account.",
    )
    @app_commands.autocomplete(
        region=autocompletes.autocompletes.pjsk_region(["en", "jp", "tw", "kr", "cn"])
    )
    @app_commands.describe(region=locale_str("general.region"))
    async def user_pjsk_unlink(
        self, interaction: discord.Interaction, region: str = "default"
    ):
        region = region.lower().strip()
        if region not in ["en", "jp", "tw", "kr", "cn", "default"]:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    await interaction.translate(
                        locale_str(
                            "errors.unsupported_region",
                            replacements={"{region}": region.upper()},
                        )
                    )
                ),
                ephemeral=True,
            )
        if region == "default":
            region = await self.bot.user_data.discord.get_settings(
                interaction.user.id, "default_region"
            )
        pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
            interaction.user.id, region
        )
        if not pjsk_id:
            return await interaction.response.send_message(
                embed=embeds.error_embed(
                    f"You are not linked to a PJSK {region.upper()} account."
                ),
                ephemeral=True,
            )
        await self.bot.user_data.discord.remove_pjsk_id(interaction.user.id, region)
        embed = embeds.success_embed(
            title="Unlink Success",
            description=f"Unlinked your PJSK {region.upper()} account.",
        )
        await interaction.response.send_message(embed=embed)

    @user_pjsk.command(
        auto_locale_strings=False,
        name="accounts",
        description="View your currently linked accounts.",
    )
    async def user_pjsk_accounts(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        regions = ["en", "jp", "tw", "kr", "cn"]
        embed = embeds.embed(
            title=f"Your PJSK Linked Accounts", color=discord.Color.blurple()
        )
        desc_text = ""
        for region in regions:
            pjsk_id = await self.bot.user_data.discord.get_pjsk_id(
                interaction.user.id, region
            )
            desc_text += f"**{region.upper()} PJSK Account:** {'`' + str(pjsk_id) + '`' if pjsk_id else 'Not Linked'}\n"
        embed.description = desc_text.strip()
        await interaction.followup.send(embed=embed)

    @user.command(
        auto_locale_strings=False, name="settings", description="Sbotga settings."
    )
    async def user_settings(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        settings = await self.bot.user_data.discord.get_settings(interaction.user.id)

        ignore_keys = ["first_time_guess_end"]

        filtered_settings = {
            key: value for key, value in settings.items() if key not in ignore_keys
        }

        setting_names_map = {"default_region": "Default Region"}
        options_map = {"default_region": ["EN", "JP", "TW", "KR"]}  # , "CN"]

        class CustomSelect(discord.ui.Select):
            def __init__(self, options: list[str] | dict, placeholder: str):
                if type(options) == list:
                    select_options = [
                        discord.SelectOption(label=option) for option in options
                    ]
                elif type(options) == dict:
                    select_options = [
                        discord.SelectOption(label=key, value=value)
                        for key, value in options.items()
                    ]
                super().__init__(placeholder=placeholder, options=select_options)

            async def callback(self, interaction: discord.Interaction):
                if (
                    interaction.user.id
                    != interaction.message.interaction_metadata.user.id
                ):
                    embed = embeds.error_embed(
                        await interaction.translate("errors.cannot_select")
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                self.placeholder = self.values[0]
                await interaction.response.defer()
                await self.custom_callback(interaction, self.values[0].lower())

            async def custom_callback(
                self, interaction: discord.Interaction, value: str
            ): ...

        class SettingsView(views.SbotgaView):
            def __init__(self):
                super().__init__()

        view = SettingsView()
        settings_select = CustomSelect(
            {setting_names_map[key]: key for key in filtered_settings.keys()},
            "Select a setting...",
        )

        def to_readable(value) -> str:
            if type(value) == bool:
                return {True: "True", False: "False"}[value]
            elif type(value) in [int, float]:
                return f"{value:,}"
            else:
                return value.upper()

        class ToggleButton(discord.ui.Button):
            def __init__(
                self,
                bot: DiscordBot,
                key: str,
                current_value: bool,
                *,
                style=discord.ButtonStyle.primary,
                label=None,
                disabled=False,
                custom_id=None,
                url=None,
                emoji=None,
                row=None,
                sku_id=None,
            ):
                super().__init__(
                    style=style,
                    label=label,
                    disabled=disabled,
                    custom_id=custom_id,
                    url=url,
                    emoji=emoji,
                    row=row,
                    sku_id=sku_id,
                )
                self.key = key
                self.bot = bot
                self.value = current_value

            async def callback(self, interaction):
                if (
                    interaction.user.id
                    != interaction.message.interaction_metadata.user.id
                ):
                    embed = embeds.error_embed(
                        await interaction.translate("errors.cannot_click")
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                await interaction.response.defer()
                settings = await self.bot.user_data.discord.change_settings(
                    interaction.user.id, self.key, not self.value
                )
                embed, view = generate_setting(self.key, settings[self.key])
                await interaction.followup.edit_message(
                    interaction.message.id, embed=embed, view=view
                )
                view.message = interaction.message

        def generate_setting(key: str, value):
            embed = embeds.embed(
                title=f"{setting_names_map[key]} Setting",
                description=f"This setting is currently set to `{to_readable(value)}`.",
                color=discord.Color.dark_gold(),
            )

            view = views.SbotgaView()
            view.add_item(settings_select)
            settings_select.placeholder = setting_names_map[key]
            if type(value) == bool:
                view.add_item(
                    ToggleButton(self.bot, key, value, label=f"Set to {not value}")
                )
            elif type(value) == str:
                select = CustomSelect(options_map[key], to_readable(value))

                async def change_value(interaction: discord.Interaction, value: str):
                    settings = await self.bot.user_data.discord.change_settings(
                        interaction.user.id, key, value.lower()
                    )
                    embed, view = generate_setting(key, settings[key])
                    await interaction.followup.edit_message(
                        interaction.message.id, embed=embed, view=view
                    )
                    view.message = interaction.message
                    await interaction.followup.send(
                        embed=embeds.success_embed("Setting changed."), ephemeral=True
                    )

                select.custom_callback = change_value
                view.add_item(select)
            return embed, view

        async def change_setting(interaction: discord.Interaction, value: str):
            def reverse_lookup(d, item):
                return next((k for k, v in d.items() if v == item), None)

            settings = await self.bot.user_data.discord.get_settings(
                interaction.user.id
            )
            filtered_settings = {
                key: value for key, value in settings.items() if key not in ignore_keys
            }
            embed, view = generate_setting(value, filtered_settings[value])
            await interaction.followup.edit_message(
                interaction.message.id, embed=embed, view=view
            )

        settings_select.custom_callback = change_setting

        view = views.SbotgaView()
        view.add_item(settings_select)

        embed = embeds.embed(
            title="Changing Settings",
            description="Please select the setting you'd like to change.",
            color=discord.Color.blue(),
        )

        await interaction.followup.send(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: DiscordBot):
    await bot.add_cog(UserCog(bot))
