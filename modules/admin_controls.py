from pbot_utils import *
from asyncio import sleep

#member check command
@client.command(pass_context=True)
async def check(ctx, arg):
    if Utils.check_perms_ctx(ctx,'ban_members'):
        user_id = ''.join(ctx.message.raw_mentions)
        srv = await Utils.get_server(ctx.message.server.id)
        usr = await srv.get_member(user_id)
        join_date = usr.join_date
        top_role = ctx.message.server.get_member(user_id).top_role
        embed = discord.Embed(title=':mag: >PBot User Lookup', color=0xc242f4)
        embed.add_field(name='Discord Name', value=usr.name, inline=False)
        embed.add_field(name='Discord ID', value=user_id, inline=False)
        embed.add_field(name='Join Date', value=join_date, inline=False)
        embed.add_field(name='Warning Count', value=str(usr.warnings)+' ({} warns left)'.format(int(srv.max_warnings)-int(usr.warnings)), inline=False)
        embed.add_field(name='Highest rank', value=top_role, inline=False)
        embed.set_footer(text='Requested by '+ctx.message.author.name+'#'+ctx.message.author.discriminator+' on '+str(timestamp()))
        await client.send_message(ctx.message.author,embed=embed)
        embed = discord.Embed(title='Admin options',color=0xc242f4)
        embed.add_field(name=':warning: to warn',value='Warns the user (No reason)',inline=False)
        embed.add_field(name=':raised_hand: to softban',value='Softbans for 5 minutes',inline=False)
        embed.add_field(name=':mens: to clear',value="Clears the user's warnings",inline=False)
        await client.say(":white_check_mark: The user's report card has been sent in your DMs")
        msg = await client.send_message(ctx.message.author,embed=embed)
        await client.add_reaction(msg,'\U000026a0')
        await client.add_reaction(msg,'\U0000270b')
        await client.add_reaction(msg,'\U0001f6b9')
        await asyncio.sleep(1)
        res = await client.wait_for_reaction(['\U000026a0','\U0000270b','\U0001f6b9'],message=msg)
        if res.reaction.emoji == '\U000026a0':
            warnman = usr
            if str(user_id) not in warn_whitelist:
                if await warnman.warn()==1:
                    await client.say(':exclamation: <@!'+str(user_id)+'> has been warned. His warning count is now '+str(warnman.warnings+1)+' ('+str(int(srv.max_warnings)-int(warnman.warnings) -1)+' warns left)')
                    embed=discord.Embed(title=":exclamation: User Warned", color=0xed00f9)
                    embed.add_field(name="User warned", value=warnman.name, inline=False)
                    embed.add_field(name="Admin in charge", value=ctx.message.author.name, inline=False)
                    embed.add_field(name="Reason", value="No reason provided", inline=False)
                    embed.add_field(name="Warning count", value=str(usr.warnings+1)+' ('+str(int(srv.max_warnings)-int(usr.warnings) -1)+' warns left)', inline=False)
                    embed.set_footer(text=str(timestamp()))
                    await client.send_message(client.get_channel(srv.log_channel),embed=embed)
                elif await warnman.warn()==2:
                    member2server = server.get_member(user_id)
                    msg = await client.send_message(ctx,message.author,':exclamation: User has {} warnings and will be banned! Click on :white_check_mark: to confirm...'.format(warnman.warnings))
                    await client.add_reaction(msg,'👍')
                    await asyncio.sleep(1)
                    res = await client.wait_for_reaction(message=msg)
                    if res.reaction.emoji == '👍':
                        await client.send_message(client.get_user_info(user_id),'You have been banned for breaking the rules. You totally received '+str(warns)+' warnings before being issued a ban.')
                        await client.ban(member2server)
                else:
                    await client.send_message(ctx.message.author,config['default_error'])        
            else:
                await client.send_message(ctx.message.author,':negative_squared_cross_mark: Haha nice try cuck. You cant warn me :^)')
        if res.reaction.emoji == '\U0000270b':
            unverified = discord.utils.get(server.roles, name="Unverified")
            user_id = ''.join(ctx.message.raw_mentions)
            time = 5*60
            await client.add_roles(server.get_member(user_id), unverified)
            await client.send_message(ctx.message.author,':white_check_mark: <@!'+str(user_id)+'> has been denied access for '+str(5)+' minutes...')
            await asyncio.sleep(time)
            await client.remove_roles(server.get_member(user_id), unverified)
            await client.say('<@!'+str(user_id)+'> is here again!')
        if res.reaction.emoji == '\U0001f6b9':
            usr.warnings = 0
            if await usr.update():
                await client.send_message(ctx.message.author,':white_check_mark: <@!'+user_id+'> is now clear!')
            else:
                await client.send_message(ctx.message.author,config['default_error'])    


@client.command(pass_context=True)
async def massdelete(ctx,msgfrom=None,msgto=None):
    if Utils.check_perms_ctx(ctx,'manage_messages'):
        if not msgfrom:
            return await client.say("""
            __**Usage:**__
            >>massdelete *# of messages above to be deleted (Max:100)*
            >>massdelete *message_id* *# of messages above that ID to be deleted*
            >>massdelete *message_id* *message_id* (Messages between those IDs will be deleted)
            """)
        channel = ctx.message.channel
        if msgto:
            if len(msgto)<=3:
                try:
                    msgto = int(msgto)
                except Exception:
                    return await client.say("Invalid input")
                message_before = await client.get_message(channel,msgfrom)
                del_list = await client.purge_from(channel=channel, before=message_before, limit=msgto)
            else:
                message_after = await client.get_message(channel,msgfrom)
                message_before = await client.get_message(channel,msgto)
                del_list = await client.purge_from(channel=channel, before=message_before, after=message_after)
        else:
            try:
                msgfrom = int(msgfrom)
            except Exception:
                return await client.say("Invalid input")
            if msgfrom<=100:
                del_list = await client.purge_from(channel=channel,limit=msgfrom)
            else:
                await client.say(":negative_squared_cross_mark: You can't massdelete more than 100 messages at a time")
        msg = await client.say(':white_check_mark: Successfully deleted '+str(len(del_list))+' messages !')
        await sleep(2)
        await client.delete_message(msg)
    else:
       await client.say(config['error_permissions'].format('Manage Messages'))

@client.command(pass_context=True)
async def verify(ctx,arg):
    server = await Utils.get_server(ctx.message.server.id)
    if Utils.check_perms_ctx(ctx,'kick_members'):
        unverified = discord.utils.get(server.disc_server.roles, name="Unverified")
        user_id = ''.join(ctx.message.raw_mentions)
        usr = await server.get_member(user_id)
        usr.verified = 1
        if await usr.update():
            await client.remove_roles(usr.disc_user, unverified)
            await client.say(':white_check_mark: Manually verified <@!'+str(user_id)+'> !')    
        else:
            await client.say(config['default_error'])        
    else:
        await client.say(config['error_permissions'].format('Kick Members'))