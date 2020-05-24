import authenticator
from tweepy import Stream, OAuthHandler
from tweepy.streaming import StreamListener
from pymongo import MongoClient
import sys
import time
import json


def classify(message):
    pass

# # # # MONGODB INIT # # # #
class MongoDbClient:

    def __init__(self, URI):
        # connection 
        try:
            self.connection = MongoClient(URI)
            print("Connection successfull!")
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
            self.collection.insert_one(d)
            return True

        except BaseException as e:
            print("Failed on_data ", str(e))
            time.sleep(5)


    def on_error(self, status):
        if status == 420:
            return False

        print(status)


class TwitterStreamer():

    def start_stream(self, stream, track):
        try:
            stream.filter(track = track)

        except KeyboardInterrupt:
            sys.exit("Exited program with CTRL+C")

        except BaseException:
            stream.disconnect()
            print("Base Exception Error...")
            print("Restarting...")
            self.start_stream(stream, track)
        except:
            print("Except:")
            stream.disconnect()
            self.start_stream(stream, track)

        

if __name__ == "__main__":

    # URI = "mongodb+srv://rami:Mur39172@my-cluster-ngfcm.mongodb.net/test?retryWrites=true&w=majority"

    URI = "mongodb+srv://rami:Mur39172@cluster0-ngfcm.mongodb.net/test?retryWrites=true&w=majority"
    
    client_db = MongoDbClient(URI).get_connection()
    db = client_db.get_database('My_Database')
    records = db.My_Collection

    try:
        # authenticator
        auth = TwitterAuthenticator().get_auth()

        # listener
        listener = TwitterListener(records)

        # Twitter stream
        twitter_stream = Stream(auth, listener)

        # streamer
        streamer = TwitterStreamer()

        # filter
        filter = ["depression", "I suffer from depression", "depressed"]
        streamer.start_stream(twitter_stream, filter)
        
    except Exception as e:
        print(e)

    except KeyboardInterrupt:
        sys.exit("Exited program with CTRL+C")

    finally:
        client_db.close()