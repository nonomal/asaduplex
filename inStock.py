import os, json, sys, urllib.request, time, IFTTT, PID
from bs4 import BeautifulSoup

def title(partno):
	global savedName
	url = "https://www.apple.com/cn/shop/product/" + partno
	try: soup = BeautifulSoup(urllib.request.urlopen(url, timeout = 20), features = "html.parser")
	except: savedName[partno] = "[获取产品名称出现错误]"
	else: savedName[partno] = soup.title.string.replace(" - Apple (中国大陆)", "").replace(" - Apple", "").replace("购买 ", "")

def fileOpen(fileloc):
	try: defOpen = open(fileloc); defReturn = defOpen.read(); defOpen.close()
	except IOError: return "No such file or directory."
	else: return defReturn

asaVersion = "5.5.0"
PID.addCurrent(os.path.basename(__file__), os.getpid())
rpath = os.path.expanduser('~') + "/Retail/"

checkProduct = sys.argv[1:]; combProduct = ",".join(checkProduct)
alreadyAvailable = {}; singleProductOutput = {}; upb = ""; global savedName; savedName = {}
statesJSON = json.loads(fileOpen(rpath + "storeList.json"))["countryStateMapping"][0]["states"]
for j in range(len(checkProduct)): alreadyAvailable[checkProduct[j]] = []; singleProductOutput[checkProduct[j]] = ""

while True:
	stateStore = ""
	for s in range(len(statesJSON)):
		stateName = statesJSON[s]["stateName"]; storeJSON = statesJSON[s]["stores"]; stateStore += "【" + stateName + "】"
		for t in range(len(storeJSON)):
			passCheck = 0; stateStore += storeJSON[t]["storeName"] + ", "
			for c in range(len(checkProduct)): 
				if storeJSON[t]["storeNumber"] in alreadyAvailable[checkProduct[c]]: passCheck += 1
			if passCheck == len(checkProduct): continue
			dLoc = rpath + "stock" + storeJSON[t]["storeNumber"]
			os.system("wget -t 100 -T 5 -q -O " + dLoc + " --header 'x-ma-pcmh: REL-" + asaVersion + 
				"' --header 'X-DeviceConfiguration: ss=2.00;vv=" + asaVersion + ";sv=12.3.1' " + 
				"'https://mobileapp.apple.com/mnr/p/cn/rci/rciCheckForPart?partNumber=" +
				combProduct + "&storeNumber=" + storeJSON[t]["storeNumber"] + "'")
			print("[" + str(s + 1) + "/" + str(len(statesJSON)) + "] " + stateName + "正在下载 已完成 " + 
				str(int((t + 1) * 100 / len(storeJSON))) + "%\r", end = "")
			sys.stdout.flush()
		stateStore = stateStore[:-2]; print()
		for p in checkProduct:
			availableStore = []
			for f in storeJSON:
				try:
					stockJSON = json.loads(fileOpen(rpath + "stock" + f["storeNumber"]))["availability"]
					if stockJSON[p] and f["storeNumber"] not in alreadyAvailable[p]: 
						availableStore.append(f["storeName"])
						alreadyAvailable[p].append(f["storeNumber"])
				except: pass
			if len(availableStore): 
				singleAdd = "【" + stateName + "】" + ", ".join(availableStore)
				singleProductOutput[p] += singleAdd
	singleProductOutput[p] = singleProductOutput[p].replace(stateStore, "all across Mainland China")
	for o in checkProduct:
		if len(singleProductOutput[o]) > 0:
			productBasename = o[:-4]
			try: keyTest = savedName[productBasename]
			except KeyError: print("正在从远端取得商品名称..."); title(productBasename)
			singleTitle = savedName[productBasename].replace(" - ", "-")
			if savedName[productBasename] == "[获取产品名称出现错误]": del savedName[productBasename]
			if len(singleTitle) > 22:
				while len(singleTitle) > 22: singleTitle = singleTitle[:-1]
				singleTitle += "..."
			singleTitle.rstrip()
			pushOut = "到货零售店: " + singleProductOutput[o]
			pushOut = pushOut.replace("到货零售店: all across Mainland China", "全中国大陆 Apple Store 零售店均已到货该产品")
			upb += o + " " + pushOut + "\n"
			IFTTT.pushbots(
				pushOut, singleTitle + " 新到货", "https://as-images.apple.com/is/" 
				+ productBasename + "?wid=1280", "raw", IFTTT.getkey(), 0)
		else: print(o + " 产品没有检测到零售店新到货")
		singleProductOutput[o] = ""
	print(upb + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + "\n")
	os.system("rm -f " + rpath + "stockR*"); time.sleep(43200)