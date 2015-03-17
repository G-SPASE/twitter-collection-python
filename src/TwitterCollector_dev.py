#!/usr/bin/env python                                                                                                                                             
# -*- coding:utf-8 -*- 

# InfluentialTweetsForEvc.py
# Last Update: 2015-03-17
# Author: Satoshi Miyazawa
# koitaroh@gmail.com
# Objective: Collect tweet and store into database

from __future__ import print_function
from tweepy import Stream
from tweepy import OAuthHandler
from tweepy.streaming import StreamListener
import time, datetime, json, sys, codecs, csv, calendar, MeCab, ConfigParser, traceback, os, MySQLdb

# Constants                                                                                                                                                     
MECAB_MODE = 'mecabrc'
PARSE_TEXT_ENCODING = 'utf-8'

# Reload sys module in order to set default encoding as utf-8.
reload(sys)
sys.setdefaultencoding('utf-8')
d = datetime.datetime.today()
conf = ConfigParser.SafeConfigParser()
conf.read('../config.cfg')
print("initiated at:" + d.strftime("%Y-%m-%d %H:%M:%S"))
i = 0

# initialize filename_json
# filename_json = "TweetsJSON_"+d.strftime("%Y%m%d%H%M%S")+".txt"
# filename_csv = "TweetsCSV_"+d.strftime("%Y%m%d%H%M%S")+".txt"
# f_CSV = codecs.open(filename_csv,"a","utf-8")
# f_CSV.write('tweet_id, datetime, user_name, user_id, x, y, raw_tweet\n')
table_name = "tweet_table_dev_" + d.strftime("%Y%m%d%H%M%S")

consumer_key = conf.get('twitter_dev', 'consumer_key')
consumer_secret = conf.get('twitter_dev', 'consumer_secret')
access_token_key = conf.get('twitter_dev', 'access_token_key')
access_token_secret = conf.get('twitter_dev', 'access_token_secret')

local_db = {
            "host": conf.get('local_db', 'host'),
            "user": conf.get('local_db', 'user'),
            "passwd": conf.get('local_db', 'passwd'),
            "db_name": conf.get('local_db', 'db_name'),
            }   


# Function to convert "created at" in GMT to JST
def YmdHMS(created_at):
    time_utc = time.strptime(created_at, '%a %b %d %H:%M:%S +0000 %Y')
    unix_time = calendar.timegm(time_utc)
    time_local = time.localtime(unix_time)
    return str(time.strftime("%Y-%m-%d %H:%M:%S", time_local))

def HMS(created_at):
    time_utc = time.strptime(created_at, '%a %b %d %H:%M:%S +0000 %Y')
    unix_time = calendar.timegm(time_utc)
    time_local = time.localtime(unix_time)
    return str(time.strftime("%H:%M:%S", time_local))

class listener(StreamListener):
    def on_status(self, status):
        print(status.text)

    def on_data(self, data):
        global i
        try:
            tweet = json.loads(data + "\n","utf-8")

            # Write as JSON
            # f = codecs.open(filename_json,"a","utf-8")
            # json.dump(tweet,f,indent=4,ensure_ascii=False)
            # f.write(',')
            # f.close()           

            # Write to CSV
            # Collect tweets only in Japanese and with geo-tag
            if tweet['lang'] == 'ja' and tweet['geo']:
                
                raw_tweet = str(tweet['text']) # conver to from Unicode
                # writer = csv.writer(f_CSV)
                raw_tweet = raw_tweet.replace('\n','') # Get rid of return
                raw_tweet = raw_tweet.replace('\r','') # Get rid of return
                if "I'm at" not in raw_tweet:
                    datetimeJST = YmdHMS(tweet['created_at']) # convert datetime to local datetime.
                    timeJST = HMS(tweet['created_at']) # convert time to local time.
                    raw_tweet = filter(raw_tweet)


                    # run mecab engine to create dictonary
                    words_dict = mecab_parse(raw_tweet)
                    words = ",".join(words_dict['all'])
                    nouns = ",".join(words_dict['nouns'])
                    verbs = ",".join(words_dict['verbs'])
                    adjs =  ",".join(words_dict['adjs'])
                    
                    print("%d" % i +' ' + datetimeJST +': '+ raw_tweet + '\r')
                    i = i + 1

                    # print text segments.
                    # print("All:", words)
                    # print("Nouns:", nouns)
                    # print("Verbs:", verbs)
                    # print("Adjs:", adjs)
                    row = [

                        tweet['id'],
                        datetimeJST,
                        timeJST,
                        tweet['user']['screen_name'],
                        tweet['user']['id_str'],
                        tweet['geo']['coordinates'][1],
                        tweet['geo']['coordinates'][0],
                        raw_tweet,
                        words,
                        nouns,
                        verbs,
                        adjs

                        ]
                    tweet_table_dict = {
                        "tweet_id": tweet['id'],
                        "datetime": datetimeJST,
                        "time": timeJST,
                        "user_name": tweet['user']['screen_name'],
                        "user_id": tweet['user']['id_str'],
                        "x": tweet['geo']['coordinates'][1],
                        "y": tweet['geo']['coordinates'][0],
                        "raw_tweet": raw_tweet,
                        "words": words,
                        "nouns": nouns,
                        "verbs": verbs,
                        "adjs": adjs
                        }

                    insert_into_tweet_table(local_db, tweet_table_dict)
                    

                # writer.writerow(row)
        # ignore type error
        except ValueError:
            pass
        except BaseException, e:
            print('failed ondata,',str(e))
            # time.sleep(5)

    def on_error(self, status_code):
        print('Got an error with status code: ' + str(status_code))
        return True # To continue listening
 
    def on_timeout(self):
        print('Timeout...')
        return True # To continue listening

