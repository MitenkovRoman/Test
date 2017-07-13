#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import web
import json
import time
import myparser as parser
import shutil
import sqlite3
import datetime
import threading
import subprocess

urls = (
    '/accesspoints', 'accessPoints',
    '/', 'index',
    '/addtolist', 'addtolist',
    '/delfromlist', 'delfromlist',
    '/getlists', 'getLists',
    '/addtoemu', 'addtoemu',
    '/delfromemu', 'delfromemu',
    '/getemussids', 'getEmu',
    '/updatestate', 'updState'
)

ROOT_PATH = u'/home/pi/WiFiGun/'
SETTINGS_PATH = u'common/Settings.db'
LOGS_PATH = u'common/Logs.db'
#DATABASE_PATH = u'WiFiGun.db'
DATABASE_PATH = u'/home/pi/WiFiGun/tmp.db'

DEBUG_MESSAGE = u'отладка'
INFO_MESSAGE = u'информация'
WARNING_MESSAGE = u'предупреждение'
ERROR_MESSAGE = u'ошибка'

flags = {
    'mon':False,
    'emu':False
}


threads = {}
processes = {}


def secs_to_string(secs):
    measures = [
        (60, '{} сек', 60),
        (60, '{} мин', 60),
        (24, '{} ч', -1),
        (-1, '{} д'),
    ]
    secs = int(secs)
    for measure in measures:
        if secs/measure[0] > 0:
            secs = secs/measure[0]
        else:
            return measure[1].format(abs(secs))

            
def run_flag(fl):
    yield flags[fl]

def logMessage(type, message):
    logConnection = sqlite3.connect(ROOT_PATH + LOGS_PATH)
    logCursor = logConnection.cursor()
    logCursor.execute("INSERT INTO Logs (Type, Message, TimeSt) VALUES ('%s','%s','%s')" % (type, message, time.strftime("%d-%b-%Y %H:%M:%S")))
    logConnection.commit()
    logConnection.close()


def getSettingsParam(param):
    settingsConnection = sqlite3.connect(ROOT_PATH + SETTINGS_PATH)
    settingsCursor = settingsConnection.cursor()
    resultCursor = settingsCursor.execute("SELECT Value from CommonSettings where Name = '%s'" % (param))
    data = resultCursor.fetchall()
    settingsConnection.close()
    return data[0][0]


def setSettingsParam(param, value):
    settingsConnection = sqlite3.connect(ROOT_PATH + SETTINGS_PATH)
    settingsCursor = settingsConnection.cursor()
    settingsCursor.execute("UPDATE CommonSettings SET Value = '%s' WHERE Name = '%s'" % (value, param))
    settingsConnection.commit()
    settingsConnection.close()


class index:
    def GET(self):
        return json.dumps({'dev_data': DATABASE_PATH})

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class accessPoints:
    def POST(self):
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = dict_factory
        c = conn.cursor()
        c.execute('SELECT `AccessPoints`.`ID` as id,\
                            `AccessPoints`.`MAC`,\
                            `AccessPoints`.`SignalLevel`,\
                            `AccessPoints`.`PacketsCount`,\
                            `AccessPoints`.`Channel`,\
                            `AccessPoints`.`SSID`,\
                            `AccessPoints`.`Encryption`,\
                            `AccessPoints`.`Chipher`,\
                            `AccessPoints`.`Auth`,\
                            `AccessPoints`.`Manufactor`,\
                            `AccessPoints`.`Comment`,\
                            `AccessPoints`.`TimeAppend`,\
                            `AccessPoints`.`TimeLast`,\
                            `AccessPoints`.`Protocol`\
                            FROM `AccessPoints`')
        ap_data = c.fetchall()
        ap_tree = {}
        for ap in ap_data:
            ap_tree[ap['SSID']] = []
            last_seen = time.strptime(ap['TimeLast'], ' %Y-%m-%d %H:%M:%S')
            last_seen = time.mktime(time.gmtime()) - time.mktime(last_seen)
            ap['since'] = secs_to_string(last_seen)
        c.execute('select `Clients`.`ID` as id,\
                           `Clients`.`MAC`,\
                           `Clients`.`SignalLevel`,\
                           `Clients`.`PacketsCount`,\
                           `Clients`.`TimeAppend`,\
                           `Clients`.`SSID`,\
                           `Clients`.`TimeLast`\
                           from `Clients`')
        cl_data = c.fetchall()
        ssids = list(set([x['SSID'] for x in cl_data]))
        ssids_list = [{'value':ssids[x],'id':str(x)} for x in xrange(len(ssids))]
        for cl in cl_data:
            last_seen = time.strptime(cl['TimeLast'], ' %Y-%m-%d %H:%M:%S')
            last_seen = time.mktime(time.gmtime()) - time.mktime(last_seen)
            cl['since'] = secs_to_string(last_seen)
            if cl['SSID'] in ap_tree:
                ap_tree[cl['SSID']].append(cl['MAC'])
        ap_tree = [{'value':x, 'data': [{'value':y} for y in ap_tree[x]]} for x in ap_tree]
        for i in xrange(len(ap_tree)):
            ap_tree[i]['id'] = str(i)
            for j in xrange(len(ap_tree[i]['data'])):
                ap_tree[i]['data'][j]['id'] = str(i)+'.'+str(j)
        return json.dumps({'ap_data':ap_data, 'cl_data':cl_data, 'ap_tree':ap_tree, 'ssids_list':ssids_list})

