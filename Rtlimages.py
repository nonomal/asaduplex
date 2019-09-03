import os, sys, json, time, IFTTT, PID, filecmp

def fileOpen(fileloc):
	try: defOpen = open(fileloc); defReturn = defOpen.read(); defOpen.close()
	except IOError: return "No such file or directory."
	else: return defReturn

def asa():
	global upb, asaVersion
	formatAsaVersion = int("".join(asaVersion.split("."))); print("正在确认远程 Apple Store app 版本...")
	os.system("wget -t 100 -T 5 -q -O " + rpath + "iTunesLookup https://itunes.apple.com/cn/lookup?id=375380948")
	try: remoteAsaVersion = int("".join(json.loads(fileOpen(rpath + "iTunesLookup"))["results"][0]["version"].split(".")))
	except: remoteAsaVersion = 0
	if remoteAsaVersion > 0 and remoteAsaVersion < 100: remoteAsaVersion *= 10
	if remoteAsaVersion > formatAsaVersion:
		asaVersion = ".".join(list(str(remoteAsaVersion)))
		asaupd = "从远程获得了新的 Apple Store app 版本 " + asaVersion
		upb += asaupd + "\n"; print(asaupd)
	print("正在确认远程 Apple Store app 文件...")
	listLoc = rpath + "storeList.json"
	orgListSize = os.path.getsize(listLoc)
	os.system("mv " + listLoc + " " + listLoc.replace(".json", "-old.json"))
	newLocation = listLoc.replace(".json", "-old.json")
	os.system("wget -t 100 -T 5 -q -U ASA/" + asaVersion + " -O " + listLoc + " --header 'x-ma-pcmh: REL-" + 
		asaVersion + "' https://mobileapp.apple.com/mnr/p/cn/retail/allStoresInfoLite")
	newListSize = os.path.getsize(listLoc)
	if not filecmp.cmp(newLocation, listLoc) and orgListSize > 1024 and newListSize > 1024 :
		deltaListSize = newListSize - orgListSize
		if deltaListSize % 83:
			oldLocation = listLoc.replace(".json", "" + time.strftime("-%Y%m%d-%H%M%S", time.localtime()) + ".json")
			os.system("mv " + newLocation + " " + oldLocation)
			formatJSON = json.dumps(json.loads(fileOpen(listLoc)), ensure_ascii = False, indent = 2)
			formatOut = open(listLoc.replace(".json", "-format.json"), "w")
			formatOut.write(formatJSON); formatOut.close()
			IFTTT.pushbots("于 " + time.strftime("%Y 年 %-m 月 %-d 日 %-H:%M ", time.localtime()) 
				+ "检测到新文件，与上次存储的文件大小差异为 " + str(deltaListSize) + " 字节。", "Apple Store app 文件更新", 
				"https://www.apple.com/retail/store/flagship-store/drawer/michiganavenue/images/store-drawer-tile-1_small_2x.jpg", 
				"raw", masterKey[0], 0)
		else: os.system("mv " + listLoc.replace(".json", "-old.json") + " " + listLoc)
	else: 
		os.system("mv " + listLoc.replace(".json", "-old.json") + " " + listLoc)
		print("没有发现 storeList 文件更新")
	if newListSize == 0: print("无法下载 allStoresInfoLite 文件\n当前的 REL 验证版本是否不被远程服务器接受？")

def down(rtl, isSpecial):
	global upb, exce; spr = "R" + rtl + ".png"; sx = sbn + rtl + ".png"
	if os.path.isfile(sx): oldsize = os.path.getsize(sx)
	else: oldsize = 0
	os.system("wget -U ASA/" + asaVersion + " -t 100 -T 5 -q -N -P " + rpath + "Pictures/ " + dieter + spr)
	if os.path.isfile(sx): newsize = os.path.getsize(sx)
	else: newsize = 0
	if newsize != oldsize and newsize > 1:
		try: rname = storejson['name'][rtl]; rflag = storejson['flag'][rtl]; rnso = storejson['nso'][rtl]
		except KeyError: rname = "Store"; rflag = ""; rnso = ""
		if rnso != "" and rnso != "TBC": rnso = "这家零售店最早开幕于 " + time.strftime("%Y 年 %-m 月 %-d 日", time.strptime(rnso, "%Y-%m-%d")) + "。"
		pushRaw = "Apple " + rname + " (R" + rtl + ") 的图片更新，大小为 " + str(int(newsize / 1024)) + " KB"
		upb += pushRaw + "\n"; print(pushRaw)
		if isSpecial: exce += rtl + ", "
		tellRaw = "零售店编号 R" + rtl + "，新图片的大小是 " + str(int(newsize / 1024)) + " KB。" + rnso
		imageURL = dieter + spr + "?output-format=jpg"
		IFTTT.pushbots(tellRaw, rflag + "Apple " + rname + " 图片更新", imageURL, "raw", masterKey, 0)
	elif isSpecial:
			try: pname = "Apple " + storejson['name'][rtl] + " (R" + rtl + ")"
			except KeyError: pname = "Apple Store (R" + rtl + ")"  
			if newsize == 0: print(pid + " 检查到 " + pname + " 的图片服务器中不存在")
			else: print(pid + " 检查到 "+ pname + " 的图片没有更新")

global upb, asaVersion;
totalStore = 901; asaVersion = "5.5.0"
pid = str(os.getpid()); upb = exce = ""; arg = rTime = 0
for m in sys.argv[1:]: arg += 1
rpath = os.path.expanduser('~') + "/Retail/"; masterKey = IFTTT.getkey()
sbn = rpath + "Pictures/R"; storejson = json.loads(fileOpen(rpath + "storeInfo.json"))
PID.addCurrent(os.path.basename(__file__), os.getpid())
dieter = "https://rtlimages.apple.com/cmc/dieter/store/16_9/"

if arg == 1 and sys.argv[1] == "0": asa(); exit()

while True:
	eCount = exce.count(", ")
	if arg - eCount:
		print("正在刷新特别零售店 [第 " + str(rTime % 18 + 1) + " 次, 共 18 次]")
		for s in sys.argv[1:]: 
			if not s in exce: down(s, True)
	else: print("没有指定特别刷新零售店 [第 " + str(rTime % 18 + 1) + " 次, 共 18 次]")
	if not (rTime % 18):
		for j in range(1, totalStore): 
			down("%03d" % j, False)
			print(pid + " 已完成 " + str(int((j + 1) * 100 / totalStore)) + "%, 目前 R" + "%03d" % j + "\r", end = "")
			sys.stdout.flush()
	print(); asa(); rTime += 1
	print(upb + time.strftime("%F %T", time.localtime()) + "\n")
	time.sleep(1200)