import json
import time
import discord
import asyncio
from discord.ext.commands import Bot
from discord.ext import commands
import unicodedata
from datetime import datetime
from random import randint
import hashlib
import pbot_orm
import os
import logging

#Parse config
with open("config.json","r+") as config:
    config = json.loads(config.read())
    if os.getenv('discord_token'):
        config['token']=os.getenv('discord_token')
    if os.getenv('DATABASE_URL'):
        config['dsn']=os.getenv('DATABASE_URL')
    if os.getenv('log_channel'):
        config['log_channel']=os.getenv('log_channel')
    if os.getenv('GCLOUD_API'):
        config['gcloud_api']=os.getenv('GCLOUD_API')

logger = logging.getLogger('discord')
logging.basicConfig(level=int(config['log_level']))

def timestamp():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return timestamp

async def log_members():
    logger.info("Logging missing members")
    res = await db.selectmany(table='members',fields=['id','server_id'])
    res2 = set(client.get_all_members())
    members = []
    db_members = []
    for r in res:
        db_members.append((r.id,r.server_id))
    for r in res2:
        members.append((int(r.id),int(r.server.id)))
    missing = set(members)-set(db_members)
    for m in missing:
        await db.insert(table='members',values={'id':m[0],'server_id':m[1],'verified':1})
        logger.info('Saved missing member {} (ServerID: {})'.format(m[0],m[1]))
    return 1

async def log_servers():
    logger.info("Logging missing servers")
    res = await db.selectmany(table='servers',fields=['id'])
    db_servers = [r.id for r in res]
    servers = [int(s.id) for s in client.servers]
    missing = set(servers) - set(db_servers)
    for m in missing:
        await Utils.make_server(id=m)
        logger.info("Logged missing server "+m)
    return 1

async def log_commands():
    logger.info("Logging commands")
    for i in client.servers:
        i = i.id
        for ii in client.commands:
            async with db.lock:
                await db.db.execute("INSERT INTO commands(command,server_id) SELECT %s,%s WHERE NOT EXISTS (SELECT command FROM commands WHERE command = %s AND server_id=%s)",(ii,i,ii,i,))

client = Bot(description="pbot_public", command_prefix=">>")
warn_whitelist = config['warn_whitelist']
logging_blacklist = []
db = pbot_orm.ORM(None,None)
server_cache = {}

class LogHandler(logging.StreamHandler):
    def __init__(self,log_channel):
        self.log_channel = log_channel
        logging.StreamHandler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        try:
            if self.log_channel:
                asyncio.ensure_future(client.send_message(self.log_channel,msg))
        except Exception as e:
            logger.error(str(e))


async def initialize():
    if 'dsn' in config:
        dicc = await pbot_orm.connect(dsn=config['dsn'])
    else:
        dicc = await pbot_orm.connect(
        host = config['db_address'],
        user = config['db_user'],
        password = config['db_password'],
        database = config['db_database'],
        loop=client.loop)
    db.db = dicc['db']
    db.conn = dicc['conn']
    logging_blacklist.append(config['logging_blacklist'])
    return
loop = asyncio.get_event_loop()
loop.run_until_complete(initialize())

@client.event
async def on_ready():
    handler =LogHandler(client.get_channel(config['log_channel'] if 'log_channel' in config else ''))
    handler.setFormatter(logging.Formatter('[%(levelname)s][%(asctime)s]%(name)s : %(message)s'))
    logger.addHandler(handler)
    await log_servers()
    await log_members()
    logging_blacklist.append(client.user.id)
    await log_commands()
    logger.info('Logged in as '+client.user.name+' (ID:'+client.user.id+') | Connected to '+str(len(client.servers))+' servers | Connected to '+str(len(set(client.get_all_members())))+' users')

def ascii_convert(s):
    if type(s)==str:
        return unicodedata.normalize('NFKD', s).encode('ascii','ignore')
    else:
        return s    

class User:
    id = ""
    name = ""
    server_id = ""
    join_date = ""
    info = ""
    warnings = 0
    verified = 0
    present = 0

    def __init__(self,id,server_id,warnings,verified,present,bday):
        self.id = id
        self.server_id = server_id
        self.warnings = warnings
        self.present = present
        self.disc_user = client.get_server(self.server_id).get_member(id)
        self.name = self.disc_user.name+'#'+self.disc_user.discriminator
        self.join_date = self.disc_user.joined_at
        self.birthday = bday
        

    async def update(self):
        update_dic = {
            'warns':self.warnings,
            'verified':self.verified,
            'in_server':self.present,
            'birthday':self.birthday
        }
        await db.update(table='members',values=update_dic,params={'id':self.id,'server_id':self.server_id})
        return 1

    async def warn(self):
        if self.warnings+1 >= self.server.max_warnings:
                return 2
        else:
            self.warnings = self.warnings+1
            await self.update()
            return 1

