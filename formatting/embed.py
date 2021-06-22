import discord

from formatting.constants import VERSION as BOTVERSION
from formatting.constants import NAME
from __main__ import bot, log

def gen_embed(name = None, icon_url = None, title = None, content = None):
        """Provides a basic template for embeds"""
        e = discord.Embed(colour = 0x1abc9c)
        if name and icon_url:
            e.set_author(name = name, icon_url = icon_url)
        e.set_footer(text = "Fueee~")
        e.title = title
        e.description = content
        return e

async def embed_splitter(embed: discord.Embed, destination: discord.abc.Messageable = None) -> List[discord.Embed]:
        """Take an embed and split it so that each embed has at most 20 fields and a length of 5900.
        Each field value will also be checked to have a length no greater than 1024.
        If supplied with a destination, will also send those embeds to the destination.
        """
        embed_dict = embed.to_dict()

        # Check and fix field value lengths
        modified = False
        if "fields" in embed_dict:
            for field in embed_dict["fields"]:
                if len(field["value"]) > 1024:
                    field["value"] = field["value"][:1021] + "..."
                    modified = True
        if modified:
            embed = discord.Embed.from_dict(embed_dict)

        # Short circuit
        if len(embed) < 5901 and (
                "fields" not in embed_dict or len(embed_dict["fields"]) < 21
        ):
            if destination:
                await destination.send(embed=embed)
            return [embed]

        # Nah we really doing this
        split_embeds: List[discord.Embed] = []
        fields = embed_dict["fields"]
        embed_dict["fields"] = []

        for field in fields:
            embed_dict["fields"].append(field)
            current_embed = discord.Embed.from_dict(embed_dict)
            if len(current_embed) > 5900 or len(embed_dict["fields"]) > 20:
                embed_dict["fields"].pop()
                current_embed = discord.Embed.from_dict(embed_dict)
                split_embeds.append(current_embed.copy())
                embed_dict["fields"] = [field]

        current_embed = discord.Embed.from_dict(embed_dict)
        split_embeds.append(current_embed.copy())

        if destination:
            for split_embed in split_embeds:
                await destination.send(embed=split_embed)
        return split_embeds