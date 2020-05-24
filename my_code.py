import authenticator
from tweepy import Stream, OAuthHandler
from tweepy.streaming import StreamListener
from pymongo import MongoClient
import json

from textblob import TextBlob

from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences

from keras.models import model_from_json
import numpy as np
import os
import sys
import pickle
import time

import re

# SETTINGS FOR CLEANING TEXT
REPLACE_BY_SPACE_RE = re.compile('[/(){}\[\]\|@,;_]')
BAD_SYMBOLS_RE = re.compile('[^0-9a-z #+_]')
RESERVED_WORDS = re.compile(r'(RT|rt|FAV|fav|VIA|via)')


# CLEANING TWEETS
def clean_text(text):

    # to lowercase
    text = text.lower()
    # text = p.clean(text)

    # Removing punctuation and numbers
    text = re.sub('[^a-zA-Z]', ' ', text)

    # Single char removal
    text = re.sub(r"\s+[a-zA-Z]\s+", ' ', text)

    # Removing multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove Twitter reserved words: RT|FAV|VIA
    text = RESERVED_WORDS.sub('', text)

     # Replace REPLACE_BY_SPACE_RE symbols by space in text. 
     # Substitute the matched string in REPLACE_BY_SPACE_RE with space.
    text = REPLACE_BY_SPACE_RE.sub(' ', text)
    
    # Remove links
    text = re.sub(r'^https?:\/\/.*[\r\n]*', '', text)
   
    return text

# CHECK THE POLARITY OF THE TWEET
# IF IT IS NEGATIVE, WE WILL CHECK FOR ANY SIGNS OF DEPRESSION/SUICIDE IDEATION
def checkPolarity(text):
    
    # Pass tweet into TextBlob
    tweet = TextBlob(text)

    # Output sentiment polarity
    print(tweet.sentiment.polarity)

    # Return sentiment polarity
    return tweet.sentiment.polarity

# CHECK IF TWEET CONTAINS SIGNS OF DEPRESSION/SUICIDE IDEATION
def isSafe(tweet):

    # In Stream, we have filtered the tweets that contains extended tweets, but it does not always provide extended tweets
    if "extended_tweets" in tweet:
                if "full_text" in tweet["extended_tweets"]:

                    # Fetch the text
                    text = tweet["extended_tweets"]['full_text']

                else: 
                    return True
    
    elif "text" in tweet:
        
        # Fetch the text
        text = tweet['text']


    # Check its polarity
    polarity = checkPolarity(text)

    # If polarity is negative and tweet is not retweeted
    if polarity < 0 and "RT @" not in text:
        print("In Full Text Here")

        # Clean text
        text = clean_text(text)

    # If polarity is positive and/or tweet is retweeted, we move on
    else:
        return True

    # Transform text into sequences for predictions
    sent_token = TK.texts_to_sequences([text])

    # Pad the sent_token so it will match the input dimension of the model
    sent_padded = pad_sequences(sent_token, maxlen = maxlen, padding="post", truncating="post")

    # Prediction
    preds = model.predict(sent_padded)
    index = np.argmax(preds)

    print(text)
    print(f"Preds: {preds}")
    print(f"Index: {index}")
    
    # 1: Safe
    # 0: Depression/Suicide Ideation
    if index == 1: 
        return True
    else: 
        return False

# Check user previous tweets if his tweet has been classified as depression/suicide ideadion 
def checkUserHistory(user):
    pass

# Loading the model that we created
def loadModel():

    try:
        # load json and create model
        json_file = open('./models/BiLSTM-128/bilstm_128.json', 'r')
        loaded_model_json = json_file.read()
        json_file.close()
        loaded_model = model_from_json(loaded_model_json)

        # load weights into new model
        loaded_model.load_weights("./models/BiLSTM-128/model.h5")
        print("\nLoaded model from disk")

        return loaded_model

    except Exception as e:
        print("Error")
        print(e)
        sys.exit(0)


# Load the tokenizer
def loadTokenizer():

    try:
        # loading
        with open('tokenizer.pickle', 'rb') as handle:
            tokenizer = pickle.load(handle)
            print("\nLoaded Tokenizer...")
            return tokenizer

    except Exception as e:
        print("Error")
        print(e)
        sys.exit(0)


# # # # MONGODB INIT # # # #
class MongoDbClient:

    def __init__(self, URI):
        # connection 
        try:
            self.connection = MongoClient(URI)
            print("\nConnection successfull!\n")
        except:
            sys.exit("Unable to connect to Mongo.")

    def get_connection(self):
        return self.connection

    def close_connection(self):
        self.connection.close()

# # # # TWITTER AUTHENTIFICATION # # # #
class TwitterAuthenticator():

    def __init__(self):
        self.auth = OAuthHandler(authenticator.CONSUMER_KEY, authenticator.CONSUMER_SECRET)
        self.auth.set_access_token(authenticator.ACCESS_TOKEN, authenticator.ACCESS_TOKEN_SECRET)

    def get_auth(self):
        return self.auth


# # # # TWITTER LISTENER # # # # 
class TwitterListener(StreamListener):

    def __init__(self, collection):
        self.collection = collection

    def on_data(self, data):
        try:
            # print(data)
            d = json.loads(data)
            
            if not isSafe(d):
                self.collection.insert_one(d)
                print("Added new record!\n")
            return True

        except BaseException as e:
            print("Failed on_data ", str(e))
            time.sleep(5)


    def on_error(self, status):
        if status == 420:
            return False

        print(status)


# # # # TWITTER STREAMER # # # #
class TwitterStreamer():

    def start_stream(self, stream, track):
        try:
            stream.filter(track = track, languages=['en'], tweet_mode='extended')

        except KeyboardInterrupt:
            sys.exit("Exited program with CTRL+C")

        except BaseException:
            stream.disconnect()
            print("Base Exception Error...")
            print("Restarting...")
            self.start_stream(stream, track)

        except Exception as e:
            print("Except: \n", e)
            stream.disconnect()
            self.start_stream(stream, track)


if __name__ == "__main__":

    # Set max len for tokenizer
    maxlen = 100

    # Labels
    labels = ["Depression/Suicide", "Safe"]

    model = loadModel()

    TK = loadTokenizer()

    # Connect to MongoDB
    URI = "mongodb+srv://rami:Mur39172@cluster0-ngfcm.mongodb.net/test?retryWrites=true&w=majority"
    
    client_db = MongoDbClient(URI).get_connection()
    db = client_db.get_database('My_Database')
    records = db.Suicide

    # To empty the table/collection
    # records.delete_many({})

    try:
        # authenticator
        auth = TwitterAuthenticator().get_auth()

        # listener
        listener = TwitterListener(records)

        # Twitter stream
        twitter_stream = Stream(auth, listener, tweet_mode = 'extented')

        # streamer
        streamer = TwitterStreamer()

        # filter
        filter = ["depressed", "suicide", "depression", "kill myself"]
        streamer.start_stream(twitter_stream, filter)
        
    except Exception as e:
        print(e)

    except KeyboardInterrupt:
        sys.exit("Exited program with CTRL+C")

    finally:
        client_db.close()