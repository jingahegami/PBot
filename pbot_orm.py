import asyncio
import aiopg
from misc.queries import queries

def normalize(s):
	if type(s)==bytes:
		s = s.decode("utf-8")
	if type(s)==int:
		s = str(s)
	if type(s)==None:
		s=0
	return s			

class Result():
	def dictate(self):
		dicc = {}
		for prop,value in vars(self).items():
			dicc[prop]=value
		return dicc

async def connect(host=None,user=None,password=None,database=None,loop=None,dsn=None):
	if dsn:
		conn = await aiopg.connect(dsn)
	else:
		conn = await aiopg.connect(database=database,user=user,password=password,host=host,loop=loop,port=5432)
	db = await conn.cursor()
	print("Checking database...")
	for q in queries:
		await db.execute(q)
	return {'conn':conn,'db':db}

class ORM():

	def __init__(self,db,conn):
		self.db = db
		self.conn = conn
		self.lock = asyncio.Lock()

	async def select(self,table='',fields='*',params=''):
		if table=='':
			return
		if fields=='*':
			fields_str='*'
		else:
			fields_str = ",".join(fields)		
		if isinstance(params,dict):
			params_str = ""
			params_arr = []
			for param in params:
				if type(param) == int:
					param = str(param)
				params_str = params_str+' {key}=%s AND'.format(**{'key':param})
				params_arr.append(params[param])
			params_str='WHERE '+params_str[:-3]						
		elif params=='':
			params_str = ""
			params_arr = []
		else:
			return	
		sql = "SELECT {fields_str} FROM {table} {params_str}".format(**{'fields_str':fields_str,'table':table,'params_str':params_str})
		#print(sql)
		async with self.lock:
			await self.db.execute(sql,params_arr)
			result = Result()
			resp = await self.db.fetchone()
		if resp==None:
			return
		for idx,res in enumerate(resp):
			if type(res) == bytes:
				res = res.decode("utf-8")
			setattr(result, fields[idx], res)
		return result

	async def selectmany(self,table='',fields='*',params=''):
		if table=='':
			return
		if fields=='*':
			fields_str='*'
		else:
			fields_str = ",".join(fields)		
		if isinstance(params,dict):
			params_str = ""
			params_arr = []
			for param in params:
				if type(param) == int:
					param = str(param)
				params_str = params_str+' {key}=%s AND'.format(**{'key':param})
				params_arr.append(params[param])
			params_str='WHERE '+params_str[:-3]
		elif params=='':
			params_str = ""
			params_arr = []
		else:
			return		
		sql = "SELECT {fields_str} FROM {table} {params_str}".format(**{'fields_str':fields_str,'table':table,'params_str':params_str})
		#print(sql)
		async with self.lock:
			await self.db.execute(sql,params_arr)
			resp = await self.db.fetchall()
		if resp==None:
			return
		arr = []
		#print(resp)
		for res in resp:
			result = Result()
			for idx,r in enumerate(res):
				#print(idx,r)
				if type(r) == bytes or type(r) == bytearray:
					r = r.decode("utf-8")
				setattr(result, fields[idx],r)
			arr.append(result)
		return arr

	async def insert(self,table="",values={}):
		if table=='':
			return
		value_str = []
		prcnt_str = []
		value_arr = []
		for value in values:
			value_str.append(value)
			prcnt_str.append('%s')
			value_arr.append(normalize(values[value]))
		value_str = ",".join(value_str)
		prcnt_str = ",".join(prcnt_str)
		sql = "INSERT INTO {table}({value_str}) values({prcnt_str})".format(**{'table':table,'value_str':value_str,'prcnt_str':prcnt_str})
		async with self.lock:
			if await self.db.execute(sql,value_arr):
				await self.conn.commit()
				return 1

	async def update(self,table="",values={},params={}):
		if table=='':
			return
		if type(values)==dict:
			value_str = []
			value_arr = []	
			for value in values:
				value_str.append("{}=%s".format(value))
				value = normalize(values[value])
				value_arr.append(value)
			value_str = ",".join(value_str)	
		elif type(values)==str:
			values=values
		else:
			return 0
		if type(params)==dict:
			params_str = []
			param_arr = []	
			for param in params:
				params_str.append("{}=%s AND".format(param))
				param = normalize(params[param])
				param_arr.append(param)
			params_str = " ".join(params_str)	
		elif type(params)==str:
			params=params
		else:
			return 0
		params_str = params_str[:-3]
		sql = "UPDATE {table} SET {value_str} WHERE {params_str}".format(**{'table':table,'value_str':value_str,'params_str':params_str})
		#print(sql)
		async with self.lock:
			await self.db.execute(sql,(value_arr+param_arr))
			return 1

	async def delete(self,table='',values='',params={}):
		if table=='':
			return
		if isinstance(values,list):
			values = ",".join(values)
		params_str = ""	
		for param in params:
			params_str = params_str+" {key}={value} AND".format(**{'key':param,'value':params[param]})
		params_str = params_str[:-3]
		sql = "DELETE {values} FROM {table} WHERE {params_str}".format(**{'values':values,'table':table,'params_str':params_str})
		async with self.lock:
			await self.db.execute(sql)
			return 1	