class Server:
    id = ""
    name=""
    added_on = ""
    welcome_channel = ""
    goodbye_channel = ""
    event_channel = ""
    log_channel = ""
    log_active = 0
    log_whitelist = []
    entry_text = ""
    entry_text_pm = ""
    goodbye_text = ""
    max_warnings = 0
    af_msg = 0
    af_time = 0
    af_warn = 0
    af_enabled = False

    async def update(self):
        if self.log_whitelist!=0:
            log_whitelist = json.dumps(self.log_whitelist)
        else:
            log_whitelist=0          
        update_dic = {
            'welcome_channel':self.welcome_channel,
            'goodbye_channel':self.goodbye_channel,
            'event_channel':self.event_channel,
            'log_channel':self.log_channel,
            'log_whitelist':log_whitelist,
            'entry_text':ascii_convert(self.entry_text),
            'entry_text_pm':ascii_convert(self.entry_text_pm),
            'goodbye_text':ascii_convert(self.goodbye_text),
            'max_warns':self.max_warnings,
            'antiflood_messages':self.af_msg,
            'antiflood_time':self.af_time,
            'antiflood_warns':self.af_warn,
            'antiflood_enabled':int(self.af_enabled)
        }
        server_cache[self.id] = self
        await db.update(table='servers',values=update_dic,params={'id':str(self.id)})
        return 1

    async def get_member(self,id):
        res = await db.select(table='members',fields=[
            'warns','verified',
            'in_server','birthday'],params={'server_id':self.id,
            'id':id})
        if res:
            user = User(id,self.id,res.warns,res.verified,res.in_server,res.birthday)
            user.server = self
            return user

    async def make_member(self,id,verified=0):
        await db.insert(table='members',values={
            'id':id,
            'server_id':self.id,
            'verified':verified
            })
        return await self.get_member(id)

    async def toggle_logging_msg(self):
        if self.log_active_message==0:
            self.log_active_message=1
            if await self.update():
                return 1              
        else:
            self.log_active_message=0
            if await self.update():
                return 2

    async def toggle_logging_name(self):
        if self.log_active_name==0:
            self.log_active_name=1
            if await self.update():
                return 1              
        else:
            self.log_active_name=0
            if await self.update():
                return 2                

class Utils:

    async def get_server(id):
        if id in server_cache:
            return server_cache[id]
        result = await db.select(table='servers',fields=[
        'added_on','entry_text','entry_text_pm','goodbye_text',
        'log_whitelist','welcome_channel','goodbye_channel','event_channel',
        'log_channel','log_active_msg','log_active_name','max_warns','antiflood_messages','antiflood_time',
        'antiflood_warns','antiflood_enabled'],params={'id':id})
        id = str(id)
        if result==None:
            return
        if result.log_whitelist:
            log_whitelist = json.loads(result.log_whitelist)
        else:
            log_whitelist=0
        if result.entry_text==None:
            result.entry_text = config['default_entrytext']
        if result.entry_text_pm==None:
            result.entry_text_pm = config['default_entrytextpm']
        if result.goodbye_text==None:
            result.goodbye_text = config['default_goodbye']
        srv = Server()          
        srv.id = id
        srv.added_on = result.added_on
        srv.welcome_channel = result.welcome_channel
        srv.goodbye_channel = result.goodbye_channel
        srv.event_channel = result.event_channel
        srv.log_channel = result.log_channel
        srv.log_active_message = result.log_active_msg
        srv.log_active_name = result.log_active_name 
        srv.log_whitelist = log_whitelist
        srv.entry_text = result.entry_text
        srv.entry_text_pm = result.entry_text_pm
        srv.goodbye_text = result.goodbye_text
        srv.max_warnings = int(result.max_warns)
        srv.disc_server = client.get_server(id)
        srv.af_msg = result.antiflood_messages
        srv.af_time = result.antiflood_time
        srv.af_warn = result.antiflood_warns
        srv.af_enabled = bool(result.antiflood_enabled)
        server_cache[id] = srv
        return srv

    def random(dig):
        size = "0"
        while len(size)<=dig:
            size = size+'0'
        return randint(int('1'+size),int('1'+size+'0'))

    def make_hash(*args,length=64):
        tobehashed = ''
        for arg in args:
            tobehashed = tobehashed+str(arg)
        tobehashed = tobehashed.encode("utf-8")
        hash_object = hashlib.sha256(tobehashed)
        return hash_object.hexdigest()[:length]    

    def check_perms_ctx(ctx,perm):
        server = ctx.message.server
        user = server.get_member(ctx.message.author.id)
        return getattr(user.server_permissions,perm)
        
    async def make_server(id=0):
        await db.insert(table='servers',values={'id':id})
        return await Utils.get_server(id)
                        
    async def delete_server(id):
        await db.delete(table='servers',params={'id':id})
        await db.delete(table='members',params={'server_id':id})
        server_cache.pop(id)