class delfromlist:
    def POST(self):
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        params = web.input()
        table = ''
        if params['list'] == '0':
            table = 'WhiteList'
        else:
            table = 'BlackList'
        sql_q = "delete from %s where ID=%s" % (table, params['elem'])
        c.execute(sql_q)
        conn.commit()
        conn.close()
        return json.dumps({})


class addtolist:
    def POST(self):
        params = web.input()
        if params['mac'] == '':
            return json.dumps({})
        table = ''
        if params['wl'] == '0':
            table = 'WhiteList'
        else:
            table = 'BlackList'
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        sql_q = "insert into %s (MAC) VALUES ('%s')" % (table, params['mac'])
        c.execute(sql_q)
        conn.commit()
        conn.close()
        return json.dumps({})


class getLists:
    def POST(self):
        wl = ''
        bl = ''
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        sql_q = "select ID,MAC from WhiteList"
        c.execute(sql_q)
        data = c.fetchall()
        for line in data:
            wl += '<tr> <td> <label> <input type="checkbox" name="wl" value="%s"> %s </label> </td> </tr>' % line
        sql_q = "select ID,MAC from BlackList"
        c.execute(sql_q)
        data = c.fetchall()
        for line in data:
            bl += '<tr> <td> <label> <input type="checkbox" name="bl" value="%s"> %s </label> </td> </tr>' % line
        return json.dumps({'bl':bl, 'wl':wl})


class delfromemu:
    def POST(self):
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        params = web.input()
        table = ''
        sql_q = "delete from EmulatedSSIDs where ID=%s" % (params['elem'])
        c.execute(sql_q)
        conn.commit()
        conn.close()
        return json.dumps({})


class addtoemu:
    def POST(self):
        params = web.input()
        if params['ssid'] == '':
            return json.dumps({})
        table = ''
        
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        sql_q = "insert into EmulatedSSIDs (SSID) VALUES ('%s')" % (params['ssid'])
        c.execute(sql_q)
        conn.commit()
        conn.close()
        return json.dumps({})


class getEmu:
    def POST(self):
        emu = ''
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        sql_q = "select ID,SSID from EmulatedSSIDs"
        c.execute(sql_q)
        data = c.fetchall()
        for line in data:
            emu += '<tr> <td> <label> <input type="checkbox" name="wl" value="%s"> %s </label> </td> </tr>' % line
        return json.dumps({'emulatedssids':emu})


class updState:
    def POST(self):
        params = web.input()
        if not flags['mon'] and params['mon'] == u"true":
            flags['mon'] = True
            os.system(u'sudo rm -f '+ROOT_PATH+u"tmp*")
            os.system(u'cp '+ROOT_PATH+u'WiFiGun.db '+DATABASE_PATH)
            subprocess.Popen(["screen",'-dmS', 'airodump', "sudo", "airodump-ng", "-w", ROOT_PATH+u'tmp', "--output-format", "csv", "mon0"])
            threads['mon'] = threading.Thread(target=parser.parse_airodump, args=(run_flag, ROOT_PATH+u'tmp-01.csv',DATABASE_PATH))
            threads['mon'].start()
            #monitor on
        if not flags['emu'] and params['emu'] == u"true":
            a = 1
            #emulator on
        if flags['mon'] and params['mon'] == u"false":
            flags['mon'] = False
            threads['mon'].join()
            subprocess.Popen(["screen",'-S', 'airodump', "-X", "quit"])
            #monitor off
        if flags['emu'] and params['emu'] == u"false":
            #emulator off
            a = 1


if __name__ == "__main__":
    logMessage(INFO_MESSAGE, u'Инициализация ОС')
    os.system(u'sudo rm -f '+ROOT_PATH+u"tmp*")
    os.system(u'cp '+ROOT_PATH+u'WiFiGun.db '+ DATABASE_PATH)
    back = DATABASE_PATH
    currentSessionNumber = getSettingsParam('NextSessionNumber')
    setSettingsParam('NextSessionNumber', str(int(currentSessionNumber) + 1))
    DATABASE_PATH = ROOT_PATH+'Sessions/Session'+currentSessionNumber
    os.makedirs(DATABASE_PATH)
    DATABASE_PATH += '/Session.db'
    os.system(u'ln -T '+ back + u' ' + DATABASE_PATH)
    os.system(u"sudo airmon-ng check kill")
    os.system(u"sudo airmon-ng start wlan1")
    os.system(u"sudo service nginx restart")
    
    logMessage(INFO_MESSAGE, u'Запуск приложения')
    print 'work'
    app = web.application(urls, globals())
    app.run()