def filter(text):
    # "RT @user:"を削除
    if "RT " in text:
        text = text.split(":", 1)[1]
    # "@user"を削除
    # if "@" in text and " " in text:
    if text[0] == "@":
        text = text.split(" ", text.count("@"))[-1]
    # "#tag"を削除
    if "#" in text:
        text = text.split("#", 1)[0]
    # "URL"を削除
    if "http" in text:
        text = text.split("http", 1)[0]
    return text

def mecab_parse(text):
    tagger = MeCab.Tagger(MECAB_MODE)
    node = tagger.parseToNode(text)
    words = []
    nouns = []
    verbs = []
    adjs = []
    while node:
        pos = node.feature.split(",")[0]
        # unicode 型に戻す
        word = node.surface.decode("utf-8")
        if pos == "名詞":
            nouns.append(word)
        elif pos == "動詞":
            lemma = node.feature.split(",")[6]
            # verbs.append(word)
            verbs.append(lemma)
        elif pos == "形容詞":
            lemma = node.feature.split(",")[6]
            # adjs.append(word)
            adjs.append(lemma)
        words.append(word)
        node = node.next
    parsed_words_dict = {
        "all": words[1:-1], # 最初と最後には空文字列が入るので除去                                                                                                
        "nouns": nouns,
        "verbs": verbs,
        "adjs": adjs
        }
    return parsed_words_dict

# From mysql_tools
def create_db(db_info): 
    connector = MySQLdb.connect(
        host = db_info["host"],
        user = db_info["user"],
        passwd = db_info["passwd"],
        charset = "utf8mb4"
        )
    cursor = connector.cursor()
    sql = u"""
    CREATE DATABASE IF NOT EXISTS                                                                                                                                 
        %s                                                                                                                                                        
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci                                                                                                                                                    
    ;                                                                                                                                                             
    """ %(db_info["db_name"])
    cursor.execute(sql)
    connector.commit()
    cursor.close()
    connector.close()
    return True

def execute_sql(sql, db_info, is_commit = False):
    connector = MySQLdb.connect(
        host = db_info["host"],
        user = db_info["user"],
        passwd = db_info["passwd"],
        db = db_info["db_name"],
        charset = "utf8mb4"
        )
    cursor = connector.cursor()
    cursor.execute(sql)
    if is_commit:
        connector.commit()
    cursor.close()
    connector.close()
    return True

def create_tweet_table(db_info):
    sql = """                                                                                                                                                     
    CREATE TABLE IF NOT EXISTS                                                                                                                                    
        %s(
            id BIGINT PRIMARY KEY AUTO_INCREMENT,                                                                                                                 
            tweet_id BIGINT,                                                                                                                                      
            datetime DATETIME,
            time TIME,                                                                                                                                    
            user_name VARCHAR(50),                                                                                                                                       
            user_id BIGINT,                                                                                                                          
            x DECIMAL(10,6),
            y DECIMAL(10,6),                                                                                                                        
            raw_tweet TEXT,                                                                                                                                       
            words TEXT,                                                                                                                                           
            nouns TEXT,                                                                                                                                           
            verbs TEXT,                                                                                                                                           
            adjs TEXT                                                                                                                                             
        )
        CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci                                                                                                                                               
    ;                                                                                                                                                             
    """ %table_name
    execute_sql(sql, db_info, is_commit = True)
    return True

def insert_into_tweet_table(db_info, tweet_table_dict):
    sql = """                                                                                                                                                     
    INSERT INTO                                                                                                                                                   
        %s                                                                                                                                         
    VALUES(                                                                                                                                                       
        NULL, '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s'                                                                                    
        )                                                                                                                                                         
    ;                                                                                                                         
    """ %(
        table_name,
        tweet_table_dict["tweet_id"],
        tweet_table_dict["datetime"],
        tweet_table_dict["time"],
        tweet_table_dict["user_name"],
        tweet_table_dict["user_id"],
        tweet_table_dict["x"],
        tweet_table_dict["y"],
        tweet_table_dict["raw_tweet"],
        tweet_table_dict["words"],
        tweet_table_dict["nouns"],
        tweet_table_dict["verbs"],
        tweet_table_dict["adjs"]
        )
    execute_sql(sql, db_info, is_commit = True)
    return True

def main():
    while True: 
        try:
            # From mysql_tools.py
            create_db(local_db)

            create_tweet_table(local_db)

            auth = OAuthHandler(consumer_key, consumer_secret)
            auth.set_access_token(access_token_key, access_token_secret)
            twitterStream = Stream(auth, listener())
            twitterStream.filter(locations=[122.933198,24.045416,153.986939,45.522785])
                                                                                                                                                     
        except Exception:
            tb = sys.exc_info()[2]
            tbinfo = traceback.format_tb(tb)[0]
            pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
            # Try reconnection
            time.sleep(60)
            twitterStream = Stream(auth, listener())

if __name__ == '__main__':
    main()